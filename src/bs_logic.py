import json
import datetime
import logging
import redis

from substrateinterface import Keypair
from substrateinterface.utils.ss58 import ss58_encode
import transitions
from src.chain_utils import calculate_multi_sig, send_token_multisig_wallet
from src.chain_utils import compose_delivery_info, publish_did, read_did, republish_did, get_station_balance
from src import chain_utils as ChainUtils
from src import p2p_utils as P2PUtils
from src import user_utils as UserUtils
from src import charging_utils as CharginUtils
from peaq_network_ev_charging_message_format.python import p2p_message_format_pb2 as P2PMessage
from src.constants import REDIS_OUT, REDIS_IN


def run_business_logic(ws_url: str, kp: Keypair, r: redis.Redis, logger: logging.Logger):
    business_logic = BusinessLogic(ws_url, kp, r, logger)
    business_logic.start()


class BusinessLogic():
    states = ['idle', 'verified', 'charging', 'charged', 'approving']

    def __init__(self, ws_url: str, kp: Keypair, r: redis.Redis, logger: logging.Logger):
        self._substrate = ChainUtils.get_substrate_connection(ws_url)
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

    def __del__(self):
        if self._substrate:
            self._substrate.close()

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

    def is_service_requested_event(self, p2p_event: P2PMessage.Event, interested_addr: str) -> bool:
        return P2PUtils.is_service_requested_event(p2p_event) and \
            p2p_event.service_requested_data.provider == interested_addr

    def is_consumer_refund_approve_event(self, event: P2PMessage.Event, charging_info: str) -> bool:
        if event.event_id != P2PMessage.RECEIVE_CHAIN_EVENT or \
           event.chain_event_data.event_id != 'MultisigExecuted':
            return False
        attributes = json.loads(event.chain_event_data.attributes)
        event_sign_pk = ss58_encode(attributes[0])
        event_call_hash = attributes[-2]
        return charging_info['consumer'] == event_sign_pk and \
            charging_info['consumer_got_call_hash'] == event_call_hash

    def is_consumer_spent_approve_event(self, event: P2PMessage.Event, charging_info: dict) -> bool:
        if event.event_id != P2PMessage.RECEIVE_CHAIN_EVENT or \
           event.chain_event_data.event_id != 'MultisigExecuted':
            return False
        attributes = json.loads(event.chain_event_data.attributes)
        event_sign_pk = ss58_encode(attributes[0])
        event_call_hash = attributes[-2]
        return charging_info['consumer'] == event_sign_pk and \
            charging_info['provider_got_call_hash'] == event_call_hash

    def emit_out(self, data: dict):
        self._redis.publish(REDIS_OUT, data)
        self._logger.info(f'{data}')

    def emit_log(self, log_data: dict):
        data_to_send = UserUtils.create_log_data(log_data)
        self._redis.publish(REDIS_OUT, data_to_send)
        self._logger.info(f'log: {log_data}')

    def emit_event(self, event_data: dict):
        data_to_send = UserUtils.create_event_data(event_data)
        self._redis.publish(REDIS_OUT, data_to_send)
        self._logger.info(f'event: {event_data}')

    def emit_deposit_verified(self, data: dict):
        named_data = {'event': 'DepositVerified', 'state': self.state}
        named_data.update(data)
        self.emit_event(named_data)

    def emit_service_requested(self, data: dict):
        named_data = {'event': 'ServiceRequested', 'state': self.state}
        named_data.update(data)
        self.emit_event(named_data)

    def emit_service_delivered(self, data: dict):
        named_data = {'event': 'ServiceDelivered', 'state': self.state}
        named_data.update(data)
        self.emit_event(named_data)

    def emit_balances_transferd(self, data: dict):
        named_data = {'event': 'BalancesTransfered', 'state': self.state}
        named_data.update(data)
        self.emit_event(named_data)

    def republish_did(self):
        did_exist = False
        try:
            self._logger.info('reading did...')
            r = read_did(self._substrate, self._kp, self._logger)
            if r.is_success and \
               len([_ for _ in r.triggered_events if _.value['event_id'] == 'AttributeRead']):
                did_exist = True
        except Exception as err:
            self._logger.error(f'failed to read did: {err}')

        try:
            if did_exist:
                receipt = republish_did(self._substrate, self._kp, self._logger)
            else:
                receipt = publish_did(self._substrate, self._kp, self._logger)

            if receipt.is_success:
                data = UserUtils.create_republish_did_ack(
                    self._kp.ss58_address,
                    True,
                    '')
                self.emit_out(data)
            else:
                if r.error_message is not None:
                    data = UserUtils.create_republish_did_ack(
                        self._kp.ss58_address,
                        False,
                        receipt.error_message)
                    self.emit_out(data)
                else:
                    data = UserUtils.create_republish_did_ack(
                        self._kp.ss58_address,
                        False,
                        'failed to publish did for unknown reason')
                    self.emit_out(data)
        except Exception as err:
            self._logger.error(f'error during publishing occurred: {err}')
            data = UserUtils.create_republish_did_ack(
                self._kp.ss58_address,
                False,
                'something unexpected happen')
            self.emit_out(data)

    def process_event(self, event):
        if event.event_id == P2PMessage.RECEIVE_CHAIN_EVENT:
            event_id = event.chain_event_data.event_id
            attributes = json.loads(event.chain_event_data.attributes)
            if self.is_consumer_refund_approve_event(event, self._charging_info):
                if not self.is_approving():
                    self._logger.error(f'received "approve refund event" event while not in state "approving" '
                                       f' event: {event_id}: {attributes}')
                    return

                if 'Ok' not in attributes[-1]:
                    self.emit_log({
                        'desc': 'the consumer refund approval has an error, please check',
                        'time_point': attributes[1],
                        'error': attributes[-1]
                    })
                    return
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

            if self.is_consumer_spent_approve_event(event, self._charging_info):
                if not self.is_approving():
                    self._logger.error(f'received "consumer spent event" event while not in state "approving" '
                                       f'event: {event_id}: {attributes}')
                    return

                if 'Ok' not in attributes[-1]:
                    self.emit_log({
                        'desc': 'the consumer spent approval has an error, please check',
                        'time_point': attributes[1],
                        'error': attributes[-1]
                    })
                    return
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
            self.emit_log({'state': self.state, 'data': f'{event_id}'})
            self._logger.info(f'Event: {event_id}: {attributes}')
            return

        if event.event_id == P2PMessage.GET_BALANCE:
            try:
                balance = get_station_balance(self._substrate, self._kp, self._logger)
                data = UserUtils.create_get_balance_ack(str(balance), True, '')
                self.emit_out(data)
            except Exception as e:
                self._logger.error(f'exception happen when acquiring balance: {e}')
                data = UserUtils.create_get_balance_ack(str(0), False, f'error: {e}')
                self.emit_out(data)
        if event.event_id == P2PMessage.GET_PK:
            data = UserUtils.create_get_pk_ack(self._kp.ss58_address, True, '')
            self.emit_out(data)
        if event.event_id == P2PMessage.REPUBLISH_DID:
            self.republish_did()
        if event.event_id == P2PMessage.RECONNECT:
            self.reconnect()
        if event.event_id == P2PMessage.STOP_CHARGE:
            if not self.is_charging():
                self._logger.error('received "finished charging" event while not in state "charging"'
                                   f'event: {event.stop_charge_data.success}')
                return

            self.end_charging()
            P2PUtils.send_stop_charing_ack(self._redis, 'Stop charing received')
            self._logger.info('ended charging')
            self.emit_log({
                'state': self.state,
                'data': 'Charging end',
                'info': event.stop_charge_data.success
            })

            self._charging_info['charging_end_time'] = datetime.datetime.now()
            charging_result = CharginUtils.calculate_charging_result(
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

            ChainUtils.send_service_deliver(
                self._substrate, self._kp, self._charging_info['consumer'],
                compose_delivery_info(refund_token, refund_info),
                compose_delivery_info(spent_token, spent_info), self._logger)

            P2PUtils.send_service_deliver(
                self._redis, self._kp, self._charging_info['consumer'],
                compose_delivery_info(refund_token, refund_info),
                compose_delivery_info(spent_token, spent_info))

            self.emit_service_delivered({
                'provider': self._kp.ss58_address,
                'consumer': self._charging_info['consumer'],
                'refund_info': compose_delivery_info(refund_token, refund_info),
                'spent_info': compose_delivery_info(spent_token, spent_info),
            })

            self.wait_approval()
            self.emit_log({'state': self.state, 'data': 'User\'s approval wait'})

        if self.is_service_requested_event(event,
                                           self._kp.ss58_address):
            if not self.is_idle():
                self._logger.error('received "service requested" event while not in state "idle"'
                                   f'event: {event_id}: {attributes}')
                return

            p2p_event = event
            consumer = p2p_event.service_requested_data.consumer
            deposit_token = int(p2p_event.service_requested_data.token_deposited)

            self._charging_info.update({
                'consumer': consumer,
                'deposit_token': deposit_token,
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
            P2PUtils.send_request_ack(self._redis, 'ServiceRequested received')

            self.check(self._charging_info)
            if self.is_idle():
                self.emit_log({'state': self.state, 'data': 'Check refuse'})
                # [TODO] We should change the API type and the naming...
                self.emit_deposit_verified({
                    'consumer': self._charging_info['consumer'],
                    'token_deposited': self._charging_info['deposit_token'],
                    'success': False,
                })
                return
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
        self._logger.info(f'Event: {event}')

    def start(self):
        r = None
        try:
            self._logger.info('reading did...')
            r = read_did(self._substrate, self._kp, self._logger)
            if r.is_success:
                event = [_.value for _ in r.triggered_events
                         if _.value['event_id'] == 'AttributeRead'][0]
                self._logger.info(f'successfully read did: {json.loads(event["attributes"]["value"])}')
        except Exception as err:
            self._logger.error(f'failed to read did: {err}')

        if r is not None and not r.is_success:
            try:
                self._logger.info('publishing did...')
                r = publish_did(self._substrate, self._kp, self._logger)
            except Exception as err:
                self._logger.error(f'failed to publish did: {err}')

        subcriber = self._redis.pubsub()
        subcriber.subscribe(REDIS_IN)

        while True:
            event_data = subcriber.get_message(True, timeout=30000.0)

            if event_data is None:
                continue

            event = ChainUtils.decode_chain_event(event_data['data'].decode('utf-8'))
            try:
                self.process_event(event)
            except BrokenPipeError:
                self.emit_log({
                    'desc': 'Broken pipe happens, please check',
                })

    def reconnect(self):
        try:
            self._substrate.close()
            self._substrate = ChainUtils.get_substrate_connection(self._ws_url)
            data = UserUtils.create_reconnect_ack(
                'Successfully reconnected',
                True,
                '')
            self.emit_out(data)
        except Exception as err:
            data = UserUtils.create_reconnect_ack(
                '',
                False,
                f'Reconnection failed: {err}')
            self.emit_out(data)
