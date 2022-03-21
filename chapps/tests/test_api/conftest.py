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
)
import chapps.config
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
    cfg = chapps.config.CHAPPSConfig()
    with monkeypatch.context() as m:
        m.setattr(chapps.config, "config", cfg)
        from chapps.rest.api import api

        client = TestClient(api)
        yield client