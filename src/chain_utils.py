import yaml
import logging
import redis
import json
import time

from functools import wraps
from substrateinterface import SubstrateInterface, Keypair, ExtrinsicReceipt
from substrateinterface.utils.ss58 import ss58_encode
from scalecodec.base import RuntimeConfiguration
from scalecodec.type_registry import load_type_registry_preset
from peaq_network_ev_charging_message_format.python import p2p_message_format_pb2 as P2PMessage
from src import did_utils as DIDUtils

RETRY_TIMES = 200
RETRY_PERIOD = 3


def parse_config(path: str) -> Keypair:
    with open(path) as f:
        data = yaml.safe_load(f)
    if 'uri' in data:
        kp = Keypair.create_from_uri(data['uri'])
    elif 'mnemonic' in data:
        kp = Keypair.create_from_mnemonic(data['mnemonic'])
    else:
        raise IOError('Please check the config file, there is no config, uri/mnemonic')
    return kp


def generate_key_pair(logger: logging.Logger) -> Keypair:
    mnemonic = Keypair.generate_mnemonic()
    logger.info(f'generated mnemonic: {mnemonic}')
    kp = Keypair.create_from_mnemonic(mnemonic)
    return kp


def generate_key_pair_from_mnemonic(mnemonic: str) -> Keypair:
    kp = Keypair.create_from_mnemonic(mnemonic)
    return kp


def parse_logger_config(path: str):
    with open(path) as f:
        data = yaml.safe_load(f)
    if 'when' in data:
        when = data['when']
    if 'maxKB' in data:
        maxKB = data['maxKB']
    if 'backups' in data:
        backups = data['backups']
    if 'logPath' in data:
        logPath = data['logPath']
    if 'storeFor' in data:
        storeFor = data['storeFor']
    return [when, maxKB, backups, logPath, storeFor]


def parse_redis_config(path: str):
    with open(path) as f:
        data = yaml.safe_load(f)
    if 'host' in data:
        host = data['host']
    if 'port' in data:
        port = data['port']
    if 'db' in data:
        db = data['db']
    return [host, port, db]


def init_redis(host: str, port: int, db: int):
    return redis.Redis(host=host, port=port, db=db)


def get_substrate_connection(url: str) -> SubstrateInterface:
    # Check the type_registry_preset_dict = load_type_registry_preset(type_registry_name)
    # ~/venv.substrate/lib/python3.6/site-packages/substrateinterface/base.py
    substrate = SubstrateInterface(
        url=url,
    )
    return substrate


def show_extrinsic(receipt: dict, info_type: str, logger: logging.Logger):
    if receipt.is_success:
        logger.info(f'✅ {info_type}, Success: {receipt.get_extrinsic_identifier()}')
    else:
        logger.error(f'⚠️  {info_type}, Extrinsic Failed: {receipt.error_message} {receipt.get_extrinsic_identifier()}')


def calculate_multi_sig(ss58_addrs: str, threshold: int) -> str:
    '''
    https://github.com/polkascan/py-scale-codec/blob/f063cfd47c836895886697e7d7112cbc4e7514b3/test/test_scale_types.py#L383
    '''

    RuntimeConfiguration().update_type_registry(load_type_registry_preset('default'))
    multi_account_id = RuntimeConfiguration().get_decoder_class('MultiAccountId')

    multi_sig_account = multi_account_id.create_from_account_list(ss58_addrs, threshold)
    return ss58_encode(multi_sig_account.value)


def broken_pipe_retry(func):
    @wraps(func)
    def broken_pipe_retry_wrapper(substrate, logger, *args, **kwargs):
        for i in range(RETRY_TIMES):
            try:
                return func(substrate, logger, *args, **kwargs)
            except BrokenPipeError as err:
                logger.error(f'failed to and retry : {err}', exc_info=True)
                time.sleep(RETRY_PERIOD)
                url = substrate.url
                substrate.close()
                substrate = get_substrate_connection(url)
        raise IOError(f'After {RETRY_TIMES} times, still cannot')
    return broken_pipe_retry_wrapper


@broken_pipe_retry
def get_station_balance(substrate: SubstrateInterface, logger: logging.Logger, ss58_addr: str):
    account_info = substrate.query(
        module='System',
        storage_function='Account',
        params=[ss58_addr],
    )

    return account_info['data']['free'].value


