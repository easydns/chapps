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

    def test_approval_not_implemented(self):
        """
        GIVEN an instance of EmailPolicy or a subclass
        WHEN  the superclass/abstract version of approve_policy_request is called
        THEN  a NotImplementedError should be raised
        """
        policy = EmailPolicy()
        with pytest.raises(NotImplementedError):
            assert policy.approve_policy_request(None)

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
        sentinel_config = CHAPPSConfig()
        policy = EmailPolicy(cfg=sentinel_config)
        assert policy.redis.ping()
        assert policy.sentinel is not None


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

    def test_tuple_key(self, caplog, allowable_ppr):
        """
        GIVEN a PostfixPolicyRequest object populated with valid data
        WHEN  we as for a tuple key
        THEN  a string in the form of grl:<ip>:<sender>:<recipient> should be returned
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_ppr
        tuple_key_result = policy.tuple_key(ppr)
        assert (
            tuple_key_result
            == f"{GreylistingPolicy.redis_key_prefix}:{ppr.client_address}:{ppr.sender}:{ppr.recipient}"
        )

    def test_client_key(self, caplog, allowable_ppr):
        """
        GIVEN a PostfixPolicyRequest object populated with valid data
        WHEN  we ask for a client key
        THEN a string in the form of grl:<ip> should be returned
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_ppr
        client_key_result = policy.client_key(ppr)
        assert (
            client_key_result
            == f"{GreylistingPolicy.redis_key_prefix}:{ppr.client_address}"
        )

    def test_config_overrides_properly_forwarded(self, caplog, testing_policy_grl):
        ### sanity check
        ### this really tests functionality of the superclass, but it is much more complicated to test it there
        assert (
            testing_policy_grl.config.get_block("GreylistingPolicy").rejection_message
            == testing_policy_grl.config.policy_grl.rejection_message
        )
        assert (
            testing_policy_grl.params.rejection_message
            == testing_policy_grl.config.policy_grl.rejection_message
        )

    def test_approve_policy_request(self, caplog, monkeypatch, allowable_ppr):
        """
        GIVEN a positive policy evaluation
        WHEN  approve_policy_request is called
        THEN  it should return True
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_ppr
        instance = ppr.instance
        monkeypatch.setattr(policy, "_evaluate_policy_request", lambda x: True)
        assert policy.approve_policy_request(ppr) == True

    def test_policy_request_instance_cache(self, caplog, monkeypatch, allowable_ppr):
        """
        GIVEN a positive policy evaluation
        WHEN  approve_policy_request is called
        THEN  it should return True
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_ppr
        instance = ppr.instance
        monkeypatch.setattr(policy, "_evaluate_policy_request", lambda x: True)
        _ = policy.approve_policy_request(ppr)
        assert policy.instance_cache[ppr.instance] == True


