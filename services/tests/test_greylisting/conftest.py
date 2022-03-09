"""Fixtures for testing greylisting"""
import os
import pytest
import logging
from pytest import fixture

from services.tests.conftest import (
    test_message_factory,
    test_recipients,
    known_sender,
    mail_sink,
)
from chapps.tests.conftest import _redis_args_grl, _populate_redis_grl, _clear_redis

logger = logging.getLogger(__name__)


def _source_ip():
    return "127.0.0.1"


@fixture(scope="session")
def source_ip():
    return _source_ip()


@fixture(scope="session")
def grl_test_message_factory():
    return test_message_factory(
        "CHAPPS-GRL", "CHAPPS automated greylisting policy service testing"
    )


@fixture(scope="session")
def grl_test_recipients():
    return test_recipients()


@fixture(scope="session")
def chapps_grl_service(
    request,
    run_services,
    mail_sink,
    chapps_mock_session,
    chapps_mock_config_file,
    watcher_getter,
):
    """Load the greylisting service using the mock-config"""
    if run_services:
        chapps_watcher = watcher_getter(
            "./services/chapps_greylisting.py",
            checker=lambda: os.path.exists("/tmp/chapps_greylisting.pid"),
            request=request,
        )
        return chapps_watcher


@fixture(scope="session")
def chapps_grl_service_with_tuple(
    chapps_grl_service, known_sender, grl_test_recipients
):
    """Return service fixture and also setup Redis to reflect seeing the test tuple"""
    sender = known_sender
    recipient = ",".join(grl_test_recipients)
    source_ip = _source_ip()
    redis_args = _redis_args_grl(source_ip, sender, recipient)
    clear_redis = _clear_redis("grl")
    _populate_redis_grl(*redis_args)
    yield chapps_grl_service
    clear_redis()


@fixture(scope="session")
def chapps_grl_service_with_tally(chapps_grl_service, grl_test_recipients):
    """Setup Redis to reflect that this client has enough successful sends in the last 24hr to be passed without greylisting"""
    sender = "someschmo@chapps.io"
    recipient = ",".join(grl_test_recipients)
    source_ip = _source_ip()
    tally_length = 10
    redis_args = _redis_args_grl(source_ip, sender, recipient, tally_length)
    logger.warning(f"redis_args are {redis_args[0]} .. {redis_args[-1]}")
    clear_redis = _clear_redis("grl")
    _populate_redis_grl(*redis_args)
    yield chapps_grl_service
    clear_redis()
