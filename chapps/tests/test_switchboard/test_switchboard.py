"""tests for chapps.switchboard"""

import pytest
from unittest.mock import Mock
import logging
from unittest.mock import patch
from chapps.switchboard import (
    RequestHandler,
    OutboundQuotaHandler,
    GreylistingHandler,
    SenderDomainAuthHandler,
    OutboundMultipolicyHandler,
)
from chapps.policy import OutboundQuotaPolicy
from chapps.signals import CallableExhausted
from chapps.outbound import OutboundPPR
from chapps.tests.test_adapter.conftest import (
    base_adapter_fixture,
    finalizing_pcadapter,
    database_fixture,
    populated_database_fixture,
)
from chapps.tests.test_policy.conftest import (
    clear_redis,
    clear_redis_grl,
    clear_redis_sda,
    testing_policy_sda,
    null_sender_policy_sda,
)

pytestmark = pytest.mark.order(-2)


@pytest.mark.asyncio
class Test_OutboundQuotaHandler:
    """Tests for the OQP switchboard"""

    async def test_exception_handling(
        self,
        caplog,
        clear_redis,
        testing_policy,
        mock_reader_ok,
        mock_exc_raising_writer,
        populated_database_fixture,
    ):
        """
        Verify that if an exception is raised, it will be handled by logging
        """
        caplog.set_level(logging.DEBUG)
        handle_policy_request = OutboundQuotaHandler(
            testing_policy
        ).async_policy_handler()
        _ = await handle_policy_request(
            mock_reader_ok, mock_exc_raising_writer
        )
        assert any(
            "Exception raised trying to send" in rec.message
            for rec in caplog.records
        )

    async def test_handle_policy_request(
        self,
        clear_redis,
        testing_policy,
        mock_reader_ok,
        mock_writer,
        populated_database_fixture,
    ):
        """
        Verify that when a permissible request is received, it gets an OK.
        """
        handle_policy_request = OutboundQuotaHandler(
            testing_policy
        ).async_policy_handler()
        with pytest.raises(CallableExhausted):
            _ = await handle_policy_request(mock_reader_ok, mock_writer)
        mock_reader_ok.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(b"action=DUNNO\n\n")

    async def test_handle_policy_rejection(
        self, caplog, testing_policy, mock_reader_rej, mock_writer
    ):
        """
        Verify that over-quota senders' requests are denied
        """
        caplog.set_level(logging.DEBUG)
        handle_policy_request = OutboundQuotaHandler(
            testing_policy
        ).async_policy_handler()
        with pytest.raises(CallableExhausted):
            _ = await handle_policy_request(mock_reader_rej, mock_writer)
        assert mock_reader_rej.readuntil.call_args.args[0] == b"\n\n"
        # mock_writer.write.assert_called_with( b'554 Rejected - outbound quota fulfilled\n\n' )
        assert (
            mock_writer.write.call_args.args[0][0:11] == b"action=554 "
            or mock_writer.write.call_args.args[0][0:14] == b"action=REJECT "
        ) and mock_writer.write.call_args.args[0][-2:] == b"\n\n"

    async def test_default_policy(self, mock_reader_ok, mock_writer):
        """
        Verify that when no policy is supplied, a default policy is instantiated
        """
        handler = OutboundQuotaHandler()
        assert handler.policy is not None
        assert type(handler.policy) == OutboundQuotaPolicy


