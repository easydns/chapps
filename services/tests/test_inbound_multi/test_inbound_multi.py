"""Tests for inbound multi service"""
import pytest
from smtplib import SMTP, SMTPRecipientsRefused
import logging

from chapps.tests.test_policy.conftest import (
    clear_redis_grl,
    populate_redis_grl,
)
from services.tests.conftest import known_sender


class Test_IBM_Greylisting:
    def test_first_attempt_denied(
        self,
        caplog,
        clear_redis_grl,
        chapps_ibm_service,
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
            with pytest.raises(
                SMTPRecipientsRefused, match="temporarily stupid"
            ):
                assert smtp.sendmail(
                    known_sender, grl_test_recipients, message
                )

    def test_acceptance_after_deferral(
        self,
        caplog,
        chapps_ibm_service_with_tuples_factory,
        known_sender,
        grl_test_recipients,
        ibm_test_message_factory,
    ):
        """
        GIVEN an email is being retried after deferral (the tuple has been seen)
        WHEN  presented for delivery
        THEN  it should be accepted (using DUNNO to allow other filters)
        """
        caplog.set_level(logging.DEBUG)
        message = ibm_test_message_factory(known_sender, grl_test_recipients)
        chapps_ibm_service_with_tuples_factory([grl_test_recipients])
        with SMTP("127.0.0.1") as smtp:
            result = smtp.sendmail(known_sender, grl_test_recipients, message)
        assert True  # email was accepted

    def test_accept_emails_from_proven_clients(
        self,
        caplog,
        chapps_ibm_service_with_tally_factory,
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
        with chapps_ibm_service_with_tally_factory([grl_test_recipients]):
            message = grl_test_message_factory(
                known_sender, grl_test_recipients
            )
            with SMTP("127.0.0.1") as smtp:
                result = smtp.sendmail(
                    known_sender, grl_test_recipients, message
                )
        assert True  # if we get here w/o error, the email was accepted


class Test_IBM_SPF:
    def test_enforcement_occurs(
        self,
        caplog,
        chapps_ibm_service,
        known_sender,
        spf_test_recipients,
        ibm_test_message_factory,
    ):
        """
        :GIVEN: a new email for a domain enforcing SPF
        :WHEN:  enforcement occurs
        :THEN:  it should match the expected outcome given the testing situation

        SPF is not meant to be tested in a live situation like this, but we
        require at least a basic integration test, so we will simply expect
        whatever the proper response is, which is probably `fail`.
        """
        caplog.set_level(logging.DEBUG)
        message = ibm_test_message_factory(known_sender, spf_test_recipients)
        with SMTP("127.0.0.1") as smtp:
            with pytest.raises(
                SMTPRecipientsRefused, match="SPF fail - not authorized"
            ):
                result = smtp.sendmail(
                    known_sender, spf_test_recipients, message
                )

    def test_enforcement_passes(
        self,
        caplog,
        chapps_ibm_service_with_tally_factory,
        passing_spf_sender,
        spf_test_recipients,
        ibm_test_message_factory,
    ):
        caplog.set_level(logging.DEBUG)
        recip = spf_test_recipients
        sender = passing_spf_sender
        message = ibm_test_message_factory(sender, recip)
        with chapps_ibm_service_with_tally_factory([(sender, recip)]):
            with SMTP("127.0.0.1") as smtp:
                result = smtp.sendmail(sender, recip, message)
        assert True

    def test_enforcement_skipped(
        self,
        caplog,
        chapps_ibm_service,
        known_sender,
        no_enforcement_recipients,
        ibm_test_message_factory,
    ):
        caplog.set_level(logging.DEBUG)
        recip = no_enforcement_recipients
        sender = known_sender
        message = ibm_test_message_factory(sender, recip)
        with SMTP("127.0.0.1") as smtp:
            result = smtp.sendmail(sender, recip, message)
        assert True  # note that SPF should fail this sender


class Test_IBM_SPF_and_Greylisting:
    """Test interaction of both

    In cases where both are enabled for a domain, messages passing SPF are also
    greylisted autonomously by the GreylistingPolicy rather than as a special
    request on behalf of the SPF policy, which happens for soft fails.
    """

    def test_passing_first_attempt_deferred(
        self,
        caplog,
        clear_redis_grl,
        chapps_ibm_service,  # no redis setup
        spf_and_grl_recipients,
        passing_spf_sender,
        ibm_test_message_factory,
    ):
        """
        :GIVEN: a new email delivery attempt, for an unrecognized tuple
        :WHEN:  presented for delivery with SPF and Greylisting enforcement
        :AND:   SPF passes
        :THEN:  it should be deferred
        """
        caplog.set_level(logging.DEBUG)
        sender = passing_spf_sender
        recip = spf_and_grl_recipients
        message = ibm_test_message_factory(sender, recip)
        with SMTP("127.0.0.1") as smtp:
            with pytest.raises(SMTPRecipientsRefused, match="4.7.1"):
                result = smtp.sendmail(sender, recip, message)

    def test_accept_after_deferral(
        self,
        caplog,
        clear_redis_grl,
        chapps_ibm_service_with_tuples_factory,
        passing_spf_sender,
        spf_and_grl_recipients,
        ibm_test_message_factory,
    ):
        """
        :GIVEN: an email is being retried after deferral (the tuple has been seen)
        :WHEN:  presented for delivery and SPF still passes
        :THEN:  it should be accepted
        """
        caplog.set_level(logging.DEBUG)
        sender = passing_spf_sender
        recip = spf_and_grl_recipients
        message = ibm_test_message_factory(sender, recip)
        chapps_ibm_service_with_tuples_factory([(sender, recip)])
        with SMTP("127.0.0.1") as smtp:
            result = smtp.sendmail(sender, recip, message)
        assert True  # email was accepted

    def test_spf_failure_enforcement(
        self,
        caplog,
        clear_redis_grl,
        chapps_ibm_service_with_tally_factory,
        known_sender,  # fails SPF check
        spf_and_grl_recipients,
        ibm_test_message_factory,
    ):
        """
        :GIVEN: an email fails SPF checking
        :WHEN:  enforcing policy
        :THEN:  it should be rejected
        """
        caplog.set_level(logging.DEBUG)
        sender = known_sender
        recip = spf_and_grl_recipients
        message = ibm_test_message_factory(sender, recip)
        with chapps_ibm_service_with_tally_factory([(sender, recip)]):
            with SMTP("127.0.0.1") as smtp:
                with pytest.raises(SMTPRecipientsRefused, match="rejected"):
                    result = smtp.sendmail(sender, recip, message)


class Test_IBM_No_Enforcement:
    def test_email_is_accepted(
        self,
        caplog,
        clear_redis_grl,
        chapps_ibm_service,
        known_sender,  # fails SPF check
        no_enforcement_recipients,
        ibm_test_message_factory,
    ):
        """
        :GIVEN: the recipient domain enforces neither SPF or Greylisting
        :WHEN:  an email is presented for delivery
        :THEN:  it is accepted
        """
        caplog.set_level(logging.DEBUG)
        sender = known_sender
        recip = no_enforcement_recipients
        message = ibm_test_message_factory(sender, recip)
        with SMTP("127.0.0.1") as smtp:
            result = smtp.sendmail(sender, recip, message)
        assert True
