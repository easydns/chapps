import pytest
import logging
from chapps.outbound import OutboundPPR
from chapps.signals import AuthenticationFailureException
from chapps.config import CHAPPSConfig


class Test_OutboundPPR:
    """Tests of the OutboundPPR subclass, which is a PPR knowing how to discover a user for outbound"""

    def test_user_default(self, chapps_test_env, testing_userppr):
        assert type(testing_userppr) == OutboundPPR
        assert (
            testing_userppr.user == testing_userppr.sasl_username
        )  # this being the default
        assert testing_userppr.user is not None
        assert testing_userppr.user != "None"

    def test_no_user_key_no_auth(self, monkeypatch, chapps_test_env, testing_userppr):
        with monkeypatch.context() as m:
            m.setattr(testing_userppr, "sasl_username", None)
            assert type(testing_userppr) == OutboundPPR
            with pytest.raises(AuthenticationFailureException):
                assert testing_userppr.user

    def test_user_default_no_sasl(self, monkeypatch, chapps_mock_env, chapps_mock_cfg_path, mocking_userppr):
        assert chapps_mock_env == chapps_mock_cfg_path
        assert str(CHAPPSConfig.what_config_file()) == chapps_mock_cfg_path
        assert not mocking_userppr._config.require_user_key
        with monkeypatch.context() as m:
            m.setattr(mocking_userppr, "sasl_username", None)
            assert type(mocking_userppr) == OutboundPPR
            assert mocking_userppr.user == mocking_userppr.ccert_subject
            assert mocking_userppr.user is not None
            assert mocking_userppr.user != "None"

    def test_user_default_no_sasl_or_ccert(
        self, monkeypatch, chapps_mock_env, mocking_userppr
    ):
        with monkeypatch.context() as m:
            m.setattr(mocking_userppr, "sasl_username", None)
            m.setattr(mocking_userppr, "ccert_subject", None)
            assert type(mocking_userppr) == OutboundPPR
            assert mocking_userppr.user == mocking_userppr.sender
            assert mocking_userppr.user is not None
            assert mocking_userppr.user != "None"

    def test_user_default_no_sasl_ccert_or_sender(
        self, caplog, monkeypatch, chapps_mock_env, mocking_userppr
    ):
        caplog.set_level(logging.DEBUG)
        with monkeypatch.context() as m:
            m.setattr(mocking_userppr, "sasl_username", None)
            m.setattr(mocking_userppr, "ccert_subject", None)
            m.setattr(mocking_userppr, "sender", None)
            assert type(mocking_userppr) == OutboundPPR
            assert mocking_userppr.user is not None
            assert mocking_userppr.user != "None"
            assert mocking_userppr.user == mocking_userppr.client_address
            assert mocking_userppr.user == "10.10.10.10"
