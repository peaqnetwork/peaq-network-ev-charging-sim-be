from peaq_network_ev_charging_message_format.python import did_document_format_pb2 as DIDMessage
from google.protobuf.json_format import Parse
from substrateinterface import Keypair
import json


VERSION = 'v2'


def decode_did_event(did: dict) -> DIDMessage.Document:
    if did['name'] != VERSION:
        raise IOError(f'Version: f{did["name"]} not {VERSION}, raw {did}')
    did_info = DIDMessage.Document()
    did_info.ParseFromString(bytes.fromhex(did['value']))
    return did_info


# TODO: Guess it will induce some error, need to check, put it to the tool?
def compose_did(kp: Keypair):
    document = DIDMessage.Document()
    document.id = f'did:peaq:{kp.ss58_address}'
    document.controller = f'did:peaq:{kp.ss58_address}'

    verification_method = DIDMessage.VerificationMethod()
    verification_method.id = f'{kp.public_key.hex()}'
    verification_method.type = DIDMessage.VerificationType.Sr25519VerificationKey2020
    verification_method.controller = f'did:peaq:{kp.ss58_address}'
    verification_method.publicKeyMultibase = f'{kp.ss58_address}'
    document.verificationMethods.push_back(verification_method)

    service = DIDMessage.Service()
    service.id = f'{kp.ss58_address}'
    service.type = DIDMessage.ServiceType.payment
    service.stringData.CopyFrom(kp.ss58_address)
    document.services.push_back(service)

    document.authentications.push_back(kp.public_key.hex())

    return document.SerializeToString().hex().encode('ascii')


def load_did(did_path: str) -> DIDMessage.Document:
    with open(did_path) as f:
        default_did = json.load(f)
    return Parse(json.dumps(default_did), DIDMessage.Document())


def is_did_valid(did_doc: DIDMessage.Document, ss58_addr: str, default_path: str) -> bool:
    if did_doc.id != f'did:peaq:{ss58_addr}':
        return False
    if load_did(default_path) != did_doc:
        return False
    return True