class Test_GreylistingPolicyEvaluation:
    def test_first_encounter_false(self, caplog, monkeypatch, allowable_ppr):
        """
        GIVEN a new tuple
        WHEN  executed
        THEN  return False
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ### simulate a new encounter with a new client
        monkeypatch.setattr(policy, "_get_control_data", lambda x: (None, None))
        response = policy._evaluate_policy_request(allowable_ppr)
        assert response == False

    def test_first_encounter_updates_tuple(self, caplog, monkeypatch, allowable_ppr):
        """
        GIVEN a new tuple
        WHEN  executed
        THEN  update the tuple
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ### simulate a new encounter with a new client
        monkeypatch.setattr(policy, "_get_control_data", lambda x: (None, None))
        mock_update = Mock()
        monkeypatch.setattr(policy, "_update_tuple", mock_update)
        response = policy._evaluate_policy_request(allowable_ppr)
        assert mock_update.called

    def test_recognized_tuple_passes(self, caplog, monkeypatch, allowable_ppr):
        """
        GIVEN a recognized tuple - a timestamp
        WHEN  the tuple was seen more than min_delay seconds ago
        THEN  return True
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ### simulate a timestamp we saw about 15 min ago
        monkeypatch.setattr(
            policy, "_get_control_data", lambda x: (time.time() - (60 * 15), None)
        )
        response = policy._evaluate_policy_request(allowable_ppr)
        assert response == True

    def test_recognized_tuple_updates_client_tally(
        self, caplog, monkeypatch, allowable_ppr
    ):
        """
        GIVEN a recognized tuple - a timestamp
        WHEN  the tuple was seen more than min_delay seconds ago
        THEN  return True
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ### simulate a timestamp we saw about 15 min ago
        monkeypatch.setattr(
            policy, "_get_control_data", lambda x: (time.time() - (60 * 15), None)
        )
        mock_update = Mock()
        monkeypatch.setattr(policy, "_update_client_tally", mock_update)
        response = policy._evaluate_policy_request(allowable_ppr)
        assert mock_update.called

    def test_sufficient_client_tally_permits_sending_for_unrecognized_tuple(
        self, caplog, monkeypatch, allowable_ppr, mock_client_tally, populate_redis_grl
    ):
        """
        GIVEN a new tuple from a client with a large enough tally
        WHEN  executed
        THEN  return True
        """
        caplog.set_level(logging.DEBUG)
        ppr = allowable_ppr
        policy = GreylistingPolicy()
        with monkeypatch.context() as m:
            m.setattr(ppr, "sender", "someschmo@chapps.io")
            populate_redis_grl(
                policy.tuple_key(ppr),
                {policy.client_key(ppr): mock_client_tally(policy.allow_after)},
            )
        response = policy._evaluate_policy_request(ppr)
        assert response == True

    def test_client_tally_updated_when_unrecognized_tuple_passes(
        self, caplog, monkeypatch, allowable_ppr, mock_client_tally, populate_redis_grl
    ):
        """
        GIVEN a new tuple from a client with a large enough tally
        WHEN  executed
        THEN  update the tally
        """
        caplog.set_level(logging.DEBUG)
        ppr = allowable_ppr
        policy = GreylistingPolicy()
        with monkeypatch.context() as m:
            m.setattr(ppr, "sender", "someschmo@chapps.io")
            populate_redis_grl(
                policy.tuple_key(ppr),
                {policy.client_key(ppr): mock_client_tally(policy.allow_after)},
            )
        tally = policy.redis.zrange(policy.client_key(ppr), 0, -1)
        assert len(tally) == policy.allow_after
        _ = policy._evaluate_policy_request(ppr)
        tally = policy.redis.zrange(policy.client_key(ppr), 0, -1)
        assert tally[-1].decode("utf-8") == ppr.instance
        assert len(tally) == policy.allow_after + 1

    def test_retry_too_soon_fails(self, caplog, monkeypatch, allowable_ppr):
        """
        GIVEN a recognized tuple
        WHEN  the tuple was seen too recently (less than min_delay seconds)
        THEN  return False
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ### simulate a timestamp we saw about 15 min ago
        monkeypatch.setattr(policy, "_get_control_data", lambda x: (time.time(), None))
        response = policy._evaluate_policy_request(allowable_ppr)
        assert response == False

    def test_retry_too_soon_updates_tuple(self, caplog, monkeypatch, allowable_ppr):
        """
        GIVEN a recognized tuple
        WHEN  the tuple was seen too recently (less than min_delay seconds)
        THEN  return False
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ### simulate a timestamp we saw about 15 min ago
        monkeypatch.setattr(policy, "_get_control_data", lambda x: (time.time(), None))
        mock_update = Mock()
        monkeypatch.setattr(policy, "_update_tuple", mock_update)
        response = policy._evaluate_policy_request(allowable_ppr)
        assert mock_update.called


class Test_GreylistingPolicy_update_control_data:
    """Testing control update routes _update_tuple and _update_client_tally"""

    def test_update_tuple(self, caplog, clear_redis_grl, allowable_ppr):
        """
        GIVEN a ppr
        WHEN  _update_tuple executed
        THEN  set a key with a particular structure to a current timestamp
        """
        caplog.set_level(logging.DEBUG)
        ppr = allowable_ppr
        policy = GreylistingPolicy()
        t = time.time()
        policy._update_tuple(ppr)
        t_stored = policy.redis.get(policy.tuple_key(ppr))
        assert t_stored is not None
        t_stored = float(t_stored)
        assert t_stored > t and t_stored < time.time()

    def test_update_client_tally(self, caplog, clear_redis_grl, allowable_ppr):
        """
        GIVEN a ppr
        WHEN  _update_client_tally is executed
        THEN  add the tuple (map) instance -> timestamp to the client key
        """
        caplog.set_level(logging.DEBUG)
        ppr = allowable_ppr
        policy = GreylistingPolicy()
        policy._update_client_tally(ppr)
        client_tally = policy.redis.zrange(policy.client_key(ppr), 0, -1)
        assert client_tally[0].decode("utf-8") == ppr.instance

    def test_skip_client_tally_update_if_allow_after_is_zero(
        self, caplog, monkeypatch, clear_redis_grl, allowable_ppr
    ):
        """
        GIVEN that allow_after is set to zero (we are not keeping a success tally)
        WHEN  _update_client_tally is executed
        THEN  immediately return
        """
        caplog.set_level(logging.DEBUG)
        ppr = allowable_ppr
        policy = GreylistingPolicy(auto_allow_after=0)
        mock_redis_pipeline = Mock()
        with monkeypatch.context() as m:
            m.setattr(policy.redis, "pipeline", mock_redis_pipeline)
            _ = policy._update_client_tally(ppr)
        assert not mock_redis_pipeline.called


