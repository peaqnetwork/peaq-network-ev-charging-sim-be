import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import logging
import argparse
from src.chain_utils import read_did, get_substrate_connection
from src.config_utils import get_account_from_env
from src import did_utils as DIDUtils


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

    r = read_did(substrate_conn, logger, kp_provider)
    if r.is_success:
        event = [_.value for _ in r.triggered_events
                 if _.value['event_id'] == 'AttributeRead'][0]["attributes"]
        did_doc = DIDUtils.decode_did_event(event)
        logger.info(f'successfully read did: {did_doc}')
