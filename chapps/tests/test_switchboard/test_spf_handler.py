"""tests for chapps.switchboard"""

import spf
import pytest
import logging

# from unittest.mock import patch
from chapps.switchboard import SPFEnforcementHandler, InboundMultipolicyHandler
from chapps.signals import CallableExhausted
from chapps.tests.test_policy.conftest import (
    auto_spf_query,
    mock_spf_queries,
    passing_spf_query,
    softfail_spf_query,
    _auto_query_param_list,
    _auto_query_param_list_spf_plus_greylist,
    idfn,
    testing_policy_spf,
    testing_policy_grl,
)
from chapps.tests.test_adapter.conftest import (
    base_adapter_fixture,
    finalizing_pcadapter,
    database_fixture,
    populated_database_fixture,
    populated_database_fixture_with_extras,
)

pytestmark = pytest.mark.order(-3)

auto_query_param_list = _auto_query_param_list()
auto_query_param_list_spf_plus_greylist = (
    _auto_query_param_list_spf_plus_greylist()
)


@pytest.mark.asyncio
class Test_SPFEnforcementHandler:
    """This class contains tests of the SPF Enforcement Handler"""

    @pytest.mark.parametrize(
        "auto_spf_query, expected_result",
        auto_query_param_list,
        indirect=["auto_spf_query"],
        ids=idfn,
    )
    async def test_handle_policy_request(
        self,
        caplog,
        monkeypatch,
        testing_policy_spf,
        auto_spf_query,
        expected_result,
        mock_reader_factory,
        mock_writer,
        populated_database_fixture,
        clear_redis_grl,
    ):
        """
        GIVEN a particular result from the SPF checker
        WHEN  communicating with Postfix
        THEN  send the appropriate result
        This test will be parameterized to go through all possible responses
        """
        caplog.set_level(logging.DEBUG)
        handle_spf_request = SPFEnforcementHandler(
            testing_policy_spf
        ).async_policy_handler()
        mock_reader = mock_reader_factory(None, "someone@chapps.io")
        with monkeypatch.context() as m:
            m.setattr(spf, "query", auto_spf_query)
            # exercise handler
            with pytest.raises(CallableExhausted):
                await handle_spf_request(mock_reader, mock_writer)
        mock_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            f"action={expected_result}\n\n".encode("utf-8")
        )

    async def test_handle_request_on_unrecognized_domain(
        self,
        caplog,
        monkeypatch,
        testing_policy_spf,
        populated_database_fixture,
        mock_reader_factory,
        mock_writer,
    ):
        """
        :GIVEN: a recipient within an unrecognized domain
        :WHEN:  policy evaluation takes place
        :THEN:  return DUNNO rather than enforcing the policy
        """
        caplog.set_level(logging.DEBUG)
        handle_spf_request = SPFEnforcementHandler(
            testing_policy_spf
        ).async_policy_handler()
        mock_reader = mock_reader_factory()  # default recip foo@bar.tld
        with monkeypatch.context() as m:
            # exercise handler
            with pytest.raises(CallableExhausted):
                await handle_spf_request(mock_reader, mock_writer)
        mock_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            f"action=DUNNO\n\n".encode("utf-8")
        )

    async def test_handle_request_on_nonenforcing_domain(
        self,
        caplog,
        monkeypatch,
        testing_policy_spf,
        mock_reader_factory,
        mock_writer,
        populated_database_fixture_with_extras,
    ):
        """
        :GIVEN: a recipient within an unrecognized domain
        :WHEN:  policy evaluation takes place
        :THEN:  return DUNNO rather than enforcing the policy
        """
        caplog.set_level(logging.DEBUG)
        handle_spf_request = SPFEnforcementHandler(
            testing_policy_spf
        ).async_policy_handler()
        mock_reader = mock_reader_factory(None, "someguy@easydns.org")
        with monkeypatch.context() as m:
            # exercise handler
            with pytest.raises(CallableExhausted):
                await handle_spf_request(mock_reader, mock_writer)
        mock_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            f"action=DUNNO\n\n".encode("utf-8")
        )


