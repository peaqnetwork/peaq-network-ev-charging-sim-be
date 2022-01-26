import unittest
import logging
from src import app
from queue import Queue


class TestBE(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_http_pk(self):
        q = Queue()
        logger = logging.getLogger('logger')
        backend, _ = app.create_app('secret', True, q, 'pk', logger)
        client = backend.test_client()
        out = client.get('/pk')
        self.assertEqual(out.status_code, 200)
        self.assertEqual(out.data.decode('ascii'), 'pk')

    def test_websocket(self):
        q = Queue()
        logger = logging.getLogger('logger')
        backend, socketio = app.create_app('secret', True, q, 'pk', logger)
        client = socketio.test_client(backend)
        self.assertTrue(client.is_connected())
        socketio.emit('yoyo_name', 'yoyo_data')
        data = client.get_received()[0]
        self.assertEqual(data['namespace'], '/')
        self.assertEqual(data['name'], 'yoyo_name')
        self.assertEqual(data['args'], ['yoyo_data'])


if __name__ == '__main__':
    unittest.main()
