import sys
from queue import Queue
from threading import Thread
import argparse
import logging
import os

import eventlet
from substrateinterface import Keypair
from src import app
from src.bs_logic import run_business_logic
from src.substrate_monitor import run_substrate_monitor
from src.utils import get_substrate_connection, parse_config, parse_logger_config, generate_key_pair
from flask_socketio import SocketIO
from src.logger import init_logger

eventlet.monkey_patch()


__author__ = 'peaq'

RUNTIME_ENV = 'RUNTIME_ENV'
RUNTIME_DEFAULT = 'dev'

def create_main_logic(ws_url: str, socketio: SocketIO, q: Queue, kp_provider: Keypair, logger: logging.Logger):
    monitor_thread = Thread(target=run_substrate_monitor, args=(ws_url, q,))
    business_logic_thread = Thread(target=run_business_logic,
                                   args=(ws_url, q, socketio, kp_provider,logger,))
    monitor_thread.start()
    business_logic_thread.start()

    monitor_thread.join()
    business_logic_thread.join()


def parse_arguement():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', help='config yaml file',
                        type=str, default='etc/config.yaml')
    parser.add_argument('--url', help='backend service url',
                        type=str, default='127.0.0.1')
    parser.add_argument('--port', help='backend service port',
                        type=str, default='25566')
    parser.add_argument('--node_ws', help="peaq node's url",
                        type=str, default='ws://127.0.0.1:9944')
    parser.add_argument('--lconfig', help='logger config yaml file',
                        type=str, default='etc/logger.yaml')
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_arguement()

    params = parse_logger_config(args.lconfig)
    logger = init_logger(params[0], params[1], params[2], params[3], params[4])

    # Test whether the node ws is available
    try:
        get_substrate_connection(args.node_ws)
    except ConnectionRefusedError:
        logger.error("⚠️  No target node running")
        sys.exit()

    runtime_env = os.getenv(RUNTIME_ENV, RUNTIME_DEFAULT)
    if (runtime_env == RUNTIME_DEFAULT):
        kp_provider = parse_config(args.config)
    else:
        kp_provider = generate_key_pair(logger)

    q = Queue()
    be, socketio = app.create_app('secret', True, q, args.node_ws, kp_provider, logger)
    socketio.start_background_task(create_main_logic, args.node_ws, socketio, q, kp_provider, logger)
    socketio.run(be, debug=False, host=args.url, port=args.port)