@pytest.mark.asyncio
class Test_InboundMultipolicyHandler:
    """This class contains tests of the inbound multipolicy handler"""

    @pytest.mark.parametrize(
        "auto_spf_query, expected_result",
        auto_query_param_list,
        indirect=["auto_spf_query"],
        ids=idfn,
    )
    async def test_handle_policy_request_spf_only(
        self,
        caplog,
        monkeypatch,
        testing_policy_spf,
        testing_policy_grl,
        auto_spf_query,
        expected_result,
        mock_reader_factory,
        mock_writer,
        populated_database_fixture_with_extras,
        clear_redis_grl,
    ):
        """
        GIVEN a particular result from the SPF checker
        WHEN  communicating with Postfix
        THEN  send the appropriate result
        This test is parameterized to go through all possible responses
        """
        caplog.set_level(logging.DEBUG)
        handle_spf_request = InboundMultipolicyHandler(
            [testing_policy_spf, testing_policy_grl]
        ).async_policy_handler()
        mock_reader = mock_reader_factory(
            None, "someone@easydns.com"  # only SPF is enabled for this domain
        )
        with monkeypatch.context() as m:
            m.setattr(spf, "query", auto_spf_query)
            # exercise handler
            with pytest.raises(CallableExhausted):
                await handle_spf_request(mock_reader, mock_writer)
        mock_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            f"action={expected_result}\n\n".encode("utf-8")
        )

    @pytest.mark.parametrize(
        "auto_spf_query, expected_result",
        auto_query_param_list_spf_plus_greylist,
        indirect=["auto_spf_query"],
        ids=idfn,
    )
    async def test_handle_policy_request_spf_plus_greylist(
        self,
        caplog,
        monkeypatch,
        testing_policy_spf,
        testing_policy_grl,
        auto_spf_query,
        expected_result,
        mock_reader_factory,
        mock_writer,
        populated_database_fixture_with_extras,
        clear_redis_grl,
    ):
        """
        GIVEN a particular result from the SPF checker
        WHEN  communicating with Postfix
        THEN  send the appropriate result based on SPF plus Greylisting
        This test is parameterized to go through all possible responses
        """
        caplog.set_level(logging.DEBUG)
        handle_spf_request = InboundMultipolicyHandler(
            [testing_policy_spf, testing_policy_grl]
        ).async_policy_handler()
        mock_reader = mock_reader_factory(
            None, "someone@chapps.io"  # enforcing both SPF and greylisting
        )
        with monkeypatch.context() as m:
            m.setattr(spf, "query", auto_spf_query)
            # exercise handler
            with pytest.raises(CallableExhausted):
                await handle_spf_request(mock_reader, mock_writer)
        mock_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            f"action={expected_result}\n\n".encode("utf-8")
        )

    async def test_pass_after_greylist(
        self,
        caplog,
        monkeypatch,
        testing_policy_spf,
        testing_policy_grl,
        grl_reader_recognized_factory,
        passing_spf_query,
        mock_writer,
        populated_database_fixture_with_extras,
        clear_redis_grl,
    ):
        """
        :GIVEN: an email delivery attempt has occured and been greylisted
        :WHEN:  the tuple is seen again
        :THEN:  the policy handler should pass the email and prepend an SPF header
        """
        caplog.set_level(logging.DEBUG)
        handle_spf_request = InboundMultipolicyHandler(
            [testing_policy_spf, testing_policy_grl]
        ).async_policy_handler()
        mock_reader = grl_reader_recognized_factory(
            "ccullen@easydns.com", "someone@chapps.io"
        )
        with monkeypatch.context() as m:
            m.setattr(spf, "query", passing_spf_query)
            with pytest.raises(CallableExhausted):
                await handle_spf_request(mock_reader, mock_writer)
        mock_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            f"action=PREPEND Received-SPF: SPF prepend\n\n".encode("utf-8")
        )

    async def test_softfail_after_greylist(
        self,
        caplog,
        monkeypatch,
        testing_policy_spf,
        testing_policy_grl,
        grl_reader_recognized_factory,
        softfail_spf_query,
        mock_writer,
        populated_database_fixture_with_extras,
        clear_redis_grl,
    ):
        """
        :GIVEN: an email delivery attempt has occured and been greylisted
        :WHEN:  the tuple is seen again
        :THEN:  the policy handler should pass the email and prepend an SPF header

        .. note:

          This test is necessary to exercise `spf_policy.py:59` where greylisting
          is used internally by SPF.

        """
        caplog.set_level(logging.DEBUG)
        handle_spf_request = InboundMultipolicyHandler(
            [testing_policy_spf, testing_policy_grl]
        ).async_policy_handler()
        mock_reader = grl_reader_recognized_factory(
            "ccullen@easydns.com", "someone@chapps.io"
        )
        with monkeypatch.context() as m:
            m.setattr(spf, "query", softfail_spf_query)
            with pytest.raises(CallableExhausted):
                await handle_spf_request(mock_reader, mock_writer)
        mock_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            f"action=PREPEND Received-SPF: SPF prepend\n\n".encode("utf-8")
        )

    async def test_handle_request_on_unrecognized_domain(
        self,
        caplog,
        monkeypatch,
        testing_policy_spf,
        testing_policy_grl,
        populated_database_fixture_with_extras,
        mock_reader_factory,
        mock_writer,
    ):
        """
        :GIVEN: a recipient within an unrecognized domain
        :WHEN:  policy evaluation takes place
        :THEN:  return DUNNO rather than enforcing the policy
        """
        caplog.set_level(logging.DEBUG)
        handle_spf_request = InboundMultipolicyHandler(
            [testing_policy_spf, testing_policy_grl]
        ).async_policy_handler()
        mock_reader = mock_reader_factory()  # default recip foo@bar.tld
        with monkeypatch.context() as m:
            # exercise handler
            with pytest.raises(CallableExhausted):
                await handle_spf_request(mock_reader, mock_writer)
        mock_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            f"action=DUNNO\n\n".encode("utf-8")
        )

    async def test_handle_request_on_nonenforcing_domain(
        self,
        caplog,
        monkeypatch,
        testing_policy_spf,
        testing_policy_grl,
        mock_reader_factory,
        mock_writer,
        populated_database_fixture_with_extras,
    ):
        """
        :GIVEN: a recipient within an unrecognized domain
        :WHEN:  policy evaluation takes place
        :THEN:  return DUNNO rather than enforcing the policy
        """
        caplog.set_level(logging.DEBUG)
        handle_spf_request = InboundMultipolicyHandler(
            [testing_policy_spf, testing_policy_grl]
        ).async_policy_handler()
        mock_reader = mock_reader_factory(None, "someguy@easydns.org")
        with monkeypatch.context() as m:
            # exercise handler
            with pytest.raises(CallableExhausted):
                await handle_spf_request(mock_reader, mock_writer)
        mock_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            f"action=DUNNO\n\n".encode("utf-8")
        )


