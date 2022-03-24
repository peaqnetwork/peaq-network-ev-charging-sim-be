import redis

from src import chain_utils as ChainUtils
from src.constants import REDIS_IN


def run_substrate_monitor(ws_url: str, r: redis.Redis):
    monitor = SubstrateMonitor(ws_url, r)
    monitor.register_monitor_event()


class SubstrateMonitor():
    def __init__(self, ws_url: str, r: redis.Redis):
        self._substrate = ChainUtils.get_substrate_connection(ws_url)
        self._redis = r

    def __del__(self):
        if self._substrate:
            self._substrate.close()

    def subscription_event_handler(self, objs, update_nr, subscription_id):
        filter_list = ['ExtrinsicSuccess', 'NewBaseFeePerGas']
        for obj in objs:
            event = obj['event'].value
            if event['event_id'] in filter_list:
                continue

            data_to_send = ChainUtils.create_chain_event_data(event)
            self._redis.publish(REDIS_IN, data_to_send.encode('ascii'))

    def register_monitor_event(self):
        self._substrate.query('System', 'Events',
                              None,
                              subscription_handler=self.subscription_event_handler)
