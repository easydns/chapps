"""Tests for CHAPPS policy module"""
import pytest
import logging
import redis
import time
import spf
from unittest.mock import Mock
from chapps.policy import (
    EmailPolicy,
    GreylistingPolicy,
    OutboundQuotaPolicy,
    SenderDomainAuthPolicy,
    TIME_FORMAT,
)
from chapps.config import CHAPPSConfig
from chapps.tests.test_config.conftest import (
    chapps_mock_cfg_path,
    chapps_mock_env,
    chapps_mock_config,
    chapps_mock_config_file,
    chapps_sentinel_cfg_path,
    chapps_sentinel_env,
    chapps_sentinel_config,
    chapps_sentinel_config_file,
)
from chapps.tests.test_policy.conftest import _auto_ppr_param_list, idfn
from chapps.models import Quota
from inspect import isclass

seconds_per_day = 3600 * 24
pytestmark = pytest.mark.order(3)
SKIP_SENTINEL = True


class Test_EmailPolicy:
    """Tests of the base policy class"""

    def test_rediskey(self):
        """
        GIVEN a prefix and some arguments
        WHEN  we ask EmailPolicy for a redis key
        THEN  it should glue everything together with colons
        """
        prefix = "pre"
        args = ["foo", "bar"]
        redis_key = EmailPolicy.rediskey(prefix, *args)
        assert redis_key == "pre:foo:bar"

    def test_fmtkey(self):
        """
        GIVEN some arguments
        WHEN  we ask EmailPolicy to format a key
        THEN  it should use the prefix 'grl', and glue all together with colons
        """
        args = ["foo", "bar"]
        redis_key = EmailPolicy._fmtkey(*args)
        assert redis_key == "chapps:foo:bar"

    def test_approval_not_implemented(self, allowable_ppr):
        """
        GIVEN an instance of EmailPolicy or a subclass
        WHEN  the superclass/abstract version of approve_policy_request is called
        THEN  a NotImplementedError should be raised
        """
        policy = EmailPolicy()
        with pytest.raises(NotImplementedError):
            assert policy.approve_policy_request(allowable_ppr)

    def test_connect_to_redis(self):
        """
        GIVEN a new EmailPolicy
        WHEN  asked for a Redis handle
        THEN  return a Redis handle
        """
        policy = EmailPolicy()
        assert policy.redis.ping()

    @pytest.mark.skipif(SKIP_SENTINEL, reason="Skipping Sentinel tests")
    def test_connect_to_sentinel(
        self, chapps_sentinel_env, chapps_sentinel_config_file
    ):
        """
        GIVEN Sentinel servers are listed in the config file
        WHEN  asked for a Redis handle
        THEN  use Sentinel server and dataset information to get a read-write Redis handle
        """
        sentinel_config = CHAPPSConfig.get_config()
        policy = EmailPolicy(cfg=sentinel_config)
        assert policy.redis.ping()
        assert policy.sentinel is not None


class Test_PostfixActions:
    """Tests for abstract Postfix action superclass"""

    def test_okay(self, postfix_actions):
        """Returns OK"""
        result = postfix_actions.okay()
        assert result == "OK"

    def test_okay_accepts_useless_message(self, postfix_actions):
        """Returns OK even if a message is supplied"""
        arbitrary_message = "This message will be ignored."
        result = postfix_actions.okay(arbitrary_message)
        assert result == "OK"

    def test_dunno(self, postfix_actions):
        """Returns DUNNO"""
        result = postfix_actions.dunno()
        assert result == "DUNNO"

    def test_dunno_accepts_useless_message(self, postfix_actions):
        """Returns DUNNO even if a message is supplied"""
        arbitrary_message = "This message will be ignored."
        result = postfix_actions.dunno(arbitrary_message)
        assert result == "DUNNO"

    def test_action_for_raises_not_implemented_error(self, postfix_actions):
        """The method action_for() is abstract and not implemented by PostfixActions"""
        with pytest.raises(NotImplementedError):
            assert postfix_actions.action_for("foo")