class Test_GreylistingPolicy_get_control_data:
    """This method interfaces with Redis"""

    def test_no_keys_yet_exist(self, caplog, clear_redis_grl, allowable_ppr):
        """
        GIVEN a new tuple
        WHEN  control data is requested
        THEN  the returned tuple should have None as its first element
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_ppr
        response = policy._get_control_data(ppr)
        assert response[0] == None

    def test_tuple_is_recognized(self, caplog, clear_redis_grl, allowable_ppr):
        """
        GIVEN a recognized tuple
        WHEN  control data is requested
        THEN  the returned tuple should have a timestamp (float) as its first argument
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_ppr
        policy._update_tuple(ppr)
        response = policy._get_control_data(ppr)
        assert type(response[0]) == float
        assert response[0] < time.time()

    def test_allow_after_is_zero(
        self, caplog, monkeypatch, clear_redis_grl, allowable_ppr
    ):
        """
        GIVEN a recognized tuple, and allow_after set to 0
        WHEN  control data is requested
        THEN  the second member of the tuple should always be None
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_ppr
        policy._update_tuple(ppr)
        monkeypatch.setattr(policy, "allow_after", 0)
        response = policy._get_control_data(ppr)
        assert response[1] == None

    def test_new_tuple_client_tally_present(
        self,
        caplog,
        monkeypatch,
        mock_client_tally,
        populate_redis_grl,
        allowable_ppr,
        unique_instance,
    ):
        """
        GIVEN an unrecognized tuple, but existing client tally
        WHEN  executed
        THEN  the count should be returned as the second member of the tuple
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_ppr
        tally = mock_client_tally(policy.allow_after - 2)
        tuple_key = ""
        with monkeypatch.context() as m:
            m.setattr(ppr, "sender", "someschmo@chapps.io")
            tuple_key = policy.tuple_key(ppr)
        client_key = policy.client_key(ppr)
        populate_redis_grl(tuple_key, {client_key: tally})
        response = policy._get_control_data(ppr)
        assert response[0] == None
        assert response[1] == len(tally)

    def test_tuple_recognized_and_tally_exists(
        self,
        caplog,
        mock_client_tally,
        allowable_ppr,
        populate_redis_grl,
        unique_instance,
    ):
        """
        GIVEN a recognized tuple, and an existing tally
        WHEN  executed
        THEN  return a timestamp, and the client's tally in that order
        """
        caplog.set_level(logging.DEBUG)
        policy = GreylistingPolicy()
        ppr = allowable_ppr
        tally = mock_client_tally(policy.allow_after - 2)
        tuple_key = policy.tuple_key(ppr)
        client_key = policy.client_key(ppr)
        populate_redis_grl(tuple_key, {client_key: tally})
        response = policy._get_control_data(ppr)
        assert type(response[0]) == float
        assert response[0] < time.time()
        assert response[1] == len(tally)


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
        populate_redis(allowable_ppr.sender, 100, well_spaced_attempts(80))
        policy = OutboundQuotaPolicy()
        assert policy.approve_policy_request(allowable_ppr)

    def test_approve_last_remaining_quota(
        self, caplog, allowable_ppr, well_spaced_attempts, populate_redis
    ):
        """
        Verify that the last bit of a quota can be used.
        """
        caplog.set_level(logging.DEBUG)
        populate_redis(allowable_ppr.sender, 100, well_spaced_attempts(99))
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
            groupsend_ppr.sender, 100, well_spaced_attempts(100 - recipient_count)
        )
        policy = OutboundQuotaPolicy()
        assert policy.approve_policy_request(groupsend_ppr)

    def test_approve_underquota_within_margin(
        self, caplog, multisend_ppr_factory, well_spaced_attempts, populate_redis
    ):
        """
        Verify that when a multi-recipient email takes an underquota account overquota, it will be
        approved if the amount overquota is within the established margin.
        """
        caplog.set_level(logging.DEBUG)
        # create a PPR reflecting 8 recipients
        groupsend_ppr = multisend_ppr_factory("underquota@chapps.io", 8)
        # for the sender, set a limit of 100, a margin of 10, and 95 well-spaced send attempts
        populate_redis(groupsend_ppr.sender, 100, well_spaced_attempts(95), 10)
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
        populate_redis(overquota_ppr.sender, 100, well_spaced_attempts(150))
        policy = OutboundQuotaPolicy()
        assert not policy.approve_policy_request(overquota_ppr)

    def test_deny_when_too_many_recipients(
        self, multisend_ppr_factory, well_spaced_attempts, populate_redis
    ):
        """
        Verify that when the recipient list would go over the quota, the attempt is denied.
        This has the side-effect of meaning that rejected multi-recipient attempts add their
        recipient count to the attempt history, meaning that the account will be fully over-quota
        once this occurs.
        TODO: consider removing failed multiple attempts from the sorted list, reducing their impact to 1
        """
        groupsend_ppr = multisend_ppr_factory("overquota@chapps.io", 20)
        populate_redis(groupsend_ppr.sender, 100, well_spaced_attempts(95), 10)
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
        populate_redis(groupsend_ppr.sender, 100, well_spaced_attempts(101), 10)
        policy = OutboundQuotaPolicy()
        assert not policy.approve_policy_request(groupsend_ppr)
        assert any("too many attempts" in rec.message for rec in caplog.records)

    def test_deny_rapid_attempts(self, allowable_ppr, rapid_attempts, populate_redis):
        """
        Verify that attempts which come too fast will be rejected.
        """
        populate_redis(allowable_ppr.sender, 200, rapid_attempts(20))
        policy = OutboundQuotaPolicy()
        assert not policy.approve_policy_request(allowable_ppr)

    def test_return_cached_instance_approval(
        self, allowable_ppr, well_spaced_double_attempts, populate_redis, caplog
    ):
        """
        GIVEN we have already seen a particular instance before,
        WHEN  we are asked to approve or deny it
        THEN  we will return the cached value of the instance (which really only matters on approval)
        """
        populate_redis(allowable_ppr.sender, 200, well_spaced_double_attempts(100))
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

    ### there was a thought about auto-loading user quotas from a memo-list, but
    ### seeing as Redis store is persistent across restarts, there seems no
    ### good reason to store a memo of users to load en-masse


