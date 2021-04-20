import shutil
from datetime import datetime, timedelta

import dateutil
import pytest

from indy_common.config_helper import NodeConfigHelper
from indy_node.test.upgrade.helper import sdk_ensure_upgrade_sent
from sovtoken.constants import ADDRESS, AMOUNT, XFER_PUBLIC
from sovtokenfees.test.constants import NYM_FEES_ALIAS, XFER_PUBLIC_FEES_ALIAS
from sovtokenfees.test.helper import get_amount_from_token_txn, send_and_check_transfer, send_and_check_nym_with_fees

from plenum.common.constants import TXN_TYPE, DATA, VERSION, CURRENT_PROTOCOL_VERSION
from indy_common.constants import NODE_UPGRADE, ACTION, COMPLETE, AUTH_RULE, START
from indy_node.test.helper import sdk_send_and_check_auth_rule_request, TestNode
from plenum.common.request import Request
from plenum.common.types import f
from plenum.test.node_catchup.helper import waitNodeDataEquality

from plenum.test.helper import assertEquality
from plenum.test.test_node import checkNodesConnected, ensure_node_disconnected
from stp_core.loop.eventually import eventually


@pytest.fixture(scope='module')
def fees():
    return {NYM_FEES_ALIAS: 0, XFER_PUBLIC_FEES_ALIAS: 0}


@pytest.fixture()
def addresses(helpers):
    return helpers.wallet.create_new_addresses(4)


@pytest.fixture()
def mint_tokens(helpers, addresses):
    outputs = [{ADDRESS: addresses[0], AMOUNT: 1000}]
    return helpers.general.do_mint(outputs)


@pytest.fixture(scope="module")
def tconf(tconf):
    old_version_matching = tconf.INDY_VERSION_MATCHING
    tconf.INDY_VERSION_MATCHING = {"1.1.50": "1.0.0"}
    yield tconf
    tconf.INDY_VERSION_MATCHING = old_version_matching


@pytest.fixture(scope='module')
def valid_upgrade(nodeSetWithIntegratedTokenPlugin, tconf):
    schedule = {}
    unow = datetime.utcnow().replace(tzinfo=dateutil.tz.tzutc())
    startAt = unow + timedelta(seconds=30000000)
    acceptableDiff = tconf.MinSepBetweenNodeUpgrades + 1
    for n in nodeSetWithIntegratedTokenPlugin[0].poolManager.nodeIds:
        schedule[n] = datetime.isoformat(startAt)
        startAt = startAt + timedelta(seconds=acceptableDiff + 3)

    return dict(name='upgrade', version="10000.10.10",
                action=START, schedule=schedule, timeout=1,
                package=None,
                sha256='db34a72a90d026dae49c3b3f0436c8d3963476c77468ad955845a1ccf7b03f55')


def send_node_upgrades(nodes, version, looper, count=None):
    if count is None:
        count = len(nodes)
    last_ordered = nodes[0].master_last_ordered_3PC[1]
    for node in nodes[:count]:
        op = {
            TXN_TYPE: NODE_UPGRADE,
            DATA: {
                ACTION: COMPLETE,
                VERSION: version
            }
        }
        op[f.SIG.nm] = node.wallet.signMsg(op[DATA])

        request = node.wallet.signRequest(
            Request(operation=op, protocolVersion=CURRENT_PROTOCOL_VERSION))

        node.startedProcessingReq(request.key, node.nodestack.name)
        node.send(request)
        looper.run(eventually(lambda: assertEquality(node.master_last_ordered_3PC[1],
                                                     last_ordered + 1)))
        last_ordered += 1


def test_state_recovery_with_xfer(looper, tconf, tdir,
                                  sdk_pool_handle,
                                  sdk_wallet_trustee,
                                  allPluginsPath,
                                  do_post_node_creation,
                                  nodeSetWithIntegratedTokenPlugin,
                                  helpers,
                                  valid_upgrade,
                                  mint_tokens,
                                  addresses,
                                  fees_set, fees,
                                  monkeypatch):
    version1 = "1.1.50"
    version2 = "1.1.88"
    current_amount = get_amount_from_token_txn(mint_tokens)
    seq_no = 1
    node_set = nodeSetWithIntegratedTokenPlugin

    current_amount, seq_no, _ = send_and_check_nym_with_fees(helpers, fees_set, seq_no, looper, addresses,
                                                             current_amount)
    # send POOL_UPGRADE to write in a ledger
    last_ordered = node_set[0].master_last_ordered_3PC[1]
    sdk_ensure_upgrade_sent(looper, sdk_pool_handle, sdk_wallet_trustee,
                            valid_upgrade)
    looper.run(eventually(lambda: assertEquality(node_set[0].master_last_ordered_3PC[1],
                                                 last_ordered + 1)))

    send_node_upgrades(node_set, version1, looper)
    for n in node_set:
        handler = n.write_manager.request_handlers.get(XFER_PUBLIC)[0]
        handler_for_1_0_0 = n.write_manager._request_handlers_with_version.get((XFER_PUBLIC, "1.0.0"))[0]
        monkeypatch.setattr(handler, 'update_state',
                            handler_for_1_0_0.update_state)

    current_amount, seq_no, _ = send_and_check_transfer(helpers, [addresses[0], addresses[1]], fees_set, looper,
                                                        current_amount, seq_no,
                                                        transfer_summ=current_amount)
    send_node_upgrades(node_set, version2, looper)
    monkeypatch.undo()
    current_amount, seq_no, _ = send_and_check_transfer(helpers, [addresses[1], addresses[0]], fees_set, looper,
                                                        current_amount, seq_no,
                                                        transfer_summ=current_amount)

    node_to_stop = node_set[-1]
    state_db_pathes = [state._kv.db_path
                       for state in node_to_stop.states.values()]
    node_to_stop.cleanupOnStopping = False
    node_to_stop.stop()
    looper.removeProdable(node_to_stop)
    ensure_node_disconnected(looper, node_to_stop, node_set[:-1])

    for path in state_db_pathes:
        shutil.rmtree(path)
    config_helper = NodeConfigHelper(node_to_stop.name, tconf, chroot=tdir)
    restarted_node = TestNode(
        node_to_stop.name,
        config_helper=config_helper,
        config=tconf,
        pluginPaths=allPluginsPath,
        ha=node_to_stop.nodestack.ha,
        cliha=node_to_stop.clientstack.ha)
    do_post_node_creation(restarted_node)

    looper.add(restarted_node)
    node_set[-1] = restarted_node

    looper.run(checkNodesConnected(node_set))
    waitNodeDataEquality(looper, restarted_node, *node_set[:-1], exclude_from_check=['check_last_ordered_3pc_backup'])
    current_amount, seq_no, _ = send_and_check_transfer(helpers, [addresses[0], addresses[1]], {}, looper,
                                                        current_amount, seq_no,
                                                        transfer_summ=1)
    waitNodeDataEquality(looper, restarted_node, *node_set[:-1], exclude_from_check=['check_last_ordered_3pc_backup'])
