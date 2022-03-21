import json
from peaq_network_ev_charging_message_format.python import p2p_message_format_pb2 as P2PMessage
from substrateinterface import Keypair


def decode_p2p_event(event: dict) -> P2PMessage.Event:
    p2p_info = P2PMessage.Event()
    p2p_info.ParseFromString(bytes.fromhex(event['data']))
    return p2p_info


def is_service_requested_event(p2p_event: P2PMessage.EventType) -> bool:
    if p2p_event.event_id != P2PMessage.EventType.SERVICE_REQUESTED and \
       p2p_event.HasField('service_requested_data'):
        return False
    return True


def _create_service_request(ss58_consumer_addr: str, ss58_provider_addr: str, token_deposit: int) -> P2PMessage.Event:
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.SERVICE_REQUESTED
    request_data = P2PMessage.ServiceRequestedData()
    request_data.consumer = ss58_consumer_addr
    request_data.provider = ss58_provider_addr
    request_data.token_deposited = str(token_deposit)
    event.service_requested_data.CopyFrom(request_data)
    return event


def send_service_request(redis, kp_consumer: Keypair, ss58_provider_addr: str, token_num: int):
    event = _create_service_request(kp_consumer.ss58_address, ss58_provider_addr, token_num)

    redis.publish('in', json.dumps({
        'type': 'p2p',
        'data': event.SerializeToString().hex()
    }).encode('ascii'))


def _create_p2p_request_ack(data_to_send) -> P2PMessage.Event:
    requested_ack = P2PMessage.ServiceAckData()
    requested_ack.resp.message = data_to_send
    requested_ack.resp.error = False
    event_resp = P2PMessage.Event()
    event_resp.service_ack_data.CopyFrom(requested_ack)
    event_resp.event_id = P2PMessage.EventType.SERVICE_REQUEST_ACK
    return event_resp


def send_request_ack(redis, data_to_send: str):
    request_ack = _create_p2p_request_ack(data_to_send)
    redis.publish('out', json.dumps({
        'type': 'p2p',
        'data': request_ack.SerializeToString().hex(),
    }).encode('ascii'))


def _convert_transaction_value(info: dict):
    data = P2PMessage.TransactionValue()
    data.token_num = str(info['token_num'])
    data.tx_hash = info['tx_hash']
    data.call_hash = info['call_hash']
    time_point = P2PMessage.TransactionValue.TimePoint()
    time_point.height = info['time_point']['height']
    time_point.index = info['time_point']['index']
    data.time_point.CopyFrom(time_point)
    return data


def _create_service_deliver_req(kp: Keypair, ss58_user_addr: str,
                                refund_info: dict, spent_info: dict) -> P2PMessage.Event:
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.SERVICE_DELIVERED
    delivered_data = P2PMessage.ServiceDeliveredData()
    delivered_data.consumer = ss58_user_addr
    delivered_data.provider = kp.ss58_address
    delivered_data.refund_info.CopyFrom(_convert_transaction_value(refund_info))
    delivered_data.spent_info.CopyFrom(_convert_transaction_value(spent_info))
    event.service_delivered_data.CopyFrom(delivered_data)
    return event


def send_service_deliver(redis, kp: Keypair, ss58_user_addr: str,
                         refund_info: dict, spent_info: dict):
    delivered_data = _create_service_deliver_req(kp, ss58_user_addr, refund_info, spent_info)

    redis.publish('out', json.dumps({
        'type': 'p2p',
        'data': delivered_data.SerializeToString().hex()
    }).encode('ascii'))
