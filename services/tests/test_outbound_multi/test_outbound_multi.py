"""Tests for chapps_outbound_multi.py"""
import pytest
from smtplib import SMTP, SMTPRecipientsRefused
import logging
from services.tests.conftest import known_sender
from chapps.tests.test_policy.conftest import clear_redis_sda

def test_chapps_obm_sda_rej( caplog, chapps_obm_service,
                     known_sender,
                     obm_test_recipients,
                     obm_test_message_factory,
                     clear_redis, clear_redis_sda
):
    """
    GIVEN a running CHAPPS Outbound Multi instance which recognizes the sender
    WHEN  we send an email from a domain for which this sender is not authorized
    THEN  we should get an rejection message
    """
    caplog.set_level(logging.DEBUG)
    message = obm_test_message_factory(
        known_sender,
        obm_test_recipients
    )

    with SMTP('127.0.0.1') as smtp:
        with pytest.raises( SMTPRecipientsRefused ):
            assert smtp.sendmail(
                known_sender,
                obm_test_recipients,
                message
            )

def test_chapps_obm_auth_send( caplog, chapps_obm_service,
                               known_sender,
                               obm_test_recipients,
                               obm_test_message_factory,
                               clear_redis, clear_redis_sda,
                               populated_database_fixture
):
    """
    GIVEN a running CHAPPS Outbound Multi instance which recognizes the sender
    WHEN  we send an email from a domain for which this sender is not authorized
    THEN  we should get an rejection message
    """
    caplog.set_level(logging.DEBUG)
    ### Setup the sender of the test email to be authorized to send to its own domain
    userauth_queries = [ f"INSERT INTO domains ( name ) VALUES ('{known_sender.split('@')[1]}');",
                         "SELECT LAST_INSERT_ID() INTO @easydnsid;",
                         "INSERT INTO domain_user ( domain_id, user_id )"
                         f" VALUES ( @easydnsid, (SELECT id FROM users WHERE name='{known_sender}') );"
    ]
    for q in userauth_queries:
        populated_database_fixture.execute( q )
    message = obm_test_message_factory(
        known_sender,
        obm_test_recipients
    )
    ### send the test email to
    with SMTP('127.0.0.1') as smtp:
        smtp.sendmail(
            known_sender,
            obm_test_recipients,
            message
        )
    assert True # success if the email gets sent

def test_chapps_obm_denied_unknown( caplog, chapps_obm_service,
                                    unknown_sender,
                                    obm_test_recipients,
                                    obm_test_message_factory,
):
    """
    GIVEN a running CHAPPS instance which does not recognize the sender
    WHEN we attempt to send an email
    THEN we should be denied, and an exception should be raised by smtplib
    """
    caplog.set_level(logging.DEBUG)
    message = obm_test_message_factory(
        unknown_sender,
        obm_test_recipients,
    )
    with SMTP('127.0.0.1') as smtp:
        with pytest.raises( SMTPRecipientsRefused ):
            assert smtp.sendmail(
                unknown_sender,
                obm_test_recipients,
                message
            )

def test_chapps_obm_denied_overquota( caplog, chapps_obm_service,
                                      known_sender,
                                      obm_test_recipients,
                                      obm_test_message_factory,
                                      populate_redis,
                                      well_spaced_attempts
):
    """
    GIVEN a running CHAPPS instance which does recognize the sender
    WHEN we attempt to send more emails than our quota allows
    THEN we should be denied, and an exception should be raised by smtplib
    """
    caplog.set_level(logging.DEBUG)
    ### because fixtures are session-scoped, we should not have to add this user again
    message = obm_test_message_factory(
        known_sender,
        obm_test_recipients,
    )
    populate_redis( known_sender, 100, well_spaced_attempts(100) )
    with SMTP('127.0.0.1') as smtp:
        with pytest.raises( SMTPRecipientsRefused ):
            assert smtp.sendmail(
                known_sender,
                obm_test_recipients,
                message
            )

def test_chapps_obm_denied_spammy( caplog, chapps_obm_service,
                                   known_sender,
                                   obm_test_recipients,
                                   obm_test_message_factory,
                                   populate_redis,
                                   well_spaced_attempts, rapid_attempts,
):
    """
    GIVEN a running CHAPPS instance which does recognize the sender
    WHEN we attempt to send emails really fast
    THEN we should be denied, and an exception should be raised by smtplib
    """
    caplog.set_level(logging.DEBUG)
    message = obm_test_message_factory(
        known_sender,
        obm_test_recipients,
    )
    attempts = well_spaced_attempts(10)
    attempts = attempts + rapid_attempts(2)
    populate_redis( known_sender, 100, attempts )
    with SMTP('127.0.0.1') as smtp:
        with pytest.raises( SMTPRecipientsRefused ):
            assert smtp.sendmail(
                known_sender,
                obm_test_recipients,
                message
            )