@pytest.mark.asyncio
class Test_GreylistingHandler:
    """Tests of the Greylisting switchboard"""

    async def test_handle_new_tuple(
        self,
        clear_redis_grl,
        testing_policy_grl,
        grl_reader_recognized,
        populated_database_fixture,
        mock_writer,
    ):
        """
        GIVEN an email attempt from a new tuple
        WHEN  the client isn't auto-allowed
        THEN  reject the email
        """
        clear_redis_grl()
        handle_greylist_request = GreylistingHandler(
            testing_policy_grl
        ).async_policy_handler()
        reader_grl = grl_reader_recognized
        with pytest.raises(CallableExhausted):
            await handle_greylist_request(reader_grl, mock_writer)
        reader_grl.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            b"action=DEFER_IF_PERMIT Service temporarily stupid\n\n"
        )

    async def test_handle_retry_too_fast(
        self,
        clear_redis_grl,
        testing_policy_grl,
        grl_reader_too_fast,
        mock_writer,
    ):
        """
        GIVEN two back-to-back attempts with the same tuple
        WHEN  the two attempts are two close together
        THEN  reject the email
        """
        handle_greylist_request = GreylistingHandler(
            testing_policy_grl
        ).async_policy_handler()
        grl_reader = grl_reader_too_fast
        with pytest.raises(CallableExhausted):
            await handle_greylist_request(grl_reader, mock_writer)
        grl_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            b"action=DEFER_IF_PERMIT Service temporarily stupid\n\n"
        )

    async def test_handle_recognized_tuple(
        self,
        clear_redis_grl,
        testing_policy_grl,
        grl_reader_recognized,
        mock_writer,
    ):
        """
        GIVEN an email delivery attempt
        WHEN  the tuple is recognized
        THEN  return DUNNO to allow other filters to block it; it will be accepted by default
        """
        handle_greylist_request = GreylistingHandler(
            testing_policy_grl
        ).async_policy_handler()
        grl_reader = grl_reader_recognized
        with pytest.raises(CallableExhausted):
            await handle_greylist_request(grl_reader, mock_writer)
        grl_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(b"action=DUNNO\n\n")

    async def test_handle_allowed_client(
        self,
        clear_redis_grl,
        testing_policy_grl,
        grl_reader_with_tally,
        mock_writer,
    ):
        """
        GIVEN an email delivery attempt
        WHEN  the client is recognized as a reliable sender
        THEN  return DUNNO to allow other filters to block it; it will be accepted by default
        """
        handle_greylist_request = GreylistingHandler(
            testing_policy_grl
        ).async_policy_handler()
        grl_reader = grl_reader_with_tally
        with pytest.raises(CallableExhausted):
            await handle_greylist_request(grl_reader, mock_writer)
        grl_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(b"action=DUNNO\n\n")


@pytest.mark.asyncio
class Test_SenderDomainAuthHandler:
    """Tests of the SenderDomainAuth handler"""

    async def test_handle_authorized_user(
        self,
        clear_redis_sda,
        testing_policy_sda,
        mock_reader_sda_auth,
        mock_writer,
    ):
        """
        GIVEN an email attempt from an authorized user
        WHEN  asked for a response
        THEN  return the acceptance message
        """
        handle_sda_request = SenderDomainAuthHandler(
            testing_policy_sda
        ).async_policy_handler()
        with pytest.raises(CallableExhausted):
            await handle_sda_request(mock_reader_sda_auth, mock_writer)
        mock_reader_sda_auth.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(b"action=DUNNO\n\n")

    async def test_handle_unauth_user(
        self,
        clear_redis_sda,
        testing_policy_sda,
        mock_reader_sda_unauth,
        mock_writer,
    ):
        """
        GIVEN an email attempt from an UNauthorized user
        WHEN  asked for a response
        THEN  return the rejection message
        """
        handle_sda_request = SenderDomainAuthHandler(
            testing_policy_sda
        ).async_policy_handler()
        with pytest.raises(CallableExhausted):
            await handle_sda_request(mock_reader_sda_unauth, mock_writer)
        mock_reader_sda_unauth.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            b"action=REJECT Rejected - not allowed to send mail from this domain\n\n"
        )


