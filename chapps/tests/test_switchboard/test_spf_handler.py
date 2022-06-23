"""tests for chapps.switchboard"""

import spf
import pytest
import logging
from unittest.mock import patch
from chapps.switchboard import SPFEnforcementHandler
from chapps.spf_policy import SPFEnforcementPolicy
from chapps.signals import CallableExhausted
from chapps.tests.test_policy.conftest import (
    auto_spf_query,
    mock_spf_queries,
    _auto_query_param_list,
    idfn,
    testing_policy_spf,
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
