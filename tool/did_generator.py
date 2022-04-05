import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import argparse
from substrateinterface import Keypair, KeypairType
from src import did_utils as DIDUtils
from google.protobuf.json_format import MessageToJson

# Bob/stash
DEFAULT_PROVIDER_SEED = {
    'sr25519': '0x1a7d114100653850c65edecda8a9b2b4dd65d900edef8e70b1a6ecdcda967056',
    'ed25519': '0x71b28bbd45fe04f07200190180f14ba0fe3dd903eb70b6a34ee16f9f463cfd10',
}


def parse_arguement():
    parser = argparse.ArgumentParser()
    parser.add_argument('--issuer_mnemonic', help='Keypair to sign the did document',
                        type=str, required=True)
    parser.add_argument('--provider_mnemonic', help='Keypair for the did document',
                        type=str, default='')
    parser.add_argument('--p2p_domain', help='add the p2p domain',
                        type=str, default='18.192.206.66')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_arguement()
    if not args.provider_mnemonic:
        sr25519_provider_kp = Keypair.create_from_seed(
            DEFAULT_PROVIDER_SEED['sr25519'],
            crypto_type=KeypairType.SR25519)

        ed25519_provider_kp = Keypair.create_from_seed(
            DEFAULT_PROVIDER_SEED['ed25519'],
            crypto_type=KeypairType.ED25519)
    else:
        sr25519_provider_kp = Keypair.create_from_mnemonic(
            args.provider_mnemonic,
            crypto_type=KeypairType.SR25519)
        ed25519_provider_kp = Keypair.create_from_mnemonic(
            args.provider_mnemonic,
            crypto_type=KeypairType.ED25519)

    issuer_kp = Keypair.create_from_mnemonic(args.issuer_mnemonic)
    did = DIDUtils.compose_did(sr25519_provider_kp, ed25519_provider_kp,
                               issuer_kp, args.p2p_domain)
    print(MessageToJson(did))
