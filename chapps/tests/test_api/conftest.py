import pytest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from chapps.tests.test_config.conftest import (
    chapps_mock_cfg_path,
    chapps_mock_config,
    chapps_mock_config_file,
    chapps_mock_env,
)
from chapps.tests.test_adapter.conftest import (
    finalizing_pcadapter,
    base_adapter_fixture,
    database_fixture,
    populated_database_fixture,
    populated_database_fixture_with_extras,
    populated_database_fixture_with_breakage,
)
from chapps.tests.test_util.conftest import (
    postfix_policy_request_message,
    postfix_policy_request_payload,
)
from chapps.tests.test_policy.conftest import (
    populate_redis,
    populate_redis_multi,
    populate_redis_grl,
    clear_redis,
    clear_redis_sda,
    clear_redis_grl,
    well_spaced_attempts,
    allowable_inbound_ppr,
    sda_allowable_ppr,
    sda_unauth_ppr,
    sda_auth_email_ppr,
    sda_unauth_email_ppr,
    testing_policy_sda,
    testing_policy_grl,
)
from chapps.tests.conftest import _redis_args_grl
from chapps.test_sqla_adapter.conftest import mock_chapps_config

# import chapps.config
import time


def pytest_configure():
    pytest.FIXED_TIME = 1647625876.036144


@pytest.fixture
def fixed_time(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(time, "time", Mock(return_value=pytest.FIXED_TIME))
        yield pytest.FIXED_TIME


@pytest.fixture
def testing_api_client(monkeypatch, chapps_mock_env, chapps_mock_config_file):
    import chapps.dbsession

    with monkeypatch.context() as m:
        m.setattr(
            chapps.dbsession,
            "sql_engine",
            chapps.dbsession.create_engine(
                chapps.dbsession.create_db_url(mock_chapps_config())
            ),
        )
        from chapps.rest.api import api

        client = TestClient(api)
        yield client