@broken_pipe_retry
def send_token_multisig_wallet(substrate: SubstrateInterface, logger: logging.Logger,
                               kp: Keypair, token_num: int, dst_addr: str,
                               other_signatories: [str], threshold: int) -> dict:
    payload = substrate.compose_call(
        call_module='Balances',
        call_function='transfer',
        call_params={
            'dest': dst_addr,
            'value': token_num
        })

    nonce = substrate.get_account_nonce(kp.ss58_address)

    as_multi_call = substrate.compose_call(
        call_module='MultiSig',
        call_function='as_multi',
        call_params={
            'threshold': threshold,
            'other_signatories': other_signatories,
            'maybe_timepoint': None,
            'call': payload.value,
            'store_call': True,
            'max_weight': 1000000000,
        })

    extrinsic = substrate.create_signed_extrinsic(
        call=as_multi_call,
        keypair=kp,
        era={'period': 64},
        nonce=nonce
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    show_extrinsic(receipt, 'as_multi', logger)
    info = receipt.get_extrinsic_identifier().split('-')
    return {
        'tx_hash': receipt.extrinsic_hash,
        'time_point': {'height': int(info[0]), 'index': int(info[1])},
        'call_hash': f'0x{payload.call_hash.hex()}',
    }


def compose_delivery_info(token_num: int, info: dict) -> dict:
    return {
        'token_num': token_num,
        'tx_hash': info['tx_hash'],
        'time_point': info['time_point'],
        'call_hash': info['call_hash'],
    }


@broken_pipe_retry
def send_service_deliver(substrate: SubstrateInterface, logger: logging.Logger, kp: Keypair,
                         user_addr: str, refund_info: dict, spent_info: dict):
    nonce = substrate.get_account_nonce(kp.ss58_address)
    call = substrate.compose_call(
        call_module='Transaction',
        call_function='service_delivered',
        call_params={
            'consumer': user_addr,
            'refund_info': refund_info,
            'spent_info': spent_info,
        })

    extrinsic = substrate.create_signed_extrinsic(
        call=call,
        keypair=kp,
        era={'period': 64},
        nonce=nonce
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    show_extrinsic(receipt, 'service_delivered', logger)


@broken_pipe_retry
def publish_did(substrate: SubstrateInterface, logger: logging.Logger, kp: Keypair, did_path: str) -> ExtrinsicReceipt:
    nonce = substrate.get_account_nonce(kp.ss58_address)

    did_doc = DIDUtils.load_did(did_path)
    if not DIDUtils.is_my_did(did_doc, kp.ss58_address):
        raise IOError(f'the default did {did_doc} does not belong to {kp.ss58_address}')

    call = substrate.compose_call(
        call_module='PeaqDid',
        call_function='add_attribute',
        call_params={
            'did_account': kp.ss58_address,
            'name': DIDUtils.VERSION,
            'value': did_doc.SerializeToString().hex().encode('ascii'),
            'valid_for': DIDUtils.VALID_FOR,
        }
    )

    extrinsic = substrate.create_signed_extrinsic(
        call=call,
        keypair=kp,
        era={'period': 64},
        nonce=nonce
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    return receipt


@broken_pipe_retry
def republish_did(substrate: SubstrateInterface, logger: logging.Logger, kp: Keypair, did_path: str) -> ExtrinsicReceipt:
    nonce = substrate.get_account_nonce(kp.ss58_address)

    did_doc = DIDUtils.load_did(did_path)
    if not DIDUtils.is_my_did(did_doc, kp.ss58_address):
        raise IOError(f'the default did {did_doc} does not belong to {kp.ss58_address}')

    call = substrate.compose_call(
        call_module='PeaqDid',
        call_function='update_attribute',
        call_params={
            'did_account': kp.ss58_address,
            'name': DIDUtils.VERSION,
            'value': did_doc.SerializeToString().hex().encode('ascii'),
            'valid_for': DIDUtils.VALID_FOR,
        }
    )

    extrinsic = substrate.create_signed_extrinsic(
        call=call,
        keypair=kp,
        era={'period': 64},
        nonce=nonce
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    return receipt


@broken_pipe_retry
def read_did(substrate: SubstrateInterface, logger: logging.Logger, kp: Keypair) -> ExtrinsicReceipt:
    nonce = substrate.get_account_nonce(kp.ss58_address)

    call = substrate.compose_call(
        call_module='PeaqDid',
        call_function='read_attribute',
        call_params={
            'did_account': kp.ss58_address,
            'name': DIDUtils.VERSION,
        }
    )

    extrinsic = substrate.create_signed_extrinsic(
        call=call,
        keypair=kp,
        era={'period': 64},
        nonce=nonce
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    return receipt


def decode_chain_event(event: str) -> P2PMessage.Event:
    user_info = P2PMessage.Event()
    user_info.ParseFromString(bytes.fromhex(event))
    return user_info


def create_chain_event_data(data):
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.RECEIVE_CHAIN_EVENT
    chain_event_data = P2PMessage.ChainEventData()
    chain_event_data.event_id = data['event_id']
    chain_event_data.attributes = json.dumps(data['attributes'])
    event.chain_event_data.CopyFrom(chain_event_data)

    return event.SerializeToString().hex()
