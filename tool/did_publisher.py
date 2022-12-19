import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import logging
import argparse
from src.chain_utils import republish_did, get_substrate_connection
from src.config_utils import get_account_from_env


def parse_arguement():
    parser = argparse.ArgumentParser()
    parser.add_argument('--did_path', help='did file path',
                        type=str,
                        default='etc/did_doc.json')
    parser.add_argument('--node_ws', help="peaq node's url",
                        type=str, default='ws://127.0.0.1:9944')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_arguement()

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('')

    kp_provider = get_account_from_env('PROVIDER')
    try:
        substrate_conn = get_substrate_connection(args.node_ws)
    except ConnectionRefusedError:
        logger.error("⚠️  No target node running")
        sys.exit()

    ret = republish_did(substrate_conn,
                        logger, kp_provider, args.did_path)

    if ret.is_success:
        logger.info(f'✅ DID {args.did_path} is already published.')
    else:
        logger.info("⚠️  please check again")
