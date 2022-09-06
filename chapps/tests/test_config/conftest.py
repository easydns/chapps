"""fixtures for CHAPPS config testing"""

from pathlib import Path
import configparser
import pytest

DEFAULT_CHAPPS_TEST_CONFIG = "etc/chapps/chapps_test.ini"
DEFAULT_CHAPPS_MOCK_CONFIG = "etc/chapps/chapps_mock.ini"
DEFAULT_CHAPPS_NULL_CONFIG = "etc/chapps/chapps_null.ini"  # null-user
DEFAULT_CHAPPS_SENTINEL_CONFIG = "etc/chapps/chapps_sentinel.ini"
DEFAULT_CHAPPS_TEST_DB_HOST = "localhost"
DEFAULT_CHAPPS_TEST_DB_NAME = "chapps_test"
DEFAULT_CHAPPS_TEST_DB_USER = "chapps_test"
DEFAULT_CHAPPS_TEST_DB_PASS = "chapps_test"


@pytest.fixture(scope="session", autouse=True)
def chapps_remove_testing_config_files():
    config_dir = Path(DEFAULT_CHAPPS_TEST_CONFIG).parent
    for f in config_dir.glob("*.ini"):
        f.unlink()
    yield
    # for f in config_dir.glob("*.ini"):
    #     f.unlink()


@pytest.fixture(scope="session")
def chapps_test_cfg_path():
    return DEFAULT_CHAPPS_TEST_CONFIG


@pytest.fixture(scope="session")
def chapps_mock_cfg_path():
    return DEFAULT_CHAPPS_MOCK_CONFIG


@pytest.fixture(scope="session")
def chapps_null_cfg_path():
    return DEFAULT_CHAPPS_NULL_CONFIG


@pytest.fixture(scope="session")
def chapps_sentinel_cfg_path():
    return DEFAULT_CHAPPS_SENTINEL_CONFIG


@pytest.fixture
def chapps_test_env(monkeypatch, chapps_test_cfg_path):
    monkeypatch.setenv("CHAPPS_CONFIG", chapps_test_cfg_path)
    return chapps_test_cfg_path


@pytest.fixture
def chapps_mock_env(monkeypatch, chapps_mock_cfg_path):
    monkeypatch.setenv("CHAPPS_CONFIG", chapps_mock_cfg_path)
    return chapps_mock_cfg_path


@pytest.fixture
def chapps_null_env(monkeypatch, chapps_null_cfg_path):
    monkeypatch.setenv("CHAPPS_CONFIG", chapps_null_cfg_path)
    return chapps_null_cfg_path


@pytest.fixture
def chapps_sentinel_env(monkeypatch, chapps_sentinel_cfg_path):
    monkeypatch.setenv("CHAPPS_CONFIG", chapps_sentinel_cfg_path)
    return chapps_sentinel_cfg_path


def _chapps_mock_config():
    """Some settings are intentionally left out; their defaults shall prevail"""
    cp = configparser.ConfigParser(interpolation=None)
    cp["CHAPPS"] = {"payload_encoding": "UTF-8", "require_user_key": False}
    cp["PolicyConfigAdapter"] = {
        "adapter": "mysql",
        "db_name": "chapps_test",
        "db_user": "chapps_test",
        "db_pass": "screwy%pass${word}",
    }
    cp["OutboundQuotaPolicy"] = {
        "min_delta": 2,
        "margin": 50.0,
        "counting_recipients": False,
        "rejection_message": "554 Rejected because I said so.",
    }
    cp["GreylistingPolicy"] = {
        "rejection_message": "DEFER_IF_PERMIT Service temporarily stupid"
    }
    cp["SPFEnforcementPolicy"] = {
        "whitelist": ["chapps.io"],
        "adapter": "None",
    }
    cp["Redis"] = {
        "sentinel_master": "",
        "server": "127.0.0.1",
        "port": "6379",
    }
    return cp


@pytest.fixture(scope="session")
def chapps_mock_config():
    return _chapps_mock_config()


@pytest.fixture(scope="session")
def chapps_null_user_config():
    """Some settings are intentionally left out; their defaults shall prevail"""
    cp = configparser.ConfigParser(interpolation=None)
    cp["CHAPPS"] = {
        "payload_encoding": "UTF-8",
        "require_user_key": True,
        "user_key": "sasl_username",
    }
    cp["PolicyConfigAdapter"] = {
        "adapter": "mysql",
        "db_name": "chapps_test",
        "db_user": "chapps_test",
        "db_pass": "screwy%pass${word}",
    }
    cp["OutboundQuotaPolicy"] = {
        "min_delta": 2,
        "margin": 50.0,
        "counting_recipients": False,
        "rejection_message": "554 Rejected because I said so.",
    }
    cp["GreylistingPolicy"] = {
        "rejection_message": "DEFER_IF_PERMIT Service temporarily stupid"
    }
    cp["SPFEnforcementPolicy"] = {
        "whitelist": ["chapps.io"],
        "adapter": "None",
    }
    cp["Redis"] = {
        "sentinel_master": "",
        "server": "127.0.0.1",
        "port": "6379",
    }
    return cp


@pytest.fixture(scope="session")
def chapps_sentinel_config():
    """Some settings are intentionally left out; their defaults shall prevail"""
    cp = configparser.ConfigParser(interpolation=None)
    cp["CHAPPS"] = {"payload_encoding": "UTF-8"}
    cp["PolicyConfigAdapter"] = {
        "adapter": "mysql",
        "db_name": "chapps_test",
        "db_user": "chapps_test",
        "db_pass": "screwy%pass${word}",
    }
    cp["OutboundQuotaPolicy"] = {
        "min_delta": 2,
        "margin": 50.0,
        "counting_recipients": False,
        "rejection_message": "554 Rejected because I said so.",
    }
    cp["GreylistingPolicy"] = {
        "rejection_message": "DEFER_IF_PERMIT Service temporarily stupid"
    }
    cp["SPFEnforcementPolicy"] = {
        "whitelist": ["chapps.io"],
        "adapter": "None",
    }
    cp["Redis"] = {
        "sentinel_servers": "10.5.12.201:26379 10.5.12.202:26379 10.5.12.203:26379",
        "sentinel_dataset": "redis-easymail",
        "server": "127.0.0.1",
        "port": "6379",
    }
    return cp


@pytest.fixture(scope="session")
def chapps_mock_config_file(chapps_mock_config, chapps_mock_cfg_path):
    yield from _chapps_mock_config_file(
        chapps_mock_config, chapps_mock_cfg_path
    )


@pytest.fixture(scope="session")
def chapps_null_config_file(chapps_null_user_config, chapps_null_cfg_path):
    yield from _chapps_mock_config_file(
        chapps_null_user_config, chapps_null_cfg_path
    )


@pytest.fixture(scope="session")
def chapps_sentinel_config_file(
    chapps_sentinel_config, chapps_sentinel_cfg_path
):
    yield from _chapps_mock_config_file(
        chapps_sentinel_config, chapps_sentinel_cfg_path
    )


def _chapps_mock_config_file(some_config, some_cfg_path):
    cfg = Path(some_cfg_path)
    with cfg.open("w") as cfg_file:
        some_config.write(cfg_file)
    yield cfg
    # cfg.unlink(True) # comment this out to be able to look at the mock config on disk
