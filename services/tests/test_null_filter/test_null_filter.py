"""Tests for null-filter.py
   a side-project related to Postfix content filtering
"""
import pytest
from smtplib import SMTP, SMTPRecipientsRefused

class Test_null_filter():
    """Tests of the null-filter script, a content filter which should do nothing"""
    def test_null_filter( null_filter_service,
                          known_sender, nlf_test_recipients, nlf_test_message_factory ):
        """
        GIVEN an arbitrary email message
        WHEN  that message is sent to the filter
        THEN  the same message should be written by the filter, on its output socket
        """
        email = nlf_test_message_factory( known_sender, nlf_test_recipients, )
        with SMTP('127.0.0.1') as smtp:
            result = smtp.sendmail(
                known_sender,
                nlf_test_recipients,
                email
            )
        assert True
