import base58

from common.serializers.serialization import serialize_msg_for_signing
from plenum.common.constants import TXN_TYPE
from plenum.common.exceptions import InvalidSignatureFormat, \
    InsufficientCorrectSignatures, InvalidClientRequest
from plenum.common.types import PLUGIN_TYPE_AUTHENTICATOR, OPERATION, f
from plenum.common.verifier import DidVerifier
from plenum.server.client_authn import CoreAuthNr
from plenum.server.plugin.fees.src import AcceptableWriteTypes, AcceptableQueryTypes
from plenum.server.plugin.fees.src.constants import SET_FEES, FEES
from plenum.server.plugin.token.src.client_authnr import AddressSigVerifier
from plenum.server.plugin.token.src.util import address_to_verkey


class FeesAuthNr(CoreAuthNr):
    pluginType = PLUGIN_TYPE_AUTHENTICATOR

    write_types = AcceptableWriteTypes
    query_types = AcceptableQueryTypes

    def __init__(self, state, token_authnr):
        super().__init__(state)
        self.token_authnr = token_authnr

    def authenticate(self, req_data, identifier: str = None,
                     signature: str = None, verifier=None):
        txn_type = req_data[OPERATION][TXN_TYPE]
        if txn_type == SET_FEES:
            verifier = verifier or DidVerifier
            return super().authenticate(req_data, identifier, signature,
                                        verifier=verifier)
        else:

            raise InvalidClientRequest(req_data[f.REQ_ID.nm], identifier,
                                       "txn type is {} not {}".format(txn_type, SET_FEES))

    def verify_signature(self, msg):
        try:
            fees = getattr(msg, f.FEES.nm)
        except (AttributeError, KeyError):
            return
        correct_sigs_from = set()
        required_sigs_from = set()
        outputs = fees[1]
        for addr, seq_no, sig in fees[0]:
            required_sigs_from.add(addr)
            try:
                sig = base58.b58decode(sig.encode())
            except Exception as ex:
                raise InvalidSignatureFormat from ex

            to_ser = [[addr, seq_no], outputs]
            serz = serialize_msg_for_signing(to_ser)
            try:
                verkey = address_to_verkey(addr)
            except ValueError:
                continue
            verifier = AddressSigVerifier(verkey=verkey)
            if verifier.verify(sig, serz):
                correct_sigs_from.add(addr)
        if correct_sigs_from != required_sigs_from:
            raise InsufficientCorrectSignatures(len(correct_sigs_from),
                                                len(fees[0]))
