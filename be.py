import sys
from threading import Thread
import argparse
import logging
import os
import redis

import eventlet
from src import app
from src.bs_logic import run_business_logic
from src.substrate_monitor import run_substrate_monitor
from src.chain_utils import get_substrate_connection, parse_logger_config, generate_key_pair, parse_redis_config, init_redis
from flask_socketio import SocketIO
from src.logger import init_logger
from src import thread_utils
from src import charging_status_monitor
from src import config_utils as ConfigUtils

eventlet.monkey_patch()


__author__ = 'peaq'

RUNTIME_ENV = 'RUNTIME_ENV'
RUNTIME_DEFAULT = 'dev'


def create_main_logic(socketio: SocketIO, r: redis.Redis, logger: logging.Logger, config: dict, did_path: str):
    thread_utils.install(logger)

    monitor_thread = Thread(target=run_substrate_monitor, args=(config['node_ws'], r))
    business_logic_thread = Thread(target=run_business_logic,
                                   args=(r, logger, config, did_path))
    read_redis_thread = Thread(target=app.redis_reader, args=(socketio, r))
    charging_monitor_thread = Thread(target=charging_status_monitor.run,
                                     args=(r, logger))

    monitor_thread.start()
    business_logic_thread.start()
    read_redis_thread.start()
    charging_monitor_thread.start()

    monitor_thread.join()
    business_logic_thread.join()
    read_redis_thread.join()
    charging_monitor_thread.join()


def parse_arguement():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', help='backend service url',
                        type=str, default='127.0.0.1')
    parser.add_argument('--port', help='backend service port',
                        type=str, default='25566')
    parser.add_argument('--node_ws', help="peaq node's url",
                        type=str, default='ws://127.0.0.1:9944')
    parser.add_argument('--charging_time', help='stop the charging process after this seconds',
                        type=int, default=300)
    parser.add_argument('--lconfig', help='logger config yaml file',
                        type=str, default='etc/logger.yaml')
    parser.add_argument('--rconfig', help='redis config yaml file',
                        type=str, default='etc/redis.yaml')
    parser.add_argument('--did_path', help='did document path',
                        type=str, default='etc/did_doc.json')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_arguement()

    params = parse_logger_config(args.lconfig)
    logger = init_logger(params[0], params[1], params[2], params[3], params[4])

    params = parse_redis_config(args.rconfig)
    redis = init_redis(params[0], params[1], params[2])

    # Test whether the node ws is available
    try:
        get_substrate_connection(args.node_ws).close()
    except ConnectionRefusedError:
        logger.error("⚠️  No target node running")
        sys.exit()

    runtime_env = os.getenv(RUNTIME_ENV, RUNTIME_DEFAULT)
    if runtime_env == RUNTIME_DEFAULT:
        # Check PROVIDER_URI and PROVIDER_MNEMONIC
        kp_provider = ConfigUtils.get_account_from_env('PROVIDER')
    else:
        kp_provider = generate_key_pair(logger)

    be, socketio = app.create_app('secret', True, args.node_ws, kp_provider, redis, logger)
    socketio.start_background_task(
        create_main_logic, socketio, redis, logger, {
            'node_ws': args.node_ws,
            'charging_time': args.charging_time,
            'kp_provider': kp_provider
        }, args.did_path)
    socketio.run(be, debug=False, host=args.url, port=args.port)