@pytest.mark.asyncio
class Test_InboundMultipolicyHandler_GreylistingOnly:
    async def test_handle_new_tuple(
        self,
        clear_redis_grl,
        testing_policy_spf,
        testing_policy_grl,
        grl_reader_recognized_factory,
        populated_database_fixture_with_extras,
        mock_writer,
    ):
        """
        GIVEN an email attempt from a new tuple
        WHEN  the client isn't auto-allowed
        THEN  reject the email
        """
        handle_greylist_request = InboundMultipolicyHandler(
            [testing_policy_spf, testing_policy_grl]
        ).async_policy_handler()
        reader_grl = grl_reader_recognized_factory(
            None, "someone@easydns.net"  # enforcing only Greylisting
        )
        clear_redis_grl()
        with pytest.raises(CallableExhausted):
            await handle_greylist_request(reader_grl, mock_writer)
        reader_grl.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            b"action=DEFER_IF_PERMIT Service temporarily stupid\n\n"
        )

    async def test_handle_retry_too_fast(
        self,
        clear_redis_grl,
        testing_policy_spf,
        testing_policy_grl,
        grl_reader_too_fast_factory,
        mock_writer,
    ):
        """
        GIVEN two back-to-back attempts with the same tuple
        WHEN  the two attempts are two close together
        THEN  reject the email
        """
        handle_greylist_request = InboundMultipolicyHandler(
            [testing_policy_spf, testing_policy_grl]
        ).async_policy_handler()
        grl_reader = grl_reader_too_fast_factory(None, "someone@easydns.net")
        with pytest.raises(CallableExhausted):
            await handle_greylist_request(grl_reader, mock_writer)
        grl_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            b"action=DEFER_IF_PERMIT Service temporarily stupid\n\n"
        )

    async def test_handle_recognized_tuple(
        self,
        clear_redis_grl,
        testing_policy_spf,
        testing_policy_grl,
        grl_reader_recognized_factory,
        mock_writer,
    ):
        """
        GIVEN an email delivery attempt
        WHEN  the tuple is recognized
        THEN  return DUNNO to allow other filters to block it; it will be accepted by default
        """
        handle_greylist_request = InboundMultipolicyHandler(
            [testing_policy_spf, testing_policy_grl]
        ).async_policy_handler()
        grl_reader = grl_reader_recognized_factory(None, "someone@easydns.net")
        with pytest.raises(CallableExhausted):
            await handle_greylist_request(grl_reader, mock_writer)
        grl_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(b"action=DUNNO\n\n")

    async def test_handle_allowed_client(
        self,
        clear_redis_grl,
        testing_policy_spf,
        testing_policy_grl,
        grl_reader_with_tally_factory,
        mock_writer,
    ):
        """
        GIVEN an email delivery attempt
        WHEN  the client is recognized as a reliable sender
        THEN  return DUNNO to allow other filters to block it; it will be accepted by default
        """
        handle_greylist_request = InboundMultipolicyHandler(
            [testing_policy_spf, testing_policy_grl]
        ).async_policy_handler()
        grl_reader = grl_reader_with_tally_factory(None, "someone@easydns.net")
        with pytest.raises(CallableExhausted):
            await handle_greylist_request(grl_reader, mock_writer)
        grl_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(b"action=DUNNO\n\n")
