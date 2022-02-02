import json
import logging

from flask_socketio import SocketIO
from flask import Flask, render_template, request, Response
from flask_cors import CORS
from queue import Queue

from src.utils import get_substrate_connection, publish_did, get_station_balance, get_substrate_connection
from substrateinterface import Keypair, SubstrateInterface

def create_app(secret: str, debugging: bool, q: Queue, node_addr: str, kp: Keypair, logger: logging.Logger)  -> (Flask, SocketIO):
    app = Flask(__name__)
    # For now, we allow CORS for all domains on all routes
    CORS(app)
    app.config['SECRET_KEY'] = secret
    app.config['DEBUG'] = debugging

    socketio = SocketIO(app, async_mode=None, logger=True, engineio_logger=True, cors_allowed_origins='*')

    @app.route('/')
    def index():
        return render_template('index.html', async_mode=socketio.async_mode)

    @app.route('/pk', methods=['GET'])
    def get_pk():
        return kp.ss58_address

    @app.route('/end_charging', methods=['POST'])
    def end_charging():
        data = json.loads(request.data.decode('ascii'))
        q.put({
            'event_id': 'UserChargingStop',
            'attributes': data,
            'raw': data
        })
        return 'ok'

    @app.route('/publish_did', methods=['POST'])
    def publish():
        logger.info('publishing did')
        si: SubstrateInterface
        try:
            with get_substrate_connection(node_addr) as si:
                r = publish_did(si, kp, logger)
                if r.is_success:
                    return Response('{"message": success}', status=201, mimetype='application/json')
                else:
                    if not r.error_message == None:
                        return Response(f'{{"message": {r.error_message}}}', status=200, mimetype='application/json')
                    return Response(f'{{"message": failed to publish did for unknown reason}}', status=200, mimetype='application/json')
        except Exception as err:
            logger.error(f'error during publishing occurred: {err}')
            return Response('{"message": "something unexpected happen"}', status=200, mimetype='application/json')

    @app.route('/balance', methods=['GET'])
    def balance():
        si: SubstrateInterface
        try:
            with get_substrate_connection(node_addr) as si:
                b = get_station_balance(si, kp, logger)
                return Response(f'{{"balance": {b}}}', status=200, mimetype='application/json')
        except Exception as err:
            return Response('{"message": something bad happen}', status=200, mimetype='application/json')

    @socketio.on('connect')
    def connect():
        logger.info('Client connected')

    @socketio.on('disconnect')
    def disonnect():
        logger.info('Client disconnect')

    # socketio won't receive the msg from the client
    return app, socketio