class Test_PostfixOQPActions:
    """Testing outbound quota actions for Postfix"""

    def test_pass_yields_okay(self, oqp_actions):
        """Pass returns OK"""
        ### When the calling routine gets True from the policy, it will call .pass()
        ### and when it gets false, it will call .fail()
        ### It may be that the acceptance message, even for outbound quota, should still be DUNNO
        result = oqp_actions.passing()
        assert result == "OK" or result == "DUNNO"

    def test_fail_yields_rejection(self, oqp_actions):
        """Fail returns a string starting with '554 Rejected' or 'REJECT'"""
        ### Postfix will insert enhanced status code 5.7.1 which is the code
        ###   we want anyhow.  There seems to be no code for gateways to use
        ###   to signal that the user's outbound quota has been reached.
        result = oqp_actions.fail()
        assert result[0:7] == "REJECT " or result[0:12] == "554 Rejected"


class Test_PostfixGRLActions:
    """Testing greylisting actions for Postfix"""

    def test_pass_yields_dunno(self, grl_actions):
        """Pass returns DUNNO"""
        result = grl_actions.passing()
        assert result == "DUNNO"

    def test_fail_yields_rejection(self, grl_actions):
        """Fail returns a string starting with DEFER_IF_PERMIT"""
        result = grl_actions.fail()
        assert result[0:16] == "DEFER_IF_PERMIT "


class Test_GreylistingPolicy_Base:
    """Tests of the greylisting policy module"""

    def test_fmtkey(self):
        """
        GIVEN some arguments
        WHEN  we ask EmailPolicy to format a key
        THEN  it should use the prefix 'grl', and glue all together with colons
        """
        args = ["foo", "bar"]
        redis_key = GreylistingPolicy._fmtkey(*args)
        assert redis_key == "grl:foo:bar"

    def test_tuple_key(self, caplog, allowable_inbound_ppr):
        """
        GIVEN a PostfixPolicyRequest object populated with valid data
        WHEN  we as for a tuple key
        THEN  a string in the form of grl:<ip>:<sender>:<recipient> should be returned
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_inbound_ppr
        tuple_key_result = policy.tuple_key(ppr)
        assert (
            tuple_key_result
            == f"{GreylistingPolicy.redis_key_prefix}:{ppr.client_address}:{ppr.sender}:{ppr.recipient}"
        )

    def test_client_key(self, caplog, allowable_inbound_ppr):
        """
        GIVEN a PostfixPolicyRequest object populated with valid data
        WHEN  we ask for a client key
        THEN a string in the form of grl:<ip> should be returned
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_inbound_ppr
        client_key_result = policy.client_key(ppr)
        assert (
            client_key_result
            == f"{GreylistingPolicy.redis_key_prefix}:{ppr.client_address}"
        )

    def test_config_overrides_properly_forwarded(
        self, caplog, testing_policy_grl
    ):
        ### sanity check
        ### this really tests functionality of the superclass, but it is much more complicated to test it there
        assert (
            testing_policy_grl.config.get_block(
                "GreylistingPolicy"
            ).rejection_message
            == testing_policy_grl.config.policy_grl.rejection_message
        )
        assert (
            testing_policy_grl.params.rejection_message
            == testing_policy_grl.config.policy_grl.rejection_message
        )

    def test_approve_policy_request(
        self, caplog, monkeypatch, allowable_inbound_ppr
    ):
        """
        GIVEN a positive policy evaluation
        WHEN  approve_policy_request is called
        THEN  it should return True
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_inbound_ppr
        instance = ppr.instance
        monkeypatch.setattr(policy, "_approve_policy_request", lambda x: True)
        assert policy.approve_policy_request(ppr) == True

    def test_policy_request_instance_cache(
        self, caplog, monkeypatch, allowable_inbound_ppr
    ):
        """
        GIVEN a positive policy evaluation
        WHEN  approve_policy_request is called
        THEN  it should return True
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_inbound_ppr
        instance = ppr.instance
        monkeypatch.setattr(policy, "_approve_policy_request", lambda x: True)
        _ = policy.approve_policy_request(ppr)
        assert policy.instance_cache[ppr.instance] == True


