import time
import json
from threading import Thread
import argparse
import logging

import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from substrateinterface import Keypair
from utils import fund, send_service_request
from utils import deposit_money_to_multsig_wallet
from utils import approve_token
from src.utils import parse_config, get_substrate_connection, generate_key_pair_from_mnemonic
import socketio

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
    parser.add_argument('--sudo_config', help='sudo config yaml file',
                        type=str, default='tool/sudo.config.yaml')
    parser.add_argument('--node_ws', help="peaq node's url",
                        type=str, default='ws://127.0.0.1:9944')
    parser.add_argument('--provider_mnemonic', help="will be used only if on preview branch",
                        type=str, default='ws://127.0.0.1:9944')
    return parser.parse_args()


def user_simulation_test(ws_url: str, kp_consumer: Keypair,
                         kp_provider: Keypair, kp_sudo: Keypair,
                         token_deposit: int):
    with get_substrate_connection(ws_url) as substrate:
        # Fund first
        fund(substrate, kp_consumer, kp_sudo, 500)
        fund(substrate, kp_provider, kp_sudo, 500)

        deposit_money_to_multsig_wallet(substrate, kp_consumer, kp_provider, token_deposit)
        send_service_request(substrate, kp_consumer, kp_provider, token_deposit)
        logging.info('---- charging start and wait')


class SubstrateMonitor():
    def __init__(self, ws_url: str, kp_consumer: Keypair, threshold: int):
        self._threshold = threshold
        self._kp_consumer = kp_consumer
        self._substrate = get_substrate_connection(ws_url)

    def __del__(self):
        self._substrate.close()

    def subscription_event_handler(self, objs, update_nr, subscription_id):
        for obj in objs:
            event = obj['event'].value
            if event['event_id'] == 'ExtrinsicSuccess':
                continue
            if event['event_id'] == 'ServiceRequested':
                time.sleep(10)
                logging.info('✅ ---- send request !!')
                sio = socketio.Client()
                sio.connect('http://127.0.0.1:25566')
                sio.emit('json', json.dumps({
                    'type': 'UserChargingStop',
                    'data': True
                }))
            if event['event_id'] == 'ServiceDelivered':
                provider_addr = event['attributes'][0]
                refund_info = {
                    'token_num': event['attributes'][2]['token_num'],
                    'timepoint': event['attributes'][2]['time_point'],
                    'call_hash': event['attributes'][2]['call_hash']
                }
                spent_info = {
                    'token_num': event['attributes'][3]['token_num'],
                    'timepoint': event['attributes'][3]['time_point'],
                    'call_hash': event['attributes'][3]['call_hash']
                }
                approve_token(
                    self._substrate, self._kp_consumer,
                    [provider_addr], self._threshold, spent_info)
                approve_token(
                    self._substrate, self._kp_consumer,
                    [provider_addr], self._threshold, refund_info)
            logging.info(f"{event['event_id']}: {event['attributes']}")
            continue

    def run_substrate_monitor(self):
        self._substrate.query("System", "Events", None,
                              subscription_handler=self.subscription_event_handler)


if __name__ == '__main__':
    args = parse_arguement()
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s : %(message)s')

    # Test whether the node ws is available
    try:
        get_substrate_connection(args.node_ws).close()
    except ConnectionRefusedError:
        logging.error("⚠️  No target node running")
        sys.exit()

    kp_sudo = parse_config(args.sudo_config)
    runtime_env = os.getenv(RUNTIME_ENV, RUNTIME_DEFAULT)
    if (runtime_env == RUNTIME_DEFAULT):
        kp_provider = parse_config(args.provider_config)
    else:
        kp_provider = generate_key_pair_from_mnemonic(args.provider_mnemonic)
    kp_consumer = parse_config(args.consumer_config)

    monitor = SubstrateMonitor(args.node_ws, kp_consumer, 2)
    monitor_thread = Thread(target=monitor.run_substrate_monitor)
    monitor_thread.start()

    user_simulation_test(args.node_ws, kp_consumer, kp_provider, kp_sudo, args.deposit_token)
    monitor_thread.join()
