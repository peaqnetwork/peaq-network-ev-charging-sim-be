import json
import logging
import redis

from flask_socketio import SocketIO
from flask import Flask, render_template
from flask_cors import CORS

from substrateinterface import Keypair


def create_app(secret: str, debugging: bool, node_addr: str, kp: Keypair, r: redis.Redis, logger: logging.Logger) -> (Flask, SocketIO):
    app = Flask(__name__)
    # For now, we allow CORS for all domains on all routes
    CORS(app)
    app.config['SECRET_KEY'] = secret
    app.config['DEBUG'] = debugging

    socketio = SocketIO(app, async_mode=None, logger=True, engineio_logger=True, cors_allowed_origins='*')

    @app.route('/')
    def index():
        return render_template('index.html')

    @socketio.on('connect')
    def connect():
        logger.info('Client connected')

    @socketio.on('disconnect')
    def disonnect():
        logger.info('Client disconnect')

    @socketio.on('json')
    def handle_requests(data):
        m = json.loads(data)
        data_to_send = {
            'event_id': m['type'],
            'data': m['data'],
            'attributes': m['data'],
        }
        r.publish("in", json.dumps(data_to_send).encode('ascii'))

    return app, socketio


def redis_reader(sock: SocketIO, r: redis.Redis):
    subcriber = r.pubsub()
    subcriber.subscribe("out")

    while True:
        event_data = subcriber.get_message(True, timeout=30000.0)

        if not event_data:
            continue
        else:
            m = json.loads(event_data['data'])
            sock.emit(m['type'], m['data'])
