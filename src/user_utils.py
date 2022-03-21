from peaq_network_ev_charging_message_format.python import p2p_message_format_pb2 as P2PMessage


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
    if data['event_id'] == 'GetBalance':
        return _create_get_balance()
    if data['event_id'] == 'GetPK':
        return _create_get_pk()
    if data['event_id'] == 'RePublishDID':
        return _create_republish_did()
    if data['event_id'] == 'Reconnect':
        return _create_reconnect()
    if data['event_id'] == 'UserChargingStop':
        return _create_stop_user_charging(data)
    raise IOError(f"data doesn't have the correct {data}")


def create_get_pk_ack(addr: str, success: bool):
    return 'GetPKResponse', {'data': addr, 'success': success}


def create_get_balance_ack(balance: str, success: bool):
    return 'GetBalanceResponse', {'data': balance, 'success': success}


def create_republish_did_ack(addr: str, success: bool, message: str):
    return 'RePublishDIDResponse', {'data': addr, 'success': success, 'message': message}


def create_reconnect_ack(mesg: str, success: bool):
    return 'ReconnectResponse', {'message': mesg, 'success': success}
