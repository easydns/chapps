"""Fixtures for testing greylisting"""
import os
import pytest
import logging
import redis
from contextlib import contextmanager
from pytest import fixture

from services.tests.conftest import (
    test_message_factory,
    test_recipients,
    known_sender,
    mail_sink,
    mail_echo_file,
)
from chapps.tests.conftest import (
    _redis_args_grl,
    _populate_redis_grl,
    _clear_redis,
)
from chapps.tests.test_policy.conftest import (
    clear_redis_grl,
    populate_redis_grl,
)
from services.tests.test_greylisting.conftest import (
    _source_ip,
    source_ip,
    grl_test_message_factory,
    grl_test_recipients,
)

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def chapps_ibm_service(
    request,
    run_services,
    mail_echo_file,
    chapps_mock_session,
    chapps_mock_config_file,
    watcher_getter,
):
    if run_services:
        chapps_watcher = watcher_getter(
            "./services/chapps_inbound_multi.py",
            checker=lambda: os.path.exists("/tmp/chapps_inbound_multi.pid"),
            request=request,
        )
        return chapps_watcher


@pytest.fixture(scope="session")
def helo_ibm_service(
    request,
    run_services,
    mail_echo_file,
    chapps_helo_session,
    chapps_helo_config_file,
    watcher_getter,
):
    if run_services:
        chapps_watcher = watcher_getter(
            "./services/chapps_inbound_multi.py",
            checker=lambda: os.path.exists("/tmp/chapps_inbound_multi.pid"),
            request=request,
        )
        return chapps_watcher


@pytest.fixture(scope="session")
def chapps_ibm_service_with_tuples_factory(chapps_ibm_service, known_sender):
    return _chapps_ibm_service_with_tuples_factory(known_sender)


@pytest.fixture(scope="session")
def chapps_ibm_service_with_tally_factory(chapps_ibm_service, known_sender):
    return _chapps_ibm_service_with_tally_factory(known_sender)


def _chapps_ibm_service_with_tuples_factory(known_sender):
    source_ip = _source_ip()

    # @contextmanager
    def _srv_w_tuples(tuples):
        # clear_redis = _clear_redis("grl")
        for t in tuples:
            sender, recipients = t if type(t) == tuple else (None, t)
            sender = sender or known_sender
            recipient = ",".join(recipients)
            redis_args = _redis_args_grl(source_ip, sender, recipient)
            logger.warning(f"Populating redis with: {redis_args!r}")
            set_ts = _populate_redis_grl(*redis_args)
            rh = redis.Redis()
            ts = float(rh.get(redis_args[0]))
            logger.warning(f"Redis returns value {ts} for {redis_args[0]}")
            if ts != set_ts:
                logger.warning(
                    "Redis setting does not match what was returned by setter:"
                    f" {ts} != {set_ts}"
                )

    return _srv_w_tuples


def _chapps_ibm_service_with_tally_factory(known_sender):
    source_ip = _source_ip()

    @contextmanager
    def _srv_w_tally(tuples):
        clear_redis = _clear_redis("grl")
        tally_length = 10  # at least enough to be whitelisted
        for t in tuples:
            sender, recipients = t if type(t) == tuple else (None, t)
            sender = sender or known_sender
            recipient = ",".join(recipients)
            redis_args = _redis_args_grl(
                source_ip, sender, recipient, tally_length
            )
            _populate_redis_grl(*redis_args)
        try:
            yield None
        finally:
            clear_redis()

    return _srv_w_tally


def _spf_recipients():
    return ["someone@easydns.com"]


def _spf_and_grl_recipients():
    return ["someone@chapps.io"]


def _no_enforcement_recipients():
    return ["someone@easydns.org"]


@pytest.fixture
def passing_spf_sender():
    return "caleb@chapps.io"


@pytest.fixture
def softfail_spf_sender():
    return "caleb@moretestingdomainsforever.com"


@pytest.fixture
def spf_test_recipients():
    return _spf_recipients()


@pytest.fixture
def spf_and_grl_recipients():
    return _spf_and_grl_recipients()


@pytest.fixture
def no_enforcement_recipients():
    return _no_enforcement_recipients()


@pytest.fixture(scope="session")
def ibm_test_message_factory():
    return test_message_factory(
        "CHAPPS-IBM", "CHAPPS automated inbound multipolicy service testing"
    )
