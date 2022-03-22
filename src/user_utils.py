from peaq_network_ev_charging_message_format.python import p2p_message_format_pb2 as P2PMessage
import json


def decode_user_event(event: dict) -> P2PMessage.Event:
    user_info = P2PMessage.Event()
    user_info.ParseFromString(bytes.fromhex(event))
    return user_info


def _create_get_balance():
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.GET_BALANCE

    return event.SerializeToString().hex()


def _create_get_pk():
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.GET_PK

    return event.SerializeToString().hex()


def _create_republish_did():
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.REPUBLISH_DID

    return event.SerializeToString().hex()


def _create_reconnect():
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.RECONNECT

    return event.SerializeToString().hex()


def _create_stop_user_charging(data):
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.STOP_CHARGE
    stop_charging_data = P2PMessage.StopChargingData()
    stop_charging_data.success = data['data']
    event.stop_charging_data.CopyFrom(stop_charging_data)

    return event.SerializeToString().hex()


def create_user_request(data: dict):
    if data['type'] == 'GetBalance':
        return _create_get_balance()
    if data['type'] == 'GetPK':
        return _create_get_pk()
    if data['type'] == 'RePublishDID':
        return _create_republish_did()
    if data['type'] == 'Reconnect':
        return _create_reconnect()
    if data['type'] == 'UserChargingStop':
        return _create_stop_user_charging(data)
    raise IOError(f"data doesn't have the correct {data}")


def create_log_data(log_data: dict):
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.EMIT_SHOW_INFO
    emit_show_info_data = P2PMessage.EmitShowInfoData()
    emit_show_info_data.type = P2PMessage.EmitShowInfoData.ShowInfoType.LOG_INFO
    emit_show_info_data.data = json.dumps(log_data)
    event.emit_show_info_data.CopyFrom(emit_show_info_data)

    return event.SerializeToString().hex().encode('ascii')


def create_event_data(event_data: dict):
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.EMIT_SHOW_INFO
    emit_show_info_data = P2PMessage.EmitShowInfoData()
    emit_show_info_data.type = P2PMessage.EmitShowInfoData.ShowInfoType.EVENT_INFO
    emit_show_info_data.data = json.dumps(event_data)
    event.emit_show_info_data.CopyFrom(emit_show_info_data)

    return event.SerializeToString().hex().encode('ascii')


def create_get_pk_ack(addr: str, success: bool):
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.GET_PK_ACK
    get_pk_ack_data = P2PMessage.GetPKAckData()
    get_pk_ack_data.data = addr
    get_pk_ack_data.success = success
    event.get_pk_ack_data.CopyFrom(get_pk_ack_data)

    return event.SerializeToString().hex().encode('ascii')


def create_get_balance_ack(balance: str, success: bool):
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.GET_BALANCE_ACK
    get_balance_ack_data = P2PMessage.GetBalanceAckData()
    get_balance_ack_data.data = balance
    get_balance_ack_data.success = success
    event.get_balance_ack_data.CopyFrom(get_balance_ack_data)

    return event.SerializeToString().hex().encode('ascii')


def create_republish_did_ack(addr: str, success: bool, message: str):
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.REPUBLISH_DID_ACK
    republish_ack_data = P2PMessage.RePublishDIDAckData()
    # [TODO]
    republish_ack_data.data = message
    republish_ack_data.data = addr
    republish_ack_data.success = success
    event.republish_ack_data.CopyFrom(republish_ack_data)

    return event.SerializeToString().hex().encode('ascii')


def create_reconnect_ack(mesg: str, success: bool):
    event = P2PMessage.Event()
    event.event_id = P2PMessage.EventType.RECONNECT_ACK
    reconnect_ack_data = P2PMessage.ReconnectAckData()
    reconnect_ack_data.data = mesg
    reconnect_ack_data.success = success
    event.reconnect_ack_data.CopyFrom(reconnect_ack_data)

    return event.SerializeToString().hex().encode('ascii')


def convert_socket_type(event: P2PMessage.Event):
    if event.event_id == P2PMessage.EventType.EMIT_SHOW_INFO:
        if event.emit_show_info_data.type == P2PMessage.EmitShowInfoData.ShowInfoType.LOG_INFO:
            return 'log'
        if event.emit_show_info_data.type == P2PMessage.EmitShowInfoData.ShowInfoType.EVENT_INFO:
            return 'event'
    if event.event_id == P2PMessage.EventType.GET_BALANCE_ACK:
        return 'GetBalanceResponse'
    if event.event_id == P2PMessage.EventType.GET_PK_ACK:
        return 'GetPKResponse'
    if event.event_id == P2PMessage.EventType.REPUBLISH_DID_ACK:
        return 'RePublishDIDResponse'
    if event.event_id == P2PMessage.EventType.RECONNECT_ACK:
        return 'ReconnectResponse'
    if event.event_id == P2PMessage.EventType.STOP_CHARGE_RESPONSE:
        return 'UserChargingStop'
    if event.event_id == P2PMessage.EventType.SERVICE_REQUEST_ACK:
        return 'SeviceRequestAck'
    if event.event_id == P2PMessage.EventType.SERVICE_DELIVERED:
        return 'ServiceDeliviered'
    if event.event_id == P2PMessage.EventType.CHARGING_STATUS:
        return 'ChargingStatus'
    raise IOError(f'Not implemnted {event}')
