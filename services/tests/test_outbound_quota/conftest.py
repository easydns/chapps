"""Fixtures for testing chapp-service.py"""
import os
import pytest
from pytest import fixture
from chapps.tests.test_config.conftest import (
    chapps_mock_config,
    chapps_mock_cfg_path,
    _chapps_mock_config_file,
)
from chapps.tests.test_adapter.conftest import (
    _adapter_fixture,
    _database_fixture,
    _populated_database_fixture,
)
from chapps.tests.test_policy.conftest import (
    clear_redis,
    populate_redis,
    well_spaced_attempts,
    rapid_attempts,
)
from services.tests.conftest import (
    test_message_factory,
    mail_sink,
    known_sender,
    test_recipients,
)


@fixture(scope="session")
def chapps_oqp_service(
    request,
    run_services,
    mail_sink,
    chapps_mock_session,
    chapps_mock_config_file,
    populated_database_fixture,
    watcher_getter,
):
    """
    The fixtures requested above establish the mock-config, which points at the
        test database, and also populates that database.
    pytest-services watcher_getter is used to launch CHAPPS with the environment
        monkey-patched so that the mock-config will be loaded.
    """
    if run_services:
        chapps_watcher = watcher_getter(
            "./services/chapps_outbound_quota.py",
            checker=lambda: os.path.exists("/tmp/chapps_outbound_quota.pid"),
            request=request,
        )
        return chapps_watcher


@fixture(scope="session")
def unknown_sender():
    return "whoddat@chapps.io"


@fixture(scope="session")
def overquota_sender():
    return "overquota@chapps.io"


@fixture(scope="session")
def oqp_test_recipients():
    return test_recipients()


@fixture(scope="session")
def oqp_test_message_factory():
    return test_message_factory(
        "CHAPPS-OQP", "CHAPPS automated outbound quota policy service testing"
    )
