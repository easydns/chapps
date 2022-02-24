"""Tests for chapps_outbound_quota.py"""
import pytest
from smtplib import SMTP, SMTPRecipientsRefused
import logging
from services.tests.conftest import known_sender

def test_chapps_oqp( caplog, chapps_oqp_service,
                     known_sender,
                     oqp_test_recipients,
                     oqp_test_message_factory,
                     clear_redis
):
    """
    GIVEN a running CHAPPS instance configured to recognize the sender
    WHEN we send an email
    THEN we should get an acceptance response (OK or 2xx)
    """
    caplog.set_level(logging.DEBUG)
    message = oqp_test_message_factory(
        known_sender,
        oqp_test_recipients,
        # default subject is 'CHAPPS-OQP Testing'
    )

    with SMTP('127.0.0.1') as smtp:
        result = smtp.sendmail(
            known_sender,
            oqp_test_recipients,
            message
        )
    assert True # success if the email gets sent

def test_chapps_oqp_denied_unknown( caplog, chapps_oqp_service,
                                    unknown_sender,
                                    oqp_test_recipients,
                                    oqp_test_message_factory,
):
    """
    GIVEN a running CHAPPS instance which does not recognize the sender
    WHEN we attempt to send an email
    THEN we should be denied, and an exception should be raised by smtplib
    """
    caplog.set_level(logging.DEBUG)
    message = oqp_test_message_factory(
        unknown_sender,
        oqp_test_recipients,
    )
    with SMTP('127.0.0.1') as smtp:
        with pytest.raises( SMTPRecipientsRefused ):
            assert smtp.sendmail(
                unknown_sender,
                oqp_test_recipients,
                message
            )

def test_chapps_oqp_denied_overquota( caplog, chapps_oqp_service,
                                      overquota_sender,
                                      oqp_test_recipients,
                                      oqp_test_message_factory,
                                      populate_redis,
                                      well_spaced_attempts
):
    """
    GIVEN a running CHAPPS instance which does recognize the sender
    WHEN we attempt to send more emails than our quota allows
    THEN we should be denied, and an exception should be raised by smtplib
    """
    caplog.set_level(logging.DEBUG)
    message = oqp_test_message_factory(
        overquota_sender,
        oqp_test_recipients,
    )
    populate_redis( overquota_sender, 100, well_spaced_attempts(100) )
    with SMTP('127.0.0.1') as smtp:
        with pytest.raises( SMTPRecipientsRefused ):
            assert smtp.sendmail(
                overquota_sender,
                oqp_test_recipients,
                message
            )

def test_chapps_oqp_denied_spammy( caplog, chapps_oqp_service,
                                   known_sender,
                                   oqp_test_recipients,
                                   oqp_test_message_factory,
                                   populate_redis,
                                   well_spaced_attempts, rapid_attempts,
):
    """
    GIVEN a running CHAPPS instance which does recognize the sender
    WHEN we attempt to send emails really fast
    THEN we should be denied, and an exception should be raised by smtplib
    """
    caplog.set_level(logging.DEBUG)
    message = oqp_test_message_factory(
        known_sender,
        oqp_test_recipients,
    )
    attempts = well_spaced_attempts(10)
    attempts = attempts + rapid_attempts(2)
    populate_redis( known_sender, 100, attempts )
    with SMTP('127.0.0.1') as smtp:
        with pytest.raises( SMTPRecipientsRefused ):
            assert smtp.sendmail(
                known_sender,
                oqp_test_recipients,
                message
            )
