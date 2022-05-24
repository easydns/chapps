"""Tests for CHAPPS SPF Enforcement policy module"""
import pytest
import logging
import redis
import time
import spf
from unittest.mock import Mock
from chapps.spf_policy import SPFEnforcementPolicy
from chapps.tests.test_policy.conftest import (
    _spf_actions,
    _spf_results,
    _auto_query_param_list,
    idfn,
)
import chapps.config

# from chapps.tests.test_config.conftest import chapps_mock_cfg_path, chapps_mock_env, chapps_mock_config, chapps_mock_config_file

### SPF result internal -> native name + message dictionary:
spf_results = _spf_results()
spf_actions = _spf_actions()
auto_query_param_list = _auto_query_param_list()


class Test_SPFEnforcementPolicy:
    """Tests of the SPF module"""

    ### Best to avoid actually using DNS for tests
    def test_passing_emails_get_prepend(
        self, caplog, monkeypatch, passing_spf_query, allowable_ppr
    ):
        caplog.set_level(logging.DEBUG)
        with monkeypatch.context() as m:
            m.setattr(spf, "query", passing_spf_query)
            result = SPFEnforcementPolicy().approve_policy_request(
                allowable_ppr
            )
        assert result == "PREPEND X-CHAPPSTESTING: SPF prepend"

    def test_failing_emails_get_reject(
        self, caplog, monkeypatch, failing_spf_query, allowable_ppr
    ):
        caplog.set_level(logging.DEBUG)
        with monkeypatch.context() as m:
            m.setattr(spf, "query", failing_spf_query)
            result = SPFEnforcementPolicy().approve_policy_request(
                allowable_ppr
            )
        assert (
            result == "550 5.7.1 SPF check failed: CHAPPS failing SPF message"
        )

    def test_no_helo_passing_mf_gets_prepend(
        self, caplog, monkeypatch, no_helo_passing_mf, allowable_ppr
    ):
        caplog.set_level(logging.DEBUG)
        with monkeypatch.context() as m:
            m.setattr(spf, "query", no_helo_passing_mf)
            result = SPFEnforcementPolicy().approve_policy_request(
                allowable_ppr
            )
        assert result == "PREPEND X-CHAPPSTESTING: SPF prepend"

    def test_passing_helo_failing_mf_gets_reject(
        self, caplog, monkeypatch, passing_helo_failing_mf, allowable_ppr
    ):
        caplog.set_level(logging.DEBUG)
        with monkeypatch.context() as m:
            m.setattr(spf, "query", passing_helo_failing_mf)
            result = SPFEnforcementPolicy().approve_policy_request(
                allowable_ppr
            )
        assert (
            result == "550 5.7.1 SPF check failed: CHAPPS failing SPF message"
        )

    @pytest.mark.parametrize(
        "auto_spf_query, expected_result",
        auto_query_param_list,
        indirect=["auto_spf_query"],
        ids=idfn,
    )
    def test_all_spf_query_result_permutations(
        self,
        caplog,
        monkeypatch,
        clear_redis_grl,
        auto_spf_query,
        expected_result,
        allowable_ppr,
    ):
        caplog.set_level(logging.DEBUG)
        with monkeypatch.context() as m:
            m.setattr(spf, "query", auto_spf_query)
            result = SPFEnforcementPolicy().approve_policy_request(
                allowable_ppr
            )
        assert result == expected_result
