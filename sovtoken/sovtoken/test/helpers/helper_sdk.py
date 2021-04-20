import json

from indy import did
from indy.anoncreds import issuer_create_and_store_credential_def, issuer_create_schema
from indy.ledger import build_cred_def_request, build_attrib_request, build_schema_request, build_nym_request, \
    build_get_txn_request

import plenum.test.helper as plenum_helper

from sovtoken.constants import RESULT

from indy_node.test.anon_creds.helper import create_revoc_reg, create_revoc_reg_entry

from indy_common.constants import ISSUANCE_BY_DEFAULT

from indy_common.types import Request
from plenum.common.util import randomString, hexToFriendly

from plenum.test.pool_transactions.helper import prepare_node_request

from plenum.common.constants import VALIDATOR

from plenum.test.helper import sdk_json_to_request_object


class HelperSdk():
    """
    HelperSdk is a class which abstracts away the looper, pool_handle, and
    node_pool in the sdk calls.

    # Methods

    - get_first_result

    ## methods for sending request objects
    - prepare_request_objects
    - send_and_check_request_objects
    - send_request_objects

    ## ported sdk methods
    - sdk_get_and_check_replies
    - sdk_send_and_check
    - sdk_send_signed_requests
    - sdk_json_to_request_object
    """

    def __init__(self, looper, pool_handle, node_pool, wallet_steward):
        self._looper = looper
        self._pool_handle = pool_handle
        self._node_pool = node_pool
        self._wallet_steward = wallet_steward

    def get_first_result(self, request_response_list):
        """ Gets the result field from the first response. """
        return request_response_list[0][1][RESULT]

    # =============
    # Request object methods
    # =============
    # Methods for sending Request from plenum.common.request

    def prepare_request_objects(self, request_objects, wallet=None, sign=False):
        """ Prepares the request to be sent by transforming it into json and sign. """
        if sign and all(not (req.signature or req.signatures) for req in request_objects):
            requests = self.sdk_sign_request_objects(request_objects, wallet)
        else:
            requests = [json.dumps(request.as_dict) for request in request_objects]
        return requests

    def send_and_check_request_objects(self, request_objects, wallet=None, sign=True):
        """
        Sends the request objects and checks the replies are valid.

        Returns a list of request_response tuples.
        """
        requests = self.prepare_request_objects(request_objects, wallet, sign)
        return self.sdk_send_and_check(requests)

    def send_request_objects(self, request_objects, wallet=None, sign=True):
        """ Sends the request objects """
        requests = self.prepare_request_objects(request_objects, wallet, sign)
        return self.sdk_send_signed_requests(requests)

    # =============
    # Methods ported from plenum helper
    # =============

    def sdk_get_and_check_replies(self, req_resp_sequence, timeout=None):
        return plenum_helper.sdk_get_and_check_replies(
            self._looper,
            req_resp_sequence,
            timeout
        )

    def sdk_send_signed_requests(self, requests_signed):
        return plenum_helper.sdk_send_signed_requests(
            self._pool_handle,
            requests_signed,
        )

    def sdk_send_and_check(self, requests_signed, timeout=None):
        return plenum_helper.sdk_send_and_check(
            requests_signed,
            self._looper,
            self._node_pool,
            self._pool_handle,
            timeout
        )

    def sdk_json_to_request_object(self, obj):
        return plenum_helper.sdk_json_to_request_object(obj)

    def sdk_sign_request_objects(self, requests, sdk_wallet=None):
        sdk_wallet = sdk_wallet or self._wallet_steward

        return plenum_helper.sdk_sign_request_objects(
            self._looper,
            sdk_wallet,
            requests
        )

    def sdk_build_nym(self, identifier=None, sdk_wallet=None):
        sdk_wallet = sdk_wallet or self._wallet_steward
        identifier = identifier or sdk_wallet[1]
        ident, verk = self._looper.loop.run_until_complete(
            did.create_and_store_my_did(self._wallet_steward[0],
                                        json.dumps({'seed': plenum_helper.random_string(32)})))

        request = self._looper.loop.run_until_complete(build_nym_request(identifier, ident, verk, None, None))
        return request

    def sdk_build_attrib(self, identifier=None, sdk_wallet=None):
        sdk_wallet = sdk_wallet or self._wallet_steward
        identifier = identifier or sdk_wallet[1]
        request = self._looper.loop.run_until_complete(build_attrib_request(identifier, identifier, None,
                                                                            json.dumps({'answer': 42}), None))
        return request

    def sdk_build_schema(self, identifier=None, sdk_wallet=None):
        sdk_wallet = sdk_wallet or self._wallet_steward
        identifier = identifier or sdk_wallet[1]
        _, schema_json = self._looper.loop.run_until_complete(
            issuer_create_schema(identifier, "name", "1.0", json.dumps(["first", "last"])))
        request = self._looper.loop.run_until_complete(build_schema_request(identifier, schema_json))
        return request

    def sdk_build_claim_def(self, schema_json, identifier=None, sdk_wallet=None):
        sdk_wallet = sdk_wallet or self._wallet_steward
        identifier = identifier or sdk_wallet[1]
        wallet_handle, _ = sdk_wallet
        _, definition_json = self._looper.loop.run_until_complete(issuer_create_and_store_credential_def(
            wallet_handle, identifier, schema_json, "some_tag", "CL", json.dumps({"support_revocation": True})))
        request = self._looper.loop.run_until_complete(build_cred_def_request(identifier, definition_json))
        return request

    def sdk_build_revoc_reg_def(self,
                                claim_def_id,
                                tag=randomString(5),
                                identifier=None,
                                sdk_wallet=None,
                                issuance=ISSUANCE_BY_DEFAULT):
        sdk_wallet = sdk_wallet or self._wallet_steward
        identifier = identifier or sdk_wallet[1]
        wallet_handle, _ = sdk_wallet
        return create_revoc_reg(self._looper, wallet_handle, identifier, tag, claim_def_id, issuance=issuance)

    def sdk_build_revoc_reg_entry(self,
                                  claim_def_id,
                                  tag=randomString(5),
                                  identifier=None,
                                  sdk_wallet=None,
                                  issuance=ISSUANCE_BY_DEFAULT):
        sdk_wallet = sdk_wallet or self._wallet_steward
        identifier = identifier or sdk_wallet[1]
        wallet_handle, _ = sdk_wallet
        reg_def, reg_entry = create_revoc_reg_entry(self._looper, wallet_handle, identifier, tag, claim_def_id,
                                                    issuance=issuance)
        self.send_and_check_request_objects([Request(**json.loads(reg_def))], wallet=sdk_wallet)
        return reg_entry

    def sdk_build_get_txn(self, ledger_id, seq_no):
        get_txn_request_future = build_get_txn_request(None, ledger_id, seq_no)
        get_txn_request = self._looper.loop.run_until_complete(get_txn_request_future)
        return get_txn_request

    def sdk_prepare_node_request(self, node, wallet, services=[]) -> str:
        _, submitter_did = wallet
        node_nym = hexToFriendly(node.nodestack.verhex)
        return self._looper.loop.run_until_complete(
            prepare_node_request(submitter_did,
                                 new_node_name=node.name,
                                 clientIp=None,
                                 clientPort=None,
                                 nodeIp=None,
                                 nodePort=None,
                                 bls_key=None,
                                 destination=node_nym,
                                 services=services,
                                 key_proof=None))

    def sdk_build_demote_txn(self, node, wallet):
        req_str = self.sdk_prepare_node_request(node, wallet, [])
        return sdk_json_to_request_object(json.loads(req_str))

    def sdk_build_promote_txn(self, node, wallet):
        req_str = self.sdk_prepare_node_request(node, wallet, [VALIDATOR])
        return sdk_json_to_request_object(json.loads(req_str))
