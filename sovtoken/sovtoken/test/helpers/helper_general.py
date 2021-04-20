import json

import base58
from sovtoken.constants import RESULT, OUTPUTS, SEQNO, ADDRESS
from indy.payment import parse_get_payment_sources_response


class HelperGeneral():
    """
    Helper that uses all the other helpers.

    # Methods
    - get_utxo_addresses
    - do_mint
    - do_transfer
    - do_get_utxo
    """

    def __init__(self, helper_sdk, helper_wallet, helper_request, helper_node):
        self._sdk = helper_sdk
        self._wallet = helper_wallet
        self._request = helper_request
        self._node = helper_node

    # =============
    # Requests
    # =============
    # Methods for creating and sending requests.

    def get_utxo_addresses(self, addresses):
        """ Get and return the utxos for each address. """
        requests = [self._request.get_utxo(address) for address in addresses]
        responses = self._sdk.send_and_check_request_objects(requests)
        utxos = [parse_get_payment_sources_response("sov", json.dumps(response)) for _request, response in responses]
        utxos = [json.loads(self._request._looper.loop.run_until_complete(utxo_future)) for utxo_future in utxos]
        return utxos

    def do_mint(self, outputs, no_wait=False, text=None, mechanism=None, version=None):
        """ Build and send a mint request. """
        request = self._request.mint(outputs, text, mechanism, version)
        if no_wait:
            return self._send_without_waiting(request)
        return self._send_get_first_result(request)

    def do_nym(
        self,
        seed=None,
        alias=None,
        role=None,
        dest=None,
        verkey=None,
        sdk_wallet=None
    ):
        """ Build and send a nym request. """
        request = self._request.nym(seed, alias, role, dest, verkey, sdk_wallet)
        return self._send_get_first_result(request)

    def do_transfer(self, inputs, outputs, identifier=None, extra=None, text=None, mechanism=None, version=None):
        """ Build and send a transfer request. """
        if text and mechanism and version:
            extra = self._request.add_transaction_author_agreement_to_extra(extra, text, mechanism, version)
        request = self._request.transfer(inputs, outputs, identifier=identifier, extra=extra)
        return self._send_get_first_result(request)

    def transfer_without_waiting(self, inputs, outputs, identifier=None):
        """ Build and send a transfer request. """
        request = self._request.transfer(inputs, outputs, identifier=identifier)
        return self._send_without_waiting(request)

    def do_get_utxo(self, address):
        """ Build and send a get_utxo request. """
        request = self._request.get_utxo(address)
        result = self._send_get_first_result(request)
        result[OUTPUTS] = self._sort_utxos(result[OUTPUTS])

        return result

    def do_acceptance_mechanism(self, sdk_trustee_wallet, aml, aml_context=None):
        request = self._request.acceptance_mechanism(sdk_trustee_wallet, aml, aml_context)
        result = self._send_get_first_result(request)
        return result

    def do_transaction_author_agreement(self, sdk_trustee_wallet, text, version="abc"):
        request = self._request.transaction_author_agreement(sdk_trustee_wallet, text, version)
        result = self._send_get_first_result(request)
        return result

    def do_get_transaction_author_agreement(self):
        request = self._request.get_transaction_author_agreement()
        result = self._send_get_first_result(request)
        return result

    # =============
    # Private Methods
    # =============

    def _send_get_first_result(self, request_object, sign=True):
        responses = self._sdk.send_and_check_request_objects([request_object], sign=sign)
        result = self._sdk.get_first_result(responses)
        return result

    def _sort_utxos(self, utxos):
        """ Sort utxos by the seq_no. """
        utxos.sort(key=lambda utxo: utxo[SEQNO])
        return utxos

    def _send_without_waiting(self, request_object):
        responses = self._sdk.send_request_objects([request_object])
        return responses


def utxo_from_addr_and_seq_no(addr, seq_no):
    a = {
        ADDRESS: addr,
        SEQNO: seq_no
    }
    s = json.dumps(a).encode('utf-8')
    return "txo:sov:" + base58.b58encode_check(s).decode('utf-8')
