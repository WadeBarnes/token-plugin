import pytest

from plenum.test.conftest import getValueFromModule

from sovtokenfees.test.conftest import MintStrategy, IOAddressesStatic
from sovtokenfees.test.helper import InputsStrategy, OutputsStrategy


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "io_border(int): mark test to use specific inputs/outputs addresses division"
    )
    config.addinivalue_line(
        "markers", "nym_fee(int): mark test to use specific nym fee value"
    )


@pytest.fixture
def addresses_num(request):
    return getValueFromModule(request, "ADDRESSES_NUM", 4)


@pytest.fixture
def mint_strategy():
    return MintStrategy.all_equal


@pytest.fixture(params=InputsStrategy, ids=lambda x: x.name)
def inputs_strategy(request):
    return request.param


@pytest.fixture(params=OutputsStrategy, ids=lambda x: x.name)
def outputs_strategy(request):
    return request.param


@pytest.fixture
def transfer_amount():
    return 10


@pytest.fixture(
    params=[
        ([0], [0]),
        ([0], [1]),
        ([0], [1, 2]),
        ([0, 1], [2]),
        ([0, 1], [2, 3]),
        ([0, 1, 2], [1, 2, 3]),
    ], ids=lambda x: (
        "i{}_o{}"
        .format(':'.join((map(str, x[0]))), ':'.join((map(str, x[1]))))
    )
)
def io_addresses(request, addresses):
    return IOAddressesStatic(
        [addresses[i] for i in request.param[0]],
        [addresses[i] for i in request.param[1]]
    )