class Test_GreylistingPolicyEvaluation:
    def test_first_encounter_false(
        self,
        caplog,
        monkeypatch,
        allowable_inbound_ppr,
        testing_policy_grl,
        populated_database_fixture,
    ):
        """
        GIVEN a new tuple
        WHEN  executed
        THEN  return False
        """
        caplog.set_level(logging.DEBUG)
        policy = testing_policy_grl
        ### simulate a new encounter with a new client
        monkeypatch.setattr(
            policy, "_get_control_data", lambda x: (None, None, None)
        )
        response = policy._approve_policy_request(allowable_inbound_ppr)
        assert not response  # .passing is False

    def test_pass_if_option_false(
        self,
        caplog,
        monkeypatch,
        allowable_inbound_ppr,
        testing_policy_grl,
        populated_database_fixture,
    ):
        """
        GIVEN that the option is set to False
        WHEN  examining a policy request
        THEN  issue a passing response since we are not enforcing this policy
        """
        caplog.set_level(logging.DEBUG)
        policy = testing_policy_grl
        monkeypatch.setattr(
            policy, "_get_control_data", lambda x: (0, None, None)
        )
        response = policy._approve_policy_request(allowable_inbound_ppr)
        assert response == "DUNNO" or response() == "DUNNO"

    def test_pass_if_whitelisted(
        self,
        caplog,
        monkeypatch,
        helo_ppr_factory,
        testing_policy_grl,
        populated_database_fixture,
    ):
        """
        :GIVEN: that the PPR's client (HELO) is whitelisted
        :WHEN:  evaluating an approval request
        :THEN:  issue a passing response
        """
        caplog.set_level(logging.DEBUG)
        policy = testing_policy_grl
        ppr = helo_ppr_factory("mail.chapps.io", "10.10.10.10")
        with monkeypatch.context() as m:
            m.setattr(
                policy.config,
                "helo_whitelist",
                {"mail.chapps.io": "10.10.10.10"},
            )
            response = policy._approve_policy_request(ppr)
        assert response == "DUNNO" or response() == "DUNNO"

    def test_first_encounter_updates_tuple(
        self, caplog, monkeypatch, allowable_inbound_ppr, testing_policy_grl
    ):
        """
        GIVEN a new tuple
        WHEN  executed
        THEN  update the tuple
        """
        caplog.set_level(logging.DEBUG)
        policy = testing_policy_grl
        ### simulate a new encounter with a new client
        monkeypatch.setattr(
            policy, "_get_control_data", lambda x: (None, None, None)
        )
        mock_update = Mock()
        monkeypatch.setattr(policy, "_update_tuple", mock_update)
        response = policy._approve_policy_request(allowable_inbound_ppr)
        assert mock_update.called

    def test_recognized_tuple_passes(
        self, caplog, monkeypatch, allowable_inbound_ppr, testing_policy_grl
    ):
        """
        GIVEN a recognized tuple - a timestamp
        WHEN  the tuple was seen more than min_delay seconds ago
        THEN  return True
        """
        caplog.set_level(logging.DEBUG)
        policy = testing_policy_grl
        ### simulate a timestamp we saw about 15 min ago
        monkeypatch.setattr(
            policy,
            "_get_control_data",
            lambda x: (1, time.time() - (60 * 15), None),
        )
        response = policy._approve_policy_request(allowable_inbound_ppr)
        assert response

    def test_recognized_tuple_updates_client_tally(
        self, caplog, monkeypatch, allowable_inbound_ppr, testing_policy_grl
    ):
        """
        GIVEN a recognized tuple - a timestamp
        WHEN  the tuple was seen more than min_delay seconds ago
        THEN  return True
        """
        caplog.set_level(logging.DEBUG)
        policy = testing_policy_grl
        ### simulate a timestamp we saw about 15 min ago
        monkeypatch.setattr(
            policy,
            "_get_control_data",
            lambda x: (1, time.time() - (60 * 15), None),
        )
        mock_update = Mock()
        monkeypatch.setattr(policy, "_update_client_tally", mock_update)
        response = policy._approve_policy_request(allowable_inbound_ppr)
        assert mock_update.called

    def test_sufficient_client_tally_permits_sending_for_unrecognized_tuple(
        self,
        caplog,
        monkeypatch,
        allowable_inbound_ppr,
        mock_client_tally,
        testing_policy_grl,
        populate_redis_grl,
        populated_database_fixture,
    ):
        """
        GIVEN a new tuple from a client with a large enough tally
        WHEN  executed
        THEN  return True
        """
        caplog.set_level(logging.DEBUG)
        ppr = allowable_inbound_ppr
        policy = testing_policy_grl
        with monkeypatch.context() as m:
            m.setattr(ppr, "sender", "someschmo@chapps.io")
            m.setattr(ppr, "recipient", "someone@chapps.io")
            populate_redis_grl(
                policy.tuple_key(ppr),
                {
                    policy.client_key(ppr): mock_client_tally(
                        policy.allow_after
                    )
                },
            )
            # # this hotwires the data-getter, which circumvents testing of
            # # the Redis-access routines which are part of the policy
            # m.setattr(
            #     policy,
            #     "_get_control_data",
            #     lambda x: (1, None, policy.allow_after),
            # )
            response = policy._approve_policy_request(ppr)
        assert response

    def test_client_tally_updated_when_unrecognized_tuple_passes(
        self,
        caplog,
        monkeypatch,
        allowable_inbound_ppr,
        mock_client_tally,
        testing_policy_grl,
        populate_redis_grl,
    ):
        """
        GIVEN a new tuple from a client with a large enough tally
        WHEN  executed
        THEN  update the tally
        """
        caplog.set_level(logging.DEBUG)
        ppr = allowable_inbound_ppr
        policy = testing_policy_grl
        with monkeypatch.context() as m:
            m.setattr(ppr, "sender", "someschmo@chapps.io")
            populate_redis_grl(
                policy.tuple_key(ppr),
                {
                    policy.client_key(ppr): mock_client_tally(
                        policy.allow_after
                    )
                },
            )
        tally = policy.redis.zrange(policy.client_key(ppr), 0, -1)
        assert len(tally) == policy.allow_after
        _ = policy._approve_policy_request(ppr)
        tally = policy.redis.zrange(policy.client_key(ppr), 0, -1)
        assert tally[-1].decode("utf-8") == ppr.instance
        assert len(tally) == policy.allow_after + 1

    def test_retry_too_soon_fails(
        self, caplog, monkeypatch, allowable_inbound_ppr, testing_policy_grl
    ):
        """
        GIVEN a recognized tuple
        WHEN  the tuple was seen too recently (less than min_delay seconds)
        THEN  return False
        """
        caplog.set_level(logging.DEBUG)
        policy = testing_policy_grl
        ### simulate a timestamp we saw about 15 min ago
        monkeypatch.setattr(
            policy, "_get_control_data", lambda x: (1, time.time(), None)
        )
        response = policy._approve_policy_request(allowable_inbound_ppr)
        assert not response

    def test_retry_too_soon_updates_tuple(
        self, caplog, monkeypatch, allowable_inbound_ppr, testing_policy_grl
    ):
        """
        GIVEN a recognized tuple
        WHEN  the tuple was seen too recently (less than min_delay seconds)
        THEN  return False
        """
        caplog.set_level(logging.DEBUG)
        policy = testing_policy_grl
        ### simulate a timestamp we saw about 15 min ago
        monkeypatch.setattr(
            policy, "_get_control_data", lambda x: (1, time.time(), None)
        )
        mock_update = Mock()
        monkeypatch.setattr(policy, "_update_tuple", mock_update)
        response = policy._approve_policy_request(allowable_inbound_ppr)
        assert mock_update.called


