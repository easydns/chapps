"""Tests for inbound multi service"""
import logging
from smtplib import SMTP  # , SMTPRecipientsRefused

# import pytest
import time

SLEEPTIME = 0.5


class Test_IBM_Greylisting_HELOWL:
    def test_whitelist(
        self,
        caplog,
        clear_redis_grl,
        helo_ibm_service,
        known_sender,
        grl_test_recipients,
        grl_test_message_factory,
        mail_echo_file,
    ):
        """
        GIVEN a new email delivery attempt, for an unrecognized tuple
        WHEN  its HELO client is whitelisted
        THEN  it should be forwarded without an SPF header
        """
        caplog.set_level(logging.DEBUG)
        message = grl_test_message_factory(known_sender, grl_test_recipients)
        with SMTP("127.0.0.1") as smtp:
            result = smtp.sendmail(known_sender, grl_test_recipients, message)
        time.sleep(SLEEPTIME)
        mail_lines = list(mail_echo_file)
        assert "Received-SPF" not in mail_lines


# class Test_IBM_SPF:
#     def test_enforcement_occurs(
#         self,
#         caplog,
#         chapps_ibm_service,
#         known_sender,
#         spf_test_recipients,
#         ibm_test_message_factory,
#     ):
#         """
#         :GIVEN: a new email for a domain enforcing SPF
#         :WHEN:  enforcement occurs
#         :THEN:  it should match the expected outcome given the testing situation

#         SPF is not meant to be tested in a live situation like this, but we
#         require at least a basic integration test, so we will simply expect
#         whatever the proper response is, which is probably `fail`.
#         """
#         caplog.set_level(logging.DEBUG)
#         message = ibm_test_message_factory(known_sender, spf_test_recipients)
#         with SMTP("127.0.0.1") as smtp:
#             with pytest.raises(
#                 SMTPRecipientsRefused, match="SPF fail - not authorized"
#             ):
#                 result = smtp.sendmail(
#                     known_sender, spf_test_recipients, message
#                 )


# class Test_IBM_SPF_and_Greylisting:
#     """Test interaction of both

#     In cases where both are enabled for a domain, messages passing SPF are also
#     greylisted autonomously by the GreylistingPolicy rather than as a special
#     request on behalf of the SPF policy, which happens for soft fails.
#     """

#     def test_passing_first_attempt_deferred(
#         self,
#         caplog,
#         clear_redis_grl,
#         chapps_ibm_service,  # no redis setup
#         spf_and_grl_recipients,
#         passing_spf_sender,
#         ibm_test_message_factory,
#     ):
#         """
#         :GIVEN: a new email delivery attempt, for an unrecognized tuple
#         :WHEN:  presented for delivery with SPF and Greylisting enforcement
#         :AND:   SPF passes
#         :THEN:  it should be deferred
#         """
#         caplog.set_level(logging.DEBUG)
#         sender = passing_spf_sender
#         recip = spf_and_grl_recipients
#         message = ibm_test_message_factory(sender, recip)
#         with SMTP("127.0.0.1") as smtp:
#             with pytest.raises(SMTPRecipientsRefused, match="4.7.1"):
#                 result = smtp.sendmail(sender, recip, message)


# class Test_IBM_No_Enforcement:
#     def test_email_is_accepted(
#         self,
#         caplog,
#         clear_redis_grl,
#         chapps_ibm_service,
#         known_sender,  # fails SPF check
#         no_enforcement_recipients,
#         ibm_test_message_factory,
#         mail_echo_file,
#     ):
#         """
#         :GIVEN: the recipient domain enforces neither SPF or Greylisting
#         :WHEN:  an email is presented for delivery
#         :THEN:  it is accepted
#         """
#         caplog.set_level(logging.DEBUG)
#         sender = known_sender
#         recip = no_enforcement_recipients
#         message = ibm_test_message_factory(sender, recip)
#         with SMTP("127.0.0.1") as smtp:
#             result = smtp.sendmail(sender, recip, message)
#         assert True
#         time.sleep(0.01)
#         mail_lines = list(mail_echo_file)
#         assert mail_lines[0][0:13] == "Received-SPF:"
