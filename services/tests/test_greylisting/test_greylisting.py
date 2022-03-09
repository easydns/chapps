"""Tests for greylisting service"""
import pytest
from smtplib import SMTP, SMTPRecipientsRefused
import logging

from chapps.tests.test_policy.conftest import clear_redis_grl, populate_redis_grl
from services.tests.conftest import known_sender


def test_chapps_grl_first_attempt_denied(
    caplog,
    clear_redis_grl,
    chapps_grl_service,
    known_sender,
    grl_test_recipients,
    grl_test_message_factory,
):
    """
    GIVEN a new email delivery attempt, for an unrecognized tuple
    WHEN  presented for delivery
    THEN  it should be denied
    """
    caplog.set_level(logging.DEBUG)
    message = grl_test_message_factory(known_sender, grl_test_recipients)
    with SMTP("127.0.0.1") as smtp:
        with pytest.raises(SMTPRecipientsRefused):
            assert smtp.sendmail(known_sender, grl_test_recipients, message)


def test_chapps_grl_acceptance_after_deferral(
    caplog,
    chapps_grl_service_with_tuple,
    known_sender,
    grl_test_recipients,
    grl_test_message_factory,
):
    """
    GIVEN an email is being retried after deferral (the tuple has been seen)
    WHEN  presented for delivery
    THEN  it should be accepted (using DUNNO to allow other filters)
    """
    caplog.set_level(logging.DEBUG)
    message = grl_test_message_factory(known_sender, grl_test_recipients)
    with SMTP("127.0.0.1") as smtp:
        result = smtp.sendmail(known_sender, grl_test_recipients, message)
    assert True  # email was accepted


def test_chapps_grl_accept_emails_from_proven_clients(
    caplog,
    chapps_grl_service_with_tally,
    known_sender,
    grl_test_recipients,
    grl_test_message_factory,
):
    """
    GIVEN a new email, but from a recognized-reliable client (source IP)
    WHEN  presented for delivery
    THEN  it should be accepted (using DUNNO to allow other filters)
    """
    caplog.set_level(logging.DEBUG)
    message = grl_test_message_factory(known_sender, grl_test_recipients)
    with SMTP("127.0.0.1") as smtp:
        result = smtp.sendmail(known_sender, grl_test_recipients, message)
    assert True  # if we get here w/o error, the email was accepted