class Test_GreylistingPolicy_update_control_data:
    """Testing control update routes _update_tuple and _update_client_tally"""

    def test_update_tuple(
        self, caplog, clear_redis_grl, allowable_inbound_ppr
    ):
        """
        GIVEN a ppr
        WHEN  _update_tuple executed
        THEN  set a key with a particular structure to a current timestamp
        """
        caplog.set_level(logging.DEBUG)
        ppr = allowable_inbound_ppr
        policy = GreylistingPolicy()
        t = time.time()
        policy._update_tuple(ppr)
        t_stored = policy.redis.get(policy.tuple_key(ppr))
        assert t_stored is not None
        t_stored = float(t_stored)
        assert t_stored > t and t_stored < time.time()

    def test_update_client_tally(
        self, caplog, clear_redis_grl, allowable_inbound_ppr
    ):
        """
        GIVEN a ppr
        WHEN  _update_client_tally is executed
        THEN  add the tuple (map) instance -> timestamp to the client key
        """
        caplog.set_level(logging.DEBUG)
        ppr = allowable_inbound_ppr
        policy = GreylistingPolicy()
        policy._update_client_tally(ppr)
        client_tally = policy.redis.zrange(policy.client_key(ppr), 0, -1)
        assert client_tally[0].decode("utf-8") == ppr.instance

    def test_skip_client_tally_update_if_allow_after_is_zero(
        self, caplog, monkeypatch, clear_redis_grl, allowable_inbound_ppr
    ):
        """
        GIVEN that allow_after is set to zero (we are not keeping a success tally)
        WHEN  _update_client_tally is executed
        THEN  immediately return
        """
        caplog.set_level(logging.DEBUG)
        ppr = allowable_inbound_ppr
        policy = GreylistingPolicy(auto_allow_after=0)
        mock_redis_pipeline = Mock()
        with monkeypatch.context() as m:
            m.setattr(policy.redis, "pipeline", mock_redis_pipeline)
            _ = policy._update_client_tally(ppr)
        assert not mock_redis_pipeline.called


