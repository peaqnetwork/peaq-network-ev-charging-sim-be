from peaq_network_ev_charging_message_format.python import did_document_format_pb2 as DIDMessage
from google.protobuf.json_format import Parse
from substrateinterface import Keypair
import json


VERSION = 'v2'
VALID_FOR = 4_294_967_295


def decode_did_event(did: dict) -> DIDMessage.Document:
    if did['name'] != VERSION:
        raise IOError(f'Version: f{did["name"]} not {VERSION}, raw {did}')
    did_info = DIDMessage.Document()
    did_info.ParseFromString(bytes.fromhex(did['value']))
    return did_info


def compose_did(sr25519_kp: Keypair, ed25519_kp: Keypair, issuer_kp: Keypair, p2p_url: str):
    document = DIDMessage.Document()
    document.id = f'did:peaq:{sr25519_kp.ss58_address}'
    document.controller = f'did:peaq:{sr25519_kp.ss58_address}'

    sr25519_verification = DIDMessage.VerificationMethod()
    sr25519_verification.id = f'{sr25519_kp.public_key.hex()}'
    sr25519_verification.type = DIDMessage.VerificationType.Sr25519VerificationKey2020
    sr25519_verification.controller = f'did:peaq:{sr25519_kp.ss58_address}'
    sr25519_verification.publicKeyMultibase = f'{sr25519_kp.ss58_address}'

    ed25519_verification = DIDMessage.VerificationMethod()
    ed25519_verification.id = f'{ed25519_kp.public_key.hex()}'
    ed25519_verification.type = DIDMessage.VerificationType.Ed25519VerificationKey2020
    ed25519_verification.controller = f'did:peaq:{sr25519_kp.ss58_address}'
    ed25519_verification.publicKeyMultibase = f'{ed25519_kp.ss58_address}'

    document.verificationMethods.extend([ed25519_verification, sr25519_verification])

    signature = DIDMessage.Signature()
    signature.type = DIDMessage.VerificationType.Sr25519VerificationKey2020
    signature.issuer = f'did:peaq:{issuer_kp.ss58_address}'
    signature.hash = issuer_kp.sign('0x' + sr25519_kp.public_key.hex()).hex()
    document.signature.CopyFrom(signature)

    payment_service = DIDMessage.Service()
    payment_service.id = f'{sr25519_kp.ss58_address}'
    payment_service.type = DIDMessage.ServiceType.payment
    payment_service.stringData = sr25519_kp.ss58_address

    p2p_service = DIDMessage.Service()
    p2p_service.id = f'{sr25519_kp.ss58_address}'
    p2p_service.type = DIDMessage.ServiceType.p2p
    p2p_service.stringData = p2p_url

    meta = DIDMessage.Metadata()
    meta.plugType = 'CEV2021'
    meta.power = '2000KwH'
    meta.status = DIDMessage.Status.AVAILABLE

    meta_service = DIDMessage.Service()
    meta_service.id = f'{sr25519_kp.ss58_address}'
    meta_service.type = DIDMessage.ServiceType.metadata
    meta_service.metadata.CopyFrom(meta)

    document.services.extend([payment_service, p2p_service, meta_service])
    document.authentications.extend([sr25519_kp.public_key.hex(), ed25519_kp.public_key.hex()])

    return document


def load_did(did_path: str) -> DIDMessage.Document:
    with open(did_path) as f:
        default_did = json.load(f)
    return Parse(json.dumps(default_did), DIDMessage.Document())


def is_my_did(did_doc: DIDMessage.Document, ss58_addr: str) -> bool:
    return did_doc.id == f'did:peaq:{ss58_addr}'


def is_did_valid(did_doc: DIDMessage.Document, ss58_addr: str, default_path: str) -> bool:
    if not is_my_did(did_doc, ss58_addr):
        return False
    default_did = load_did(default_path)
    default_did.signature.hash = ''
    did_doc.signature.hash = ''

    if default_did != did_doc:
        return False
    return True
