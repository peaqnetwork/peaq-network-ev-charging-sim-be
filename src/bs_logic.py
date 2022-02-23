import json
import datetime
from queue import Queue
import logging
import json
import redis

from substrateinterface import Keypair, ExtrinsicReceipt
from substrateinterface.utils.ss58 import ss58_encode
import transitions
from src.utils import calculate_multi_sig, get_substrate_connection, send_token_multisig_wallet, send_service_deliver
from src.utils import compose_delivery_info, publish_did, read_did, get_station_balance
from src.charging_utils import calculate_charging_result


def run_business_logic(ws_url: str, socketio, kp: Keypair, r: redis.Redis, logger: logging.Logger):
    business_logic = BusinessLogic(ws_url, socketio, kp, r, logger)
    business_logic.start()


class BusinessLogic():
    states = ['idle', 'verified', 'charging', 'charged', 'approving']

    def __init__(self, ws_url: str, socketio, kp: Keypair, r: redis.Redis, logger: logging.Logger):
        self._substrate = get_substrate_connection(ws_url)
        self._machine = transitions.Machine(
            model=self,
            states=BusinessLogic.states,
            initial='idle'
        )
        self._kp = kp
        self._multi_threshold = 2

        self._machine.add_transition(trigger='check', source='idle', dest='verified',
                                     conditions=['is_allow_charging'])
        self._machine.add_transition(trigger='start_charging', source='verified', dest='charging')
        self._machine.add_transition(trigger='end_charging', source='charging', dest='charged')
        self._machine.add_transition(trigger='wait_approval', source='charged', dest='approving')
        self._machine.add_transition(trigger='receive_approvals', source='approving', dest='idle')
        self._machine.on_enter_idle('reset')

        self._logger = logger
        self._redis = r
        self._ws_url = ws_url

        self.reset()

    def reset(self):
        self._charging_info = {
            'consumer': '',
            'multisig_pk': '',
            'deposit_token': 0,
            'provider_got': False,
            'provider_got_call_hash': '',
            'consumer_got': False,
            'consumer_got_call_hash': '',
            'spent_token': 0,
            'refund_token': 0,
            'charging_start_time': None,
            'charging_end_time': None,
        }

    def is_all_approvals(self) -> bool:
        return self._charging_info['consumer_got'] and self._charging_info['provider_got']

    def is_allow_charging(self, data: dict) -> bool:
        result = self._substrate.query('System', 'Account', [data['multisig_pk']])
        return result['data']['free'] >= data['deposit_token']

    def is_finish_charging(self, event: dict) -> bool:
        return event['event_id'] == 'UserChargingStop'

    def is_service_requested_event(self, event: dict, interested_addr: str) -> bool:
        return event['event_id'] == 'ServiceRequested' and \
            ss58_encode(event['attributes'][1]) == interested_addr

    def is_consumer_refund_approve_event(self, event: dict, charging_info: str) -> bool:
        if event['event_id'] != 'MultisigExecuted':
            return False
        event_sign_pk = ss58_encode(event['attributes'][0])
        event_call_hash = event['attributes'][-2]
        return charging_info['consumer'] == event_sign_pk and \
            charging_info['consumer_got_call_hash'] == event_call_hash

    def is_consumer_spent_approve_event(self, event: dict, charging_info: dict) -> bool:
        if event['event_id'] != 'MultisigExecuted':
            return False
        event_sign_pk = ss58_encode(event['attributes'][0])
        event_call_hash = event['attributes'][-2]
        return charging_info['consumer'] == event_sign_pk and \
            charging_info['provider_got_call_hash'] == event_call_hash

    def emit_data(self, data_type: str, log_data: dict):
        raw_data = json.dumps(log_data)
        data_to_send = {
            'type': data_type,
            'data': raw_data,
        }
        self._redis.publish("out", json.dumps(data_to_send).encode('ascii'))
        self._logger.info(f'{data_type}: {raw_data}')

    def emit_log(self, log_data: dict):
        self.emit_data('log', log_data)

    def emit_deposit_verified(self, data: dict):
        named_data = {'event' : 'DepositVerified', 'state': self.state}
        named_data.update(data)
        self.emit_data('event', named_data)

    def emit_service_requested(self, data: dict):
        named_data = {'event' : 'ServiceRequested', 'state': self.state}
        named_data.update(data)
        self.emit_data('event', named_data)

    def emit_service_delivered(self, data: dict):
        named_data = {'event' : 'ServiceDelivered', 'state': self.state}
        named_data.update(data)
        self.emit_data('event', named_data)

    def emit_balances_transferd(self, data: dict):
        named_data = {'event' : 'BalancesTransfered', 'state': self.state}
        named_data.update(data)
        self.emit_data('event', named_data)

    def start(self):
        r = None
        try:
            self._logger.info('reading did...')
            r = read_did(self._substrate, self._kp, self._logger)
            if r.is_success:
                f = r.triggered_events[0].value['attributes']['value']
                self._logger.info(f'successfully read did: {json.loads(f)}')
        except Exception as err:
            self._logger.error(f'failed to read did: {err}')

        if not r == None and not r.is_success:
            try:
                self._logger.info('publishing did...')
                r = publish_did(self._substrate, self._kp, self._logger)
            except Exception as err:
                self._logger.error(f'failed to publish did: {err}')


        subcriber = self._redis.pubsub()
        subcriber.subscribe("in")

        while True:
            event_data = subcriber.get_message(True, timeout=30000.0)

            if event_data == None:
                continue
            else:
                event = json.loads(event_data['data'])

            if event['event_id'] == 'ExtrinsicSuccess' or event['event_id'] == 'NewBaseFeePerGas':
                continue

            if event['event_id'] == 'GetBalance':
                try:
                    balance = get_station_balance(self._substrate, self._kp, self._logger)
                    self.emit_data("GetBalanceResponse", {'data': balance, 'success' : True})
                except Exception as e:
                    self._logger.error(f'exception happen when acquiring balance: {e}')
                    self.emit_data("GetBalanceResponse", {'data': 0, 'success' : False})

            if event['event_id'] == 'GetPK':
                self.emit_data("GetPKResponse", {'data': self._kp.ss58_address, 'success' : True})

            if event['event_id'] == 'PublishDID':
                try:
                    receipt = publish_did(self._substrate, self._kp, self._logger)
                    if receipt.is_success:
                        self.emit_data("PublishDIDResponse", {'data': self._kp.ss58_address, 'success' : True})
                    else:
                        if not r.error_message == None:
                            self.emit_data("GetPKResponse", {"message":  receipt.error_message, 'success' : False})
                        self.emit_data("PublishDIDResponse", {"message": "failed to publish did for unknown reason", 'success' : False})
                except Exception as err:
                    self._logger.error(f'error during publishing occurred: {err}')
                    self.emit_data("PublishDIDResponse", {"message": "something unexpected happen", 'success' : False})

            if event['event_id'] == 'Reconnect':
                self.reconnect()

            if self.is_service_requested_event(event, self._kp.ss58_address):
                if not self.is_idle():
                    self._logger.error(f'received "service requested" event while not in state "idle" event: {event["event_id"]}: {event["attributes"]}')
                    continue

                consumer = ss58_encode(event['attributes'][0])
                self._charging_info.update({
                    'consumer': consumer,
                    'deposit_token': event['attributes'][2],
                    'multisig_pk': calculate_multi_sig(
                        [consumer, self._kp.ss58_address],
                        self._multi_threshold),
                })

                # [TODO] We should change the API type and the naming...
                self.emit_service_requested({
                    'provider': self._kp.ss58_address,
                    'consumer': self._charging_info['consumer'],
                    'token_deposited': self._charging_info['deposit_token'],
                })
                self.emit_log({'state': self.state, 'data': 'ServiceRequested received'})
                data_to_send = {
                    'type': "log",
                    'data': "ServiceRequested received",
                }
                self._redis.publish("out", json.dumps(data_to_send).encode('ascii'))

                self.check(self._charging_info)
                if self.is_idle():
                    self.emit_log({'state': self.state, 'data': 'Check refuse'})
                    # [TODO] We should change the API type and the naming...
                    self.emit_deposit_verified({
                        'consumer': self._charging_info['consumer'],
                        'token_deposited': self._charging_info['deposit_token'],
                        'success': False,
                    })
                    continue
                # [TODO] We should change the API type and the naming...
                self.emit_deposit_verified({
                    'consumer': self._charging_info['consumer'],
                    'token_deposited': self._charging_info['deposit_token'],
                    'success': True,
                })
                self.emit_log({'state': self.state, 'data': 'Check verified'})

                self._charging_info['charging_start_time'] = datetime.datetime.now()
                self.start_charging()
                self._logger.info('started charging')
                self.emit_log({'state': self.state, 'data': 'Charging start'})

            elif self.is_finish_charging(event):
                if not self.is_charging():
                    self._logger.error(f'received "finished charging" event while not in state "charging" event: {event["event_id"]}: {event["data"]}')
                    continue

                self.end_charging()
                self._logger.info('ended charging')
                self.emit_log({'state': self.state, 'data': 'Charging end', 'info': event['data']})

                self._charging_info['charging_end_time'] = datetime.datetime.now()
                charging_result = calculate_charging_result(
                    self._charging_info['charging_start_time'],
                    self._charging_info['charging_end_time'],
                    self._charging_info['deposit_token']
                )
                spent_token = charging_result['spent_token']
                refund_token = charging_result['refund_token']
                charging_period = charging_result['charging_period']
                energy_consumption = charging_result['energy_consumption']

                self._charging_info.update({
                    'spent_token': spent_token,
                    'refund_token': refund_token
                })
                self.emit_log({
                    'state': self.state,
                    'data': '{}, {}'.format(
                        f'spent: {spent_token}, refund: {refund_token}',
                        f'charging period: {charging_period}, energy consumption: {energy_consumption}')
                })

                # Send the spent + delivier
                spent_info = send_token_multisig_wallet(
                    self._substrate, self._kp,
                    spent_token, self._kp.ss58_address,
                    [self._charging_info['consumer']], self._multi_threshold, self._logger)
                self.emit_log({'state': self.state, 'data': 'Charging sends spent for multisig'})

                # Send the refund + delivier
                refund_info = send_token_multisig_wallet(
                    self._substrate, self._kp,
                    refund_token, self._charging_info['consumer'],
                    [self._charging_info['consumer']], self._multi_threshold, self._logger)
                self.emit_log({'state': self.state, 'data': 'Charging sends refund for multisig'})

                self._charging_info.update({
                    'provider_got_call_hash': spent_info['call_hash'],
                    'consumer_got_call_hash': refund_info['call_hash']
                })

                send_service_deliver(
                    self._substrate, self._kp, self._charging_info['consumer'],
                    compose_delivery_info(refund_token, refund_info),
                    compose_delivery_info(spent_token, spent_info), self._logger)
                self.emit_service_delivered({
                    'provider': self._kp.ss58_address,
                    'consumer': self._charging_info['consumer'],
                    'refund_info': compose_delivery_info(refund_token, refund_info),
                    'spent_info': compose_delivery_info(spent_token, spent_info),
                })

                self.wait_approval()
                self.emit_log({'state': self.state, 'data': 'User\'s approval wait'})

            elif self.is_consumer_refund_approve_event(event, self._charging_info):
                if not self.is_approving():
                    self._logger.error(f'received "approve refund event" event while not in state "approving" event: {event["event_id"]}: {event["attributes"]}')
                    continue

                if 'Ok' not in event['attributes'][-1]:
                    self.emit_log({
                        'desc': 'the consumer refund approval has an error, please check',
                        'time_point': event['attributes'][1],
                        'error': event['attributes'][-1]
                    })
                    continue
                self._charging_info['consumer_got'] = True
                self.emit_balances_transferd({
                    'from': self._charging_info['multisig_pk'],
                    'to': self._charging_info['consumer'],
                    'value': self._charging_info['refund_token'],
                })
                self.emit_log({'state': self.state, 'data': 'receive multisig -> conumser, approval'})

                if self.is_all_approvals():
                    self.receive_approvals()
                    self.emit_log({'state': self.state, 'data': 'charging process finish!'})

            elif self.is_consumer_spent_approve_event(event, self._charging_info):
                if not self.is_approving():
                    self._logger.error(f'received "consumer spent event" event while not in state "approving" event: {event["event_id"]}: {event["attributes"]}')
                    continue

                if 'Ok' not in event['attributes'][-1]:
                    self.emit_log({
                        'desc': 'the consumer spent approval has an error, please check',
                        'time_point': event['attributes'][1],
                        'error': event['attributes'][-1]
                    })
                    continue
                self._charging_info['provider_got'] = True
                self.emit_balances_transferd({
                    'from': self._charging_info['multisig_pk'],
                    'to': self._kp.ss58_address,
                    'value': self._charging_info['spent_token'],
                })
                self.emit_log({'state': self.state, 'data': 'receive multisig -> provider, approval'})

                if self.is_all_approvals():
                    self.receive_approvals()
                    self.emit_log({'state': self.state, 'data': 'charging process finish!'})

            self.emit_log({'state': self.state, 'data': f'{event["event_id"]}'})
            self._logger.info(f'Event: {event["event_id"]}: {event["attributes"]}')
    def reconnect(self):
        try:
            self._substrate.close()
            self._substrate = get_substrate_connection(self._ws_url)
            self.emit_data('ReconnectResponse' ,{'message': 'Successfully reconnected', 'success' : True})
        except Exception as err:
            self.emit_data('ReconnectResponse' ,{'message': f'Reconnection failed: {err}', 'success' : False})
