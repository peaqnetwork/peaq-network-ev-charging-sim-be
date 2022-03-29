import redis
import transitions
import threading
import logging
from peaq_network_ev_charging_message_format.python import p2p_message_format_pb2 as P2PMessage

from src.constants import REDIS_OUT, REDIS_IN, CHARGING_STATUS_POLLING_TIME
from src import chain_utils as ChainUtils
from src import p2p_utils as P2PUtils


def run(r: redis.Redis, logger: logging.Logger):
    c = ChargingStatusMonitor(r, logger)
    c.start()


# New thread
def send_the_status(stop_event: threading.Event, logger: logging.Logger, r: redis.Redis):
    while not stop_event.isSet():
        event_hex = P2PUtils.create_server_charging_status()
        r.publish(REDIS_IN, event_hex.encode('ascii'))
        stop_event.wait(CHARGING_STATUS_POLLING_TIME)


class ChargingStatusMonitor():
    states = ['idle', 'monitoring']

    def __init__(self, r: redis.Redis, logger: logging.Logger):
        self._r = r
        self._machine = transitions.Machine(
            model=self,
            states=ChargingStatusMonitor.states,
            initial='idle'
        )
        self._logger = logger
        self._stop_event = threading.Event()

        self._machine.add_transition(trigger='start_monitor', source='idle', dest='monitoring')
        self._machine.add_transition(trigger='end_monitor', source='monitoring', dest='idle')

    def is_charging_start(self, event):
        # We use service request as charging start
        if event.event_id != P2PMessage.SERVICE_REQUEST_ACK:
            return False
        if not self.is_idle():
            self._logger.info(f'In {self.state}, but receive the charging start')
            return False
        return True

    def is_charging_end(self, event):
        if event.event_id != P2PMessage.STOP_CHARGE_RESPONSE:
            return False
        if not self.is_monitoring():
            self._logger.info(f'In {self.state}, but receive the stop')
            return False
        return True

    def start(self):
        subcriber = self._r.pubsub()
        subcriber.subscribe(REDIS_OUT)

        while True:
            event_data = subcriber.get_message(True, timeout=30000.0)

            if event_data is None:
                continue

            event = ChainUtils.decode_chain_event(event_data['data'].decode('utf-8'))

            if self.is_charging_start(event):
                self._logger.info('Start to monitor')
                self.start_monitor()
                monitor_thread = threading.Thread(target=send_the_status,
                                                  args=(self._stop_event, self._logger, self._r))
                monitor_thread.start()

            if self.is_charging_end(event):
                self._stop_event.set()
                self._stop_event = threading.Event()
                self.end_monitor()
                self._logger.info('Stop to monitor')
