"""fixtures for testing chapps.switchboard"""

from unittest.mock import Mock, AsyncMock
import pytest
from chapps.policy import GreylistingPolicy
from chapps.signals import CallableExhausted
from chapps.tests.conftest import ErrorAfter,_unique_instance
from chapps.tests.test_util.conftest import postfix_policy_request_payload
from chapps.tests.test_config.conftest import (
    chapps_mock_env,
    chapps_mock_config,
    chapps_mock_cfg_path,
    chapps_mock_config_file,
)
from chapps.tests.test_policy.conftest import (
    testing_policy,
    testing_policy_grl,
    populate_redis_grl,
    unique_instance,
    mock_client_tally,
)


@pytest.fixture
def mock_reader_ok(postfix_policy_request_payload):
    mock = AsyncMock()
    deadbeef = "beefdead"
    unique_instance = _unique_instance(deadbeef)
    mock.readuntil = AsyncMock(
        side_effect=[
            postfix_policy_request_payload(
                "somebody@chapps.io", None, unique_instance()
            ),
            postfix_policy_request_payload(
                "ccullen@easydns.com", None, unique_instance()
            ),
            CallableExhausted,
        ]
    )
    return mock


@pytest.fixture
def mock_reader_sda_auth(postfix_policy_request_payload):
    mock = AsyncMock()
    deadbeef = "beadfeed"
    unique_instance = _unique_instance(deadbeef)
    mock.readuntil = AsyncMock(
        side_effect=[
            postfix_policy_request_payload(
                "caleb@chapps.io", sasl_username="ccullen@easydns.com", ccert_subject=""
            ),
            CallableExhausted,
        ]
    )
    return mock


@pytest.fixture
def mock_reader_sda_unauth(postfix_policy_request_payload):
    mock = AsyncMock()
    deadbeef = "beadfade"
    unique_instance = _unique_instance(deadbeef)
    mock.readuntil = AsyncMock(
        side_effect=[
            postfix_policy_request_payload(
                "unauth@easydns.com",
                sasl_username="somebody@chapps.io",
                ccert_subject="",
            ),
            CallableExhausted,
        ]
    )
    return mock


@pytest.fixture
def grl_reader_too_fast(postfix_policy_request_payload):
    mock = AsyncMock()
    mock.readuntil = AsyncMock(
        side_effect=[
            postfix_policy_request_payload("somebody@chapps.io"),
            postfix_policy_request_payload("somebody@chapps.io"),
            CallableExhausted,
        ]
    )
    return mock


@pytest.fixture
def grl_reader_recognized(postfix_policy_request_payload, populate_redis_grl):
    sender = "somebody@chapps.io"
    pprp = postfix_policy_request_payload(sender)
    populate_redis_grl(GreylistingPolicy._fmtkey("10.10.10.10", sender, "bar@foo.tld"))
    mock = AsyncMock()
    mock.readuntil = AsyncMock(side_effect=[pprp, CallableExhausted])
    return mock


@pytest.fixture
def grl_reader_with_tally(
    postfix_policy_request_payload, populate_redis_grl, mock_client_tally
):
    sender = "somebody@chapps.io"
    pprp = postfix_policy_request_payload(sender)
    tally = {GreylistingPolicy._fmtkey("10.10.10.10"): mock_client_tally(10)}
    populate_redis_grl(
        GreylistingPolicy._fmtkey("10.10.10.10", "someschmo@chapps.io", "bar@foo.tld"),
        tally,
    )
    mock = AsyncMock()
    mock.readuntil = AsyncMock(side_effect=[pprp, CallableExhausted])
    return mock


@pytest.fixture
def mock_reader_rej(postfix_policy_request_payload):
    mock = AsyncMock()
    mock.readuntil = AsyncMock(
        side_effect=[
            postfix_policy_request_payload("overquota@chapps.io"),
            CallableExhausted,
        ]
    )
    return mock


@pytest.fixture
def unique_instance():
    return _unique_instance()


@pytest.fixture
def mock_reader_factory(unique_instance, postfix_policy_request_payload):
    def mock_reader(sender="somebody@chapps.io"):
        pprp = postfix_policy_request_payload(sender, None, unique_instance())
        mock = AsyncMock()
        mock.readuntil = AsyncMock(side_effect=[pprp, CallableExhausted])
        return mock

    return mock_reader


@pytest.fixture
def mock_writer():
    mock = Mock()
    mock.write = Mock(return_value=None)
    return mock


@pytest.fixture
def mock_exc_raising_writer():
    mock = Mock()
    mock.write = Mock(side_effect=Exception("A test exception."))
    return mock
