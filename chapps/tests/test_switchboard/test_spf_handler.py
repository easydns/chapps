"""tests for chapps.switchboard"""

import spf
import pytest
import logging
from unittest.mock import patch
from chapps.switchboard import SPFEnforcementHandler
from chapps.spf_policy import SPFEnforcementPolicy
from chapps.tests.conftest import CallableExhausted
from chapps.tests.test_policy.conftest import (
    auto_spf_query,
    mock_spf_queries,
    _auto_query_param_list,
    idfn,
    testing_policy_spf,
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
        mock_reader = mock_reader_factory()
        with monkeypatch.context() as m:
            m.setattr(spf, "query", auto_spf_query)
            # exercise handler
            with pytest.raises(CallableExhausted):
                await handle_spf_request(mock_reader, mock_writer)
        mock_reader.readuntil.assert_called_with(b"\n\n")
        mock_writer.write.assert_called_with(
            f"action={expected_result}\n\n".encode("utf-8")
        )
