import pytest
import logging
from chapps.outbound import OutboundPPR

class Test_OutboundPPR():
    """Tests of the OutboundPPR subclass, which is a PPR knowing how to discover a user for outbound"""
    def test_user_default(self, chapps_test_env, testing_userppr):
        assert type(testing_userppr) == OutboundPPR
        assert testing_userppr.user == testing_userppr.sasl_username # this being the default
        assert testing_userppr.user is not None
        assert testing_userppr.user != 'None'

    def test_user_default_no_sasl(self, monkeypatch, chapps_test_env, testing_userppr):
        with monkeypatch.context() as m:
            m.setattr( testing_userppr, 'sasl_username', None )
            assert type(testing_userppr) == OutboundPPR
            assert testing_userppr.user == testing_userppr.ccert_subject
            assert testing_userppr.user is not None
            assert testing_userppr.user != 'None'

    def test_user_default_no_sasl_or_ccert(self, monkeypatch, chapps_test_env, testing_userppr):
        with monkeypatch.context() as m:
            m.setattr( testing_userppr, 'sasl_username', None )
            m.setattr( testing_userppr, 'ccert_subject', None )
            assert type(testing_userppr) == OutboundPPR
            assert testing_userppr.user == testing_userppr.sender
            assert testing_userppr.user is not None
            assert testing_userppr.user != 'None'

    def test_user_default_no_sasl_ccert_or_sender(self, caplog, monkeypatch, chapps_test_env, testing_userppr):
        caplog.set_level(logging.DEBUG)
        with monkeypatch.context() as m:
            m.setattr( testing_userppr, 'sasl_username', None )
            m.setattr( testing_userppr, 'ccert_subject', None )
            m.setattr( testing_userppr, 'sender', None )
            assert type(testing_userppr) == OutboundPPR
            assert testing_userppr.user is not None
            assert testing_userppr.user != 'None'
            assert testing_userppr.user == testing_userppr.client_address
            assert testing_userppr.user == '10.10.10.10'
