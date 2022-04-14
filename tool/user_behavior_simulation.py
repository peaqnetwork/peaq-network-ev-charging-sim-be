import time
from threading import Thread
import argparse
import logging

import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from substrateinterface import Keypair
import src.p2p_utils as P2PUtils
import src.user_utils as UserUtils

from src.chain_utils import get_substrate_connection, generate_key_pair_from_mnemonic
from src.chain_utils import parse_redis_config, init_redis
from src.constants import REDIS_OUT
from src import config_utils as ConfigUtils

import utils as ToolUtils

from peaq_network_ev_charging_message_format.python import p2p_message_format_pb2 as P2PMessage
import redis
import socketio
import json

RUNTIME_ENV = 'RUNTIME_ENV'
RUNTIME_DEFAULT = 'dev'


def parse_arguement():
    parser = argparse.ArgumentParser()
    parser.add_argument('--deposit_token', help='deposit token amount',
                        type=int, default=10)
    parser.add_argument('--provider_config', help='provider config yaml file',
                        type=str, default='etc/config.yaml')
    parser.add_argument('--consumer_config', help='consumer config yaml file',
                        type=str, default='tool/consumer.config.yaml')
    parser.add_argument('--node_ws', help="peaq node's url",
                        type=str, default='ws://127.0.0.1:9944')
    parser.add_argument('--be_url', help="peaq charging simulator BE url",
                        type=str, default='http://127.0.0.1:25566')
    parser.add_argument('--provider_mnemonic', help='will be used only if on preview branch',
                        type=str, default='ws://127.0.0.1:9944')
    parser.add_argument('--rconfig', help='redis config yaml file',
                        type=str, default='etc/redis.yaml')
    parser.add_argument('--p2p', help='wait for p2p client request',
                        action='store_true')
    return parser.parse_args()


def reconnect(sio: socketio.Client):
    sio.emit('json', json.dumps({
        'type': 'Reconnect',
        'data': '',
    }))


def republish_did(sio: socketio.Client):
    sio.emit('json', json.dumps({
        'type': 'RePublishDID',
        'data': '',
    }))


def get_pk(sio: socketio.Client):
    sio.emit('json', json.dumps({
        'type': 'GetPK',
        'data': '',
    }))


def get_balance(sio: socketio.Client):
    sio.emit('json', json.dumps({
        'type': 'GetBalance',
        'data': '',
    }))


def user_simulation_test(ws_url: str,
                         be_url: str,
                         p2p_flag: bool,
                         kp_consumer: Keypair,
                         kp_provider: Keypair,
                         token_deposit: int):
    with get_substrate_connection(ws_url) as substrate:
        sio = socketio.Client()
        sio.connect(be_url)
        reconnect(sio)
        # republish_did(sio)
        get_pk(sio)
        get_balance(sio)
        sio.disconnect()

        token_num = token_deposit * ToolUtils.TOKEN_NUM_BASE
        ToolUtils.deposit_money_to_multsig_wallet(substrate, kp_consumer, kp_provider, token_num)
        if not p2p_flag:
            ToolUtils.send_service_request(substrate, kp_consumer, kp_provider, token_num)
            P2PUtils.send_service_request(r, kp_consumer, kp_provider.ss58_address, token_num)
            logging.info('---- Start charging and wait')
        else:
            logging.info('⚠️ ⚠️ ⚠️  Please send the service request!!')
            logging.info('---- Wait for the service request')