@pytest.mark.asyncio
class Test_OutboundMultipolicyHandler:
    async def test_authed_user_gets_quota_check(
        self,
        monkeypatch,
        clear_redis,
        clear_redis_sda,
        testing_policy,
        testing_policy_sda,
        mock_reader_sda_auth,
        mock_writer,
        populated_database_fixture,
        database_fixture,
        finalizing_pcadapter,
        base_adapter_fixture,
    ):
        """
        Verify that a successful SDA test cascades to a quota test
        """
        with pytest.raises(CallableExhausted):
            with monkeypatch.context() as m:
                mock_apr = Mock(return_value=True)
                m.setattr(testing_policy, "approve_policy_request", mock_apr)
                handler = OutboundMultipolicyHandler(
                    [testing_policy_sda, testing_policy]
                )
                handle_policy_request = handler.async_policy_handler()
                await handle_policy_request(mock_reader_sda_auth, mock_writer)
        mock_apr.assert_called_once()

    async def test_missing_user_key(
        self,
        clear_redis,
        clear_redis_sda,
        null_user_oq_policy,
        null_user_sda_policy,
        mock_reader_factory,
        mock_writer,
        populated_database_fixture,
    ):
        """
        :GIVEN: that we require a user-key
        :WHEN: a PPR is evaluated which has no value for the user-key
        :THEN: the email is rejected and the `no_user_key_response` is returned
        """
        OutboundPPR.clear_memoized_routines()
        no_sasl_reader = mock_reader_factory(
            sasl_username="", ccert_subject=""
        )
        handler = OutboundMultipolicyHandler(
            [null_user_sda_policy, null_user_oq_policy]
        )
        handle_policy_request = handler.async_policy_handler()
        with pytest.raises(CallableExhausted):
            # with monkeypatch.context() as m:
            # mock_apr = Mock(return_value=True)
            # m.setattr(testing_policy, "approve_policy_request", mock_apr)
            await handle_policy_request(no_sasl_reader, mock_writer)
        # meaning the AuthenticationFailureException was handled
        mock_writer.write.assert_called_with(
            bytes(
                "action="
                + handler.config.chapps.no_user_key_response
                + "\n\n",
                handler.config.chapps.payload_encoding,
            )
        )

    async def test_handle_null_sender(
        self,
        null_sender_policy_sda,
        testing_policy,
        mock_reader_sda_auth,
        mock_writer,
    ):
        handler = OutboundMultipolicyHandler(
            [null_sender_policy_sda, testing_policy]
        )
        handle_policy_request = handler.async_policy_handler()
        with pytest.raises(CallableExhausted):
            await handle_policy_request(mock_reader_sda_auth, mock_writer)
        mock_writer.write.assert_called_once()  # if it was called, we handled the exception raised by null_sender_policy_sda

    async def test_reject_null_sender(
        self,
        null_sender_policy_sda,
        testing_policy,
        mock_reader_sda_auth,
        mock_writer,
    ):
        handler = OutboundMultipolicyHandler(
            [null_sender_policy_sda, testing_policy]
        )
        handle_policy_request = handler.async_policy_handler()
        with pytest.raises(CallableExhausted):
            await handle_policy_request(mock_reader_sda_auth, mock_writer)
        mock_writer.write.assert_called_with(
            b"action=REJECT Rejected - not allowed to send mail from this domain\n\n"
        )  # the SDA rejection message b/c using SDA policy

    async def test_unauthed_user_gets_rejected(
        self,
        monkeypatch,
        clear_redis,
        clear_redis_sda,
        testing_policy,
        testing_policy_sda,
        mock_reader_sda_unauth,
        mock_writer,
        populated_database_fixture,
        database_fixture,
        finalizing_pcadapter,
        base_adapter_fixture,
    ):
        """
        Verify that unsuccessful SDA tests prevent quota testing, and immediately reject the email
        """
        with pytest.raises(CallableExhausted):
            with monkeypatch.context() as m:
                mock_apr = Mock(return_value=True)
                m.setattr(testing_policy, "approve_policy_request", mock_apr)
                handler = OutboundMultipolicyHandler(
                    [testing_policy_sda, testing_policy]
                )
                handle_policy_request = handler.async_policy_handler()
                await handle_policy_request(
                    mock_reader_sda_unauth, mock_writer
                )
        mock_apr.assert_not_called()
