from chapps.outbound import OutboundPPR
from chapps.config import CHAPPSConfig
from chapps.tests.test_util.conftest import (
    postfix_policy_request_payload,
    postfix_policy_request_message,
)
from pytest import fixture
from chapps.tests.test_config.conftest import (
    chapps_test_env,
    chapps_test_cfg_path,
    chapps_mock_env,
    chapps_mock_cfg_path,
    chapps_mock_config,
    chapps_mock_config_file,
)


@fixture(scope="function")
def testing_userppr(chapps_test_env, postfix_policy_request_message):
    return OutboundPPR(postfix_policy_request_message("ccullen@easydns.com"))


@fixture(scope="function")
def mocking_userppr(
        chapps_mock_env,
        chapps_mock_config_file,
        postfix_policy_request_message
):
    conf = CHAPPSConfig()
    return OutboundPPR(
        postfix_policy_request_message("ccullen@easydns.com"),
        cfg=conf
    )
