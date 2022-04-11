import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

import unittest
from src.bs_logic import BusinessLogic
from src.p2p_utils import _create_p2p_request_ack
from src.p2p_utils import _convert_transaction_value, _create_service_deliver_req
from src import user_utils as UserUtils
from unittest import mock
from peaq_network_ev_charging_message_format.python import p2p_message_format_pb2 as P2PMessage
from substrateinterface import Keypair


class TestBSLogic(unittest.TestCase):
    def test_decode_hex_event(self):
        p2p_info = P2PMessage.Event()
        p2p_info.event_id = P2PMessage.EventType.CHARGING_STATUS
        status = P2PMessage.ChargingStatusData()
        status.progress = 17
        p2p_info.charging_status_data.CopyFrom(status)

        p2p_event = UserUtils.decode_hex_event(p2p_info.SerializeToString().hex())
        self.assertEqual(p2p_info, p2p_event)

    @mock.patch('src.chain_utils.get_substrate_connection')
    def test_is_service_requested_event_true(self, mock_get_conn):
        mock_get_conn.return_value = None

        bs = BusinessLogic('', None, None, None, None)
        kp = Keypair.create_from_uri('//Alice')

        p2p_info = P2PMessage.Event()
        p2p_info.event_id = P2PMessage.EventType.SERVICE_REQUESTED
        request = P2PMessage.ServiceRequestedData()
        request.provider = kp.ss58_address
        request.token_deposited = '10'
        p2p_info.service_requested_data.CopyFrom(request)

        self.assertTrue(bs.is_service_requested_event(p2p_info, kp.ss58_address))

    @mock.patch('src.chain_utils.get_substrate_connection')
    def test_is_service_requested_event_false(self, mock_get_conn):
        mock_get_conn.return_value = None

        bs = BusinessLogic('', None, None, None, None)

        p2p_info = P2PMessage.Event()
        p2p_info.event_id = P2PMessage.EventType.SERVICE_REQUESTED
        request = P2PMessage.ServiceRequestedData()
        request.provider = Keypair.create_from_uri('//Alice').public_key.hex()
        request.token_deposited = '10'
        p2p_info.service_requested_data.CopyFrom(request)

        self.assertFalse(bs.is_service_requested_event(p2p_info,
                                                       Keypair.create_from_uri('//QQ').ss58_address))

    def test_create_request_ack(self):
        data = 'to the moon'

        resp = _create_p2p_request_ack(data)

        requested_ack = P2PMessage.ServiceAckData()
        requested_ack.resp.message = data
        event_resp = P2PMessage.Event()
        event_resp.service_ack_data.CopyFrom(requested_ack)
        event_resp.event_id = P2PMessage.EventType.SERVICE_REQUEST_ACK

        self.assertEqual(resp, event_resp)

    def test_convert_transaction_value(self):
        data = {
            'token_num': 21,
            'tx_hash': '112233',
            'time_point': {
                'height': 20,
                'index': 31,
            },
            'call_hash': '223344'
        }
        resp = _convert_transaction_value(data)
        self.assertEqual(resp.token_num, str(data['token_num']))
        self.assertEqual(resp.tx_hash, str(data['tx_hash']))
        self.assertEqual(resp.call_hash, str(data['call_hash']))
        self.assertEqual(resp.time_point.height, data['time_point']['height'])
        self.assertEqual(resp.time_point.index, data['time_point']['index'])

    def test_create_service_deliver_req(self):
        refund_data = {
            'token_num': 21,
            'tx_hash': '112233',
            'time_point': {
                'height': 20,
                'index': 31,
            },
            'call_hash': '223344'
        }
        spent_data = {
            'token_num': 22,
            'tx_hash': '334455',
            'time_point': {
                'height': 21,
                'index': 3,
            },
            'call_hash': '445566'
        }
        provider_kp = Keypair.create_from_uri('//AA')
        consumer_kp = Keypair.create_from_uri('//BB')
        resp = _create_service_deliver_req(provider_kp, consumer_kp.ss58_address, refund_data, spent_data)

        self.assertEqual(resp.event_id, P2PMessage.EventType.SERVICE_DELIVERED)
        self.assertTrue(resp.HasField('service_delivered_data'))
        self.assertEqual(resp.service_delivered_data.provider, provider_kp.ss58_address)
        self.assertEqual(resp.service_delivered_data.consumer, consumer_kp.ss58_address)
        self.assertEqual(resp.service_delivered_data.refund_info, _convert_transaction_value(refund_data))
        self.assertEqual(resp.service_delivered_data.spent_info, _convert_transaction_value(spent_data))


if __name__ == '__main__':
    unittest.main()