class RedisMonitor():
    def __init__(self,
                 r: redis.Redis,
                 ws_url: str,
                 be_url: str,
                 p2p_flag: bool,
                 kp_consumer: Keypair,
                 threshold: int):
        self._threshold = threshold
        self._kp_consumer = kp_consumer
        self._substrate = get_substrate_connection(ws_url)
        self._sio = socketio.Client()
        self._sio.connect(be_url)
        self._r = r
        self._p2p_flag = p2p_flag

    def __del__(self):
        if self._substrate:
            self._substrate.close()
        self._sio.disconnect()

    def redis_reader(self):
        subcriber = r.pubsub()
        subcriber.subscribe(REDIS_OUT)
        # subcriber.subscribe(REDIS_IN)

        while True:
            event_data = subcriber.get_message(True, timeout=30000.0)

            if not event_data:
                continue

            event = UserUtils.decode_hex_event(event_data['data'].decode('ascii'))

            if event.event_id == P2PMessage.EventType.SERVICE_REQUEST_ACK:
                if not self._p2p_flag:
                    time.sleep(10)
                    logging.info('✅ ---- send request !!')
                    self._sio.emit('json', json.dumps({
                        'type': 'UserChargingStop',
                        'data': True,
                    }))
                else:
                    logging.info('⚠️ ⚠️ ⚠️  Please send the charging stop!!')

            if event.event_id == P2PMessage.EventType.SERVICE_DELIVERED:
                provider_addr = event.service_delivered_data.provider
                refund_info = {
                    'token_num': int(event.service_delivered_data.refund_info.token_num),
                    'timepoint': {
                        'height': event.service_delivered_data.refund_info.time_point.height,
                        'index': event.service_delivered_data.refund_info.time_point.index,
                    },
                    'call_hash': event.service_delivered_data.refund_info.call_hash
                }
                spent_info = {
                    'token_num': int(event.service_delivered_data.spent_info.token_num),
                    'timepoint': {
                        'height': event.service_delivered_data.spent_info.time_point.height,
                        'index': event.service_delivered_data.spent_info.time_point.index,
                    },
                    'call_hash': event.service_delivered_data.spent_info.call_hash
                }
                ToolUtils.approve_token(
                    self._substrate, self._kp_consumer,
                    [provider_addr], self._threshold, spent_info)
                ToolUtils.approve_token(
                    self._substrate, self._kp_consumer,
                    [provider_addr], self._threshold, refund_info)
            logging.info(f"{event.event_id}: {event}")


# Only print
class SubstrateMonitor():
    def __init__(self, ws_url: str, kp_consumer: Keypair, threshold: int):
        self._threshold = threshold
        self._kp_consumer = kp_consumer
        self._substrate = get_substrate_connection(ws_url)

    def __del__(self):
        if self._substrate:
            self._substrate.close()

    def subscription_event_handler(self, objs, update_nr, subscription_id):
        for obj in objs:
            event = obj['event'].value
            if event['event_id'] == 'ExtrinsicSuccess' or event['event_id'] == 'NewBaseFeePerGas':
                continue
            logging.info(f"chain: {event['event_id']}: {event['attributes']}")

    def run_substrate_monitor(self):
        self._substrate.query('System', 'Events', None,
                              subscription_handler=self.subscription_event_handler)


if __name__ == '__main__':
    args = parse_arguement()
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s : %(message)s')

    # Test whether the node ws is available
    try:
        get_substrate_connection(args.node_ws).close()
    except ConnectionRefusedError:
        logging.error('⚠️  No target node running')
        sys.exit()

    runtime_env = os.getenv(RUNTIME_ENV, RUNTIME_DEFAULT)
    if runtime_env == RUNTIME_DEFAULT:
        kp_provider = ConfigUtils.get_account_from_env('PROVIDER')
    else:
        kp_provider = generate_key_pair_from_mnemonic(args.provider_mnemonic)
    kp_consumer = ConfigUtils.get_account_from_env('CONSUMER')

    substrate_monitor = SubstrateMonitor(args.node_ws, kp_consumer, 2)
    monitor_thread = Thread(target=substrate_monitor.run_substrate_monitor)
    monitor_thread.start()

    params = parse_redis_config(args.rconfig)
    r = init_redis(params[0], params[1], params[2])
    redis_monitor = RedisMonitor(r, args.node_ws, args.be_url, args.p2p, kp_consumer, 2)
    read_redis_thread = Thread(target=redis_monitor.redis_reader)
    read_redis_thread.start()

    try:
        user_simulation_test(
            args.node_ws,
            args.be_url,
            args.p2p,
            kp_consumer,
            kp_provider,
            args.deposit_token
        )
    except ConnectionRefusedError:
        logging.error('⚠️  No target node running')
        sys.exit()
    monitor_thread.join()
