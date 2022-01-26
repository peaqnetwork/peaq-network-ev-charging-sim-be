import logging
import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from substrateinterface import SubstrateInterface, Keypair
from src import utils

TOKEN_NUM_BASE = 10 ** 19


def fund(substrate: SubstrateInterface, kp_dst: Keypair, kp_sudo: Keypair, token_num: int):
    payload = substrate.compose_call(
        call_module='Balances',
        call_function='set_balance',
        call_params={
            'who': kp_dst.ss58_address,
            'new_free': token_num * TOKEN_NUM_BASE,
            'new_reserved': 0
        }
    )

    call = substrate.compose_call(
        call_module='Sudo',
        call_function='sudo',
        call_params={
            'call': payload.value,
        }
    )

    extrinsic = substrate.create_signed_extrinsic(
        call=call,
        keypair=kp_sudo
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    utils.show_extrinsic(receipt, 'fund', logging.getLogger('logger'))


def deposit_money_to_multsig_wallet(substrate: SubstrateInterface, kp_consumer: Keypair,
                                    kp_provider: Keypair, token_num: int):
    logging.info('----- Consumer deposit money to multisig wallet')
    threshold = 2
    signators = [kp_consumer.ss58_address, kp_provider.ss58_address]
    multi_sig_addr = utils.calculate_multi_sig(signators, threshold)
    call = substrate.compose_call(
        call_module='Balances',
        call_function='transfer',
        call_params={
            'dest': multi_sig_addr,
            'value': token_num * TOKEN_NUM_BASE
        })

    nonce = substrate.get_account_nonce(kp_consumer.ss58_address)
    extrinsic = substrate.create_signed_extrinsic(
        call=call,
        keypair=kp_consumer,
        era={'period': 64},
        nonce=nonce
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    utils.show_extrinsic(receipt, 'transfer', logging.getLogger('logger'))


def send_service_request(substrate: SubstrateInterface, kp_consumer: Keypair,
                         kp_provider: Keypair, token_num: int):
    logging.info('----- Consumer sends the serviice requested to peaq-transaction')
    nonce = substrate.get_account_nonce(kp_consumer.ss58_address)
    call = substrate.compose_call(
        call_module='Transaction',
        call_function='service_requested',
        call_params={
            'provider': kp_provider.ss58_address,
            'token_deposited': token_num * TOKEN_NUM_BASE
        })

    extrinsic = substrate.create_signed_extrinsic(
        call=call,
        keypair=kp_consumer,
        era={'period': 64},
        nonce=nonce
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    utils.show_extrinsic(receipt, 'service_requested', logging.getLogger('logger'))


def send_spent_token_from_multisig_wallet(
        substrate: SubstrateInterface, kp_consumer: Keypair,
        kp_provider: Keypair, token_num: int, threshold: int):

    logging.info('----- Provider asks the spent token')
    payload = substrate.compose_call(
        call_module='Balances',
        call_function='transfer',
        call_params={
            'dest': kp_provider.ss58_address,
            'value': token_num * TOKEN_NUM_BASE
        })

    nonce = substrate.get_account_nonce(kp_provider.ss58_address)

    as_multi_call = substrate.compose_call(
        call_module='MultiSig',
        call_function='as_multi',
        call_params={
            'threshold': threshold,
            'other_signatories': [kp_consumer.ss58_address],
            'maybe_timepoint': None,
            'call': str(payload.data),
            'store_call': True,
            'max_weight': 1000000000,
        })

    extrinsic = substrate.create_signed_extrinsic(
        call=as_multi_call,
        keypair=kp_provider,
        era={'period': 64},
        nonce=nonce
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    utils.show_extrinsic(receipt, 'as_multi', logging.getLogger('logger'))
    info = receipt.get_extrinsic_identifier().split('-')
    return {
        'tx_hash': receipt.extrinsic_hash,
        'timepoint': {'height': int(info[0]), 'index': int(info[1])},
        'call_hash': f'0x{payload.call_hash.hex()}',
    }


def send_refund_token_from_multisig_wallet(
        substrate: SubstrateInterface, kp_consumer: Keypair,
        kp_provider: Keypair, token_num: int, threshold: int):
    logging.info('----- Provider asks the refund token')
    payload = substrate.compose_call(
        call_module='Balances',
        call_function='transfer',
        call_params={
            'dest': kp_consumer.ss58_address,
            'value': token_num * TOKEN_NUM_BASE
        })

    nonce = substrate.get_account_nonce(kp_provider.ss58_address)

    as_multi_call = substrate.compose_call(
        call_module='MultiSig',
        call_function='as_multi',
        call_params={
            'threshold': threshold,
            'other_signatories': [kp_consumer.ss58_address],
            'maybe_timepoint': None,
            'call': str(payload.data),
            'store_call': True,
            'max_weight': 1000000000,
        })

    extrinsic = substrate.create_signed_extrinsic(
        call=as_multi_call,
        keypair=kp_provider,
        era={'period': 64},
        nonce=nonce
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    utils.show_extrinsic(receipt, 'as_multi', logging.getLogger('logger'))
    info = receipt.get_extrinsic_identifier().split('-')
    return {
        'tx_hash': receipt.extrinsic_hash,
        'timepoint': {'height': int(info[0]), 'index': int(info[1])},
        'call_hash': f'0x{payload.call_hash.hex()}'
    }


def approve_token(substrate: SubstrateInterface, kp_sign: Keypair,
                  other_signatories: [str], threshold: int, info: dict):
    nonce = substrate.get_account_nonce(kp_sign.ss58_address)

    as_multi_call = substrate.compose_call(
        call_module='MultiSig',
        call_function='approve_as_multi',
        call_params={
            'threshold': threshold,
            'other_signatories': other_signatories,
            'maybe_timepoint': info['timepoint'],
            'call_hash': info['call_hash'],
            'max_weight': 1000000000,
        })

    extrinsic = substrate.create_signed_extrinsic(
        call=as_multi_call,
        keypair=kp_sign,
        era={'period': 64},
        nonce=nonce
    )

    receipt = substrate.submit_extrinsic(extrinsic, wait_for_inclusion=True)
    utils.show_extrinsic(receipt, 'approve_as_multi', logging.getLogger('logger'))