class Test_GreylistingPolicy_get_control_data:
    """This method interfaces with Redis"""

    def test_no_keys_yet_exist(
        self, caplog, clear_redis_grl, allowable_inbound_ppr
    ):
        """
        GIVEN a new tuple
        WHEN  control data is requested
        THEN  the returned tuple should have None as its first element
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_inbound_ppr
        response = policy._get_control_data(ppr)
        assert response[0] is None

    def test_tuple_is_recognized(
        self, caplog, clear_redis_grl, allowable_inbound_ppr
    ):
        """
        GIVEN a recognized tuple
        WHEN  control data is requested
        THEN  the tuple should have a timestamp (float) as its 2nd argument
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_inbound_ppr
        policy._update_tuple(ppr)
        response = policy._get_control_data(ppr)
        assert type(response[1]) == float
        assert response[1] < time.time()

    def test_allow_after_is_zero(
        self, caplog, monkeypatch, clear_redis_grl, allowable_inbound_ppr
    ):
        """
        GIVEN a recognized tuple, and allow_after set to 0
        WHEN  control data is requested
        THEN  the third member of the tuple should always be None
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_inbound_ppr
        policy._update_tuple(ppr)
        monkeypatch.setattr(policy, "allow_after", 0)
        response = policy._get_control_data(ppr)
        assert response[2] == None

    def test_new_tuple_client_tally_present(
        self,
        caplog,
        monkeypatch,
        mock_client_tally,
        populate_redis_grl,
        allowable_inbound_ppr,
        unique_instance,
    ):
        """
        GIVEN an unrecognized tuple, but existing client tally
        WHEN  executed
        THEN  the count should be returned as the third member of the tuple
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_inbound_ppr
        tally = mock_client_tally(policy.allow_after - 2)
        tuple_key = ""
        with monkeypatch.context() as m:
            m.setattr(ppr, "sender", "someschmo@chapps.io")
            tuple_key = policy.tuple_key(ppr)
        client_key = policy.client_key(ppr)
        populate_redis_grl(tuple_key, {client_key: tally})
        response = policy._get_control_data(ppr)
        assert response[1] is None
        assert response[2] == len(tally)

    def test_tuple_recognized_and_tally_exists(
        self,
        caplog,
        mock_client_tally,
        allowable_inbound_ppr,
        populate_redis_grl,
        unique_instance,
    ):
        """
        :GIVEN: a recognized tuple, and an existing tally
        :WHEN:  executed
        :THEN:  return the option flag,
                a timestamp,
                and the client's tally in that order
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_inbound_ppr
        tally = mock_client_tally(policy.allow_after - 2)
        tuple_key = policy.tuple_key(ppr)
        client_key = policy.client_key(ppr)
        populate_redis_grl(tuple_key, {client_key: tally})
        response = policy._get_control_data(ppr)
        assert type(response[1]) == float
        assert response[1] < time.time()
        assert response[2] == len(tally)


class Test_OutboundQuotaPolicy:
    """Tests of the outbound quota policy module"""

    def test_oqp_fmtkey(self):
        """
        GIVEN: email (user), and parameter name
        WHEN: oqp is asked for a Redis key
        THEN: oqp._fmtkey(user, param) should return a string like 'oqp:<user>:<param>'
        """
        policy = OutboundQuotaPolicy()
        redis_key = policy._fmtkey("ccullen@easydns.com", "attempts")
        assert redis_key == "oqp:ccullen@easydns.com:attempts"

    def test_approve_policy_request(
        self, caplog, allowable_ppr, well_spaced_attempts, populate_redis
    ):
        """
        Verify that underquota users' emails are approved.
        """
        caplog.set_level(logging.DEBUG)
        populate_redis(allowable_ppr.user, 100, well_spaced_attempts(80))
        policy = OutboundQuotaPolicy()
        assert policy.approve_policy_request(allowable_ppr)

    def test_approve_last_remaining_quota(
        self, caplog, allowable_ppr, well_spaced_attempts, populate_redis
    ):
        """
        Verify that the last bit of a quota can be used.
        """
        caplog.set_level(logging.DEBUG)
        populate_redis(allowable_ppr.user, 100, well_spaced_attempts(99))
        policy = OutboundQuotaPolicy()
        assert policy.approve_policy_request(allowable_ppr)

    def test_approve_last_with_multiple_recipients(
        self, caplog, groupsend_ppr, well_spaced_attempts, populate_redis
    ):
        """
        Verify that multiple recipients adding up to the last available messages will be approved.
        """
        caplog.set_level(logging.DEBUG)
        recipient_count = len(groupsend_ppr.recipient.split(","))
        populate_redis(
            groupsend_ppr.user,
            100,
            well_spaced_attempts(100 - recipient_count),
        )
        policy = OutboundQuotaPolicy()
        assert policy.approve_policy_request(groupsend_ppr)

    def test_approve_underquota_within_margin(
        self,
        caplog,
        multisend_ppr_factory,
        well_spaced_attempts,
        populate_redis,
    ):
        """
        Verify that when a multi-recipient email takes an underquota account overquota, it will be
        approved if the amount overquota is within the established margin.
        """
        caplog.set_level(logging.DEBUG)
        # create a PPR reflecting 8 recipients
        groupsend_ppr = multisend_ppr_factory("underquota@chapps.io", 8)
        # for the sender, set a limit of 100, a margin of 10, and 95 well-spaced send attempts
        populate_redis(groupsend_ppr.user, 100, well_spaced_attempts(95), 10)
        policy = OutboundQuotaPolicy()
        # even though this would be 3 emails overquota, it should be allowed anyway, by the margin
        assert policy.approve_policy_request(groupsend_ppr)
        assert any("OK" in rec.message for rec in caplog.records)

    def test_deny_policy_request(
        self, overquota_ppr, well_spaced_attempts, populate_redis
    ):
        """
        Verify that overquota users are rejected.
        """
        populate_redis(overquota_ppr.user, 100, well_spaced_attempts(150))
        policy = OutboundQuotaPolicy()
        assert not policy.approve_policy_request(overquota_ppr)

    def test_deny_when_too_many_recipients(
        self, multisend_ppr_factory, well_spaced_attempts, populate_redis
    ):
        """:GIVEN: a multi-recipient PPR
        :WHEN: the recipient list would go over the quota
        :THEN: the attempt is denied.

        This has the side-effect of meaning that rejected multi-recipient
        attempts add their recipient count to the attempt history, meaning that
        the account will be fully over-quota once this occurs.

        """
        groupsend_ppr = multisend_ppr_factory("overquota@chapps.io", 20)
        populate_redis(groupsend_ppr.user, 100, well_spaced_attempts(95), 10)
        policy = OutboundQuotaPolicy()
        assert not policy.approve_policy_request(groupsend_ppr)

    def test_deny_overquota_within_margin(
        self, caplog, groupsend_ppr, well_spaced_attempts, populate_redis
    ):
        """
        Verify that an account which is just over-quota will not have a new email which is within
        the margin approved.  This is to ensure that the quota is real, and not just enlarged by
        the margin.
        """
        caplog.set_level(logging.DEBUG)
        populate_redis(groupsend_ppr.user, 100, well_spaced_attempts(101), 10)
        policy = OutboundQuotaPolicy()
        assert not policy.approve_policy_request(groupsend_ppr)
        assert any(
            "too many attempts" in rec.message for rec in caplog.records
        )

    @pytest.mark.xfail  # this feature is on hold at present
    def test_deny_rapid_attempts(
        self, allowable_ppr, rapid_attempts, populate_redis
    ):
        """
        Verify that attempts which come too fast will be rejected.
        """
        populate_redis(allowable_ppr.user, 200, rapid_attempts(20))
        policy = OutboundQuotaPolicy()
        assert not policy.approve_policy_request(allowable_ppr)

    def test_return_cached_instance_approval(
        self,
        allowable_ppr,
        well_spaced_double_attempts,
        populate_redis,
        caplog,
    ):
        """
        GIVEN we have already seen a particular instance before,
        WHEN  we are asked to approve or deny it
        THEN  we will return the cached value of the instance (which really only matters on approval)
        """
        populate_redis(
            allowable_ppr.user, 200, well_spaced_double_attempts(100)
        )
        policy = OutboundQuotaPolicy()
        policy.instance_cache[allowable_ppr.instance] = False
        ### need a patched policy which has the instance in its instance cache
        response = policy.approve_policy_request(allowable_ppr)
        for m in caplog.messages:
            print(m)
        assert response == False

    def test_approve_policy_request_for_uncached(
        self,
        uncached_allowable_ppr,
        well_spaced_attempts,
        populated_database_fixture,
        testing_policy,
    ):
        """
        Verify that existing-but-uncached users' emails are approved.
        (Uncached implies they have sent no emails w/i the rolling interval.)
        """
        assert testing_policy.approve_policy_request(uncached_allowable_ppr)

    def test_deny_policy_request_for_undefined(
        self, undefined_ppr, populated_database_fixture, testing_policy
    ):
        """
        Verify that undefined users are rejected.
        """
        assert not testing_policy.approve_policy_request(undefined_ppr)

    def test_current_quota(
        self,
        sda_allowable_ppr,
        populate_redis,
        well_spaced_attempts,
        populated_database_fixture,
        testing_policy,
    ):
        ppr = sda_allowable_ppr
        attempts = well_spaced_attempts(100)
        populate_redis(ppr.user, 240, attempts)
        remaining, remarks = testing_policy.current_quota(
            ppr.user, Quota(id=1, name="10eph", quota=240)
        )
        assert remaining == 140
        last_try = time.strftime(TIME_FORMAT, time.gmtime(attempts[-1]))
        assert f"Last send attempt was at {last_try}" in remarks


auto_ppr_param_list = _auto_ppr_param_list(
    senders=[
        "ccullen@easydns.com",
        "mautic+bounce_622b80da90870@easydns.com",
        "weirdo@twodomains.ca@weird.com",
        "bareword",
    ]
)


class Test_SenderDomainAuthPolicy:
    def test_sda_fmtkey(self):
        policy = SenderDomainAuthPolicy()
        redis_key = policy._fmtkey("ccullen@easydns.com", "chapps.io")
        assert redis_key == "sda:ccullen@easydns.com:chapps.io"

    @pytest.mark.parametrize(
        "auto_ppr, expected_result", auto_ppr_param_list, ids=idfn
    )
    def test_get_sender_domain(self, auto_ppr, expected_result):
        policy = SenderDomainAuthPolicy()
        if isclass(expected_result) and issubclass(expected_result, Exception):
            with pytest.raises(expected_result):
                assert policy._get_sender_domain(auto_ppr)
        else:
            result = policy._get_sender_domain(auto_ppr)
            assert result == expected_result

    def test_sender_domain_key(self, allowable_ppr):
        policy = SenderDomainAuthPolicy()
        redis_key = policy.sender_domain_key(allowable_ppr)
        assert (
            redis_key
            == f"sda:{allowable_ppr.sasl_username}:{allowable_ppr.sender.split('@')[1]}"
        )

    def test_authorized_user(self, sda_allowable_ppr, testing_policy_sda):
        result = testing_policy_sda.approve_policy_request(sda_allowable_ppr)
        assert result == True

    def test_whole_email_auth(self, sda_auth_email_ppr, testing_policy_sda):
        result = testing_policy_sda.approve_policy_request(sda_auth_email_ppr)
        assert result == True

    def test_whole_email_unauth(
        self, sda_unauth_email_ppr, testing_policy_sda
    ):
        result = testing_policy_sda.approve_policy_request(
            sda_unauth_email_ppr
        )
        assert result == False

    ### note that no clearing of Redis is going on
    def test_cached_authed_user(
        self, monkeypatch, sda_allowable_ppr, testing_policy_sda
    ):
        mock_acq_pol_data = Mock(result=False)
        with monkeypatch.context() as m:
            m.setattr(
                testing_policy_sda, "acquire_policy_for", mock_acq_pol_data
            )
            result = testing_policy_sda.approve_policy_request(
                sda_allowable_ppr
            )
        mock_acq_pol_data.assert_not_called()
        assert result == True

    def test_cached_whole_email(
        self, monkeypatch, sda_auth_email_ppr, testing_policy_sda
    ):
        mock_acq_pol_data = Mock(result=True)
        with monkeypatch.context() as m:
            m.setattr(
                testing_policy_sda, "acquire_policy_for", mock_acq_pol_data
            )
            result = testing_policy_sda.approve_policy_request(
                sda_auth_email_ppr
            )
        mock_acq_pol_data.assert_not_called()
        assert result == True

    def test_unauthorized_user(
        self, sda_unauth_ppr, testing_policy_sda, clear_redis_sda
    ):
        result = testing_policy_sda.approve_policy_request(sda_unauth_ppr)
        assert result == False

    ### For completeness we will test both
    def test_cached_unauth_user(
        self, monkeypatch, sda_unauth_ppr, testing_policy_sda
    ):
        mock_acq_pol_data = Mock(result=True)
        with monkeypatch.context() as m:
            m.setattr(
                testing_policy_sda, "acquire_policy_for", mock_acq_pol_data
            )
            result = testing_policy_sda.approve_policy_request(sda_unauth_ppr)
        mock_acq_pol_data.assert_not_called()


class Test_InboundPolicy:
    def test_whitelist(self, testing_policy_inbound, helo_ppr_factory):
        """
        :GIVEN: a helo whitelist and an inbound policy
        :WHEN:  the PPR reflects a connection from the whitelisted server
        :THEN:  the policy's _whitelisted() method should return True
        """
        policy = testing_policy_inbound
        ppr = helo_ppr_factory("mail.chapps.io", "10.10.10.10")
        assert ppr.helo_match({"mail.chapps.io": "10.10.10.10"})

    def test_not_whitelisted(self, testing_policy_inbound, helo_ppr_factory):
        """
        :GIVEN: a helo whitelist and an inbound policy
        :WHEN:  the PPR reflects a connection from an unlisted server
        :THEN:  the policy's _whitelisted() method should return False
        """
        policy = testing_policy_inbound
        ppr = helo_ppr_factory("spammity.spam.com", "1.2.3.4")
        assert not ppr.helo_match({"mail.chapps.io": "10.10.10.10"})
