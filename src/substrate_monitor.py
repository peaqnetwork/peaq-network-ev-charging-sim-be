import redis
import json

from src.utils import get_substrate_connection


def run_substrate_monitor(ws_url: str, r: redis.Redis):
    monitor = SubstrateMonitor(ws_url, r)
    monitor.register_monitor_event()


class SubstrateMonitor():
    def __init__(self, ws_url: str, r: redis.Redis):
        self._substrate = get_substrate_connection(ws_url)
        self._redis = r

    def subscription_event_handler(self, objs, update_nr, subscription_id):
        for obj in objs:
            event = obj['event'].value
            data_to_send = {
                'event_id': event['event_id'],
                'attributes': event['attributes'],
            }
            self._redis.publish("in", json.dumps(data_to_send).encode('ascii'))

    def register_monitor_event(self):
        self._substrate.query('System', 'Events',
                              None,
                              subscription_handler=self.subscription_event_handler)