auto_ppr_param_list = _auto_ppr_param_list(senders=[
    "ccullen@easydns.com",
    "mautic+bounce_622b80da90870@easydns.com",
    "weirdo@twodomains.ca@weird.com",
    "bareword",
])

class Test_SenderDomainAuthPolicy:
    def test_sda_fmtkey(self):
        policy = SenderDomainAuthPolicy()
        redis_key = policy._fmtkey("ccullen@easydns.com", "chapps.io")
        assert redis_key == "sda:ccullen@easydns.com:chapps.io"

    @pytest.mark.parametrize(
        "auto_ppr, expected_result",
        auto_ppr_param_list,
        ids=idfn,
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

    def test_unauthorized_user(self, sda_unauth_ppr, testing_policy_sda):
        result = testing_policy_sda.approve_policy_request(sda_unauth_ppr)
        assert result == False

    ### note that no clearing of Redis is going on
    def test_cached_authed_user(
        self, monkeypatch, sda_allowable_ppr, testing_policy_sda
    ):
        mock_acq_pol_data = Mock(result=False)
        with monkeypatch.context() as m:
            m.setattr(testing_policy_sda, "acquire_policy_for", mock_acq_pol_data)
            result = testing_policy_sda.approve_policy_request(sda_allowable_ppr)
        mock_acq_pol_data.assert_not_called()

    ### For completeness we will test both
    def test_cached_unauth_user(self, monkeypatch, sda_unauth_ppr, testing_policy_sda):
        mock_acq_pol_data = Mock(result=True)
        with monkeypatch.context() as m:
            m.setattr(testing_policy_sda, "acquire_policy_for", mock_acq_pol_data)
            result = testing_policy_sda.approve_policy_request(sda_unauth_ppr)
        mock_acq_pol_data.assert_not_called()
