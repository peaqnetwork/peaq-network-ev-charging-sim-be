from peaq_network_ev_charging_message_format.python import p2p_message_format_pb2 as P2PMessage
from substrateinterface import Keypair
from src.constants import REDIS_OUT, REDIS_IN


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

    redis.publish(REDIS_IN, event.SerializeToString().hex().encode('ascii'))


def _create_p2p_request_ack(wait_time: int, data_to_send: str, success: bool) -> P2PMessage.Event:
    service_requested_ack_data = P2PMessage.ServiceRequestedAckData()
    service_requested_ack_data.wait_time = wait_time
    service_requested_ack_data.resp.message = data_to_send
    service_requested_ack_data.resp.error = not success
    event_resp = P2PMessage.Event()
    event_resp.service_requested_ack_data.CopyFrom(service_requested_ack_data)
    event_resp.event_id = P2PMessage.EventType.SERVICE_REQUEST_ACK
    return event_resp


def send_request_ack(redis, wait_time: int, data_to_send: str, success: bool):
    request_ack = _create_p2p_request_ack(wait_time, data_to_send, success)
    redis.publish(REDIS_OUT, request_ack.SerializeToString().hex().encode('ascii'))


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

    redis.publish(REDIS_OUT, delivered_data.SerializeToString().hex().encode('ascii'))


def _create_stop_charing_ack(data_to_send) -> P2PMessage.Event:
    stop_charge_resp_data = P2PMessage.StopChargeResponseData()
    stop_charge_resp_data.resp.message = data_to_send
    stop_charge_resp_data.resp.error = False
    event_resp = P2PMessage.Event()
    event_resp.stop_charge_resp_data.CopyFrom(stop_charge_resp_data)
    event_resp.event_id = P2PMessage.EventType.STOP_CHARGE_RESPONSE
    return event_resp


def send_stop_charing_ack(redis, data_to_send: str):
    ack = _create_stop_charing_ack(data_to_send)
    redis.publish(REDIS_OUT, ack.SerializeToString().hex().encode('ascii'))


def _create_stop_charging(success: bool):
    stop_charge_data = P2PMessage.StopChargeData()
    stop_charge_data.success = success
    event_resp = P2PMessage.Event()
    event_resp.stop_charge_data.CopyFrom(stop_charge_data)
    event_resp.event_id = P2PMessage.EventType.STOP_CHARGE
    return event_resp


def send_stop_charging(redis, success: bool):
    event = _create_stop_charging(success)
    redis.publish(REDIS_IN, event.SerializeToString().hex().encode('ascii'))


def create_server_charging_status():
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.CHARGING_STATUS

    return event.SerializeToString().hex()


def _create_client_charging_status(progress: float, charging_period: int, energy_consumption: float, token_spent: int):
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.CHARGING_STATUS
    charging_status_data = P2PMessage.ChargingStatusData()
    charging_status_data.progress = progress
    charging_status_data.charging_period = charging_period
    charging_status_data.energy_consumption = str(energy_consumption)
    charging_status_data.token_spent = str(token_spent)
    event.charging_status_data.CopyFrom(charging_status_data)

    return event.SerializeToString().hex()


def send_client_charging_status(redis, progress: float, charging_period: str, energy_consumption: float, token_spent: int):
    event = _create_client_charging_status(progress, charging_period, energy_consumption, token_spent)
    redis.publish(REDIS_OUT, event.encode('ascii'))
