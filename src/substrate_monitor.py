from queue import Queue
from src.utils import get_substrate_connection


def run_substrate_monitor(ws_url: str, q: Queue):
    monitor = SubstrateMonitor(ws_url, q)
    monitor.register_monitor_event()


class SubstrateMonitor():
    def __init__(self, ws_url: str, q: Queue):
        self._substrate = get_substrate_connection(ws_url)
        self._q = q

    def subscription_event_handler(self, objs, update_nr, subscription_id):
        for obj in objs:
            event = obj['event'].value
            self._q.put({
                'event_id': event['event_id'],
                'attributes': event['attributes'],
            })

    def register_monitor_event(self):
        self._substrate.query('System', 'Events',
                              None,
                              subscription_handler=self.subscription_event_handler)
