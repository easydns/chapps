"""Fixtures for testing of CHAPPS policy module"""
import pytest
from pytest import fixture
from unittest.mock import Mock
from chapps.signals import TooManyAtsException, NotAnEmailAddressException
from chapps.tests.test_config.conftest import (
    chapps_mock_config,
    chapps_mock_env,
    chapps_mock_cfg_path,
    chapps_mock_config_file,
)
from chapps.tests.test_util.conftest import (
    postfix_policy_request_message,
    postfix_policy_request_payload,
    _postfix_policy_request_message,
)
from chapps.tests.test_adapter.conftest import (
    base_adapter_fixture,
    finalizing_pcadapter,
    database_fixture,
    populated_database_fixture,
)
from chapps.tests.conftest import (
    _unique_instance,
    _mock_client_tally,
    _clear_redis,
    _populate_redis_grl,
)
import redis
import time
import random
import string
from chapps.config import CHAPPSConfig
from chapps.policy import (
    OutboundQuotaPolicy,
    GreylistingPolicy,
    SenderDomainAuthPolicy,
)
from chapps.util import PostfixPolicyRequest
from chapps.outbound import OutboundPPR
from chapps.signals import NullSenderException

seconds_per_day = 3600 * 24


@fixture
def testing_policy(chapps_mock_env, chapps_mock_config_file):
    newconfig = CHAPPSConfig()
    policy = OutboundQuotaPolicy(newconfig)
    return policy


@fixture
def testing_policy_sda(chapps_mock_env, chapps_mock_config_file):
    newconfig = CHAPPSConfig()
    policy = SenderDomainAuthPolicy(newconfig)
    return policy


@fixture
def null_sender_policy_sda(
    chapps_mock_env, chapps_mock_config_file, monkeypatch
):
    newconfig = CHAPPSConfig()
    policy = SenderDomainAuthPolicy(newconfig)
    apr = Mock(name="approve_policy_request", side_effect=NullSenderException)
    monkeypatch.setattr(policy, "approve_policy_request", apr)
    return policy


@fixture
def testing_policy_grl(chapps_mock_env, chapps_mock_config_file):
    newconfig = CHAPPSConfig()
    policy = GreylistingPolicy(newconfig)
    return policy


@fixture
def testing_policy_spf():
    # insert logic similar to above, to have an alternate config
    # for testing SPF there seems little reason
    return None


@fixture
def allowable_ppr(postfix_policy_request_message):
    return OutboundPPR(postfix_policy_request_message("underquota@chapps.io"))


@fixture
def sda_allowable_ppr(postfix_policy_request_message):
    return OutboundPPR(
        postfix_policy_request_message(
            "caleb@chapps.io",
            sasl_username="ccullen@easydns.com",
            ccert_subject="",
        )
    )


@fixture
def sda_unauth_ppr(postfix_policy_request_message):
    return OutboundPPR(
        postfix_policy_request_message(
            "ccullen@easydns.com",
            sasl_username="somebody@chapps.io",
            ccert_subject="",
        )
    )


@fixture
def groupsend_ppr(postfix_policy_request_message):
    return OutboundPPR(
        postfix_policy_request_message(
            "underquota@chapps.io",
            [
                "one@recipient.com",
                "two@recipient.com",
                "three@recipient.com",
                "four@recipient.com",
                "five@recipient.com",
            ],
        )
    )


@fixture
def multisend_ppr_factory(random_recipient, postfix_policy_request_message):
    def _ppr_factory(sender, recipient_count):
        return OutboundPPR(
            postfix_policy_request_message(
                sender, [random_recipient for _ in range(recipient_count)]
            )
        )

    return _ppr_factory


@fixture
def random_recipient():
    return (
        "".join(random.choice(string.ascii_letters) for _ in range(8))
        + "@recipient.com"
    )


@fixture
def overquota_ppr(postfix_policy_request_message):
    return OutboundPPR(postfix_policy_request_message("overquota@chapps.io"))


@fixture
def undefined_ppr(postfix_policy_request_message):
    return OutboundPPR(postfix_policy_request_message("nonexistent@chapps.io"))


@fixture
def uncached_allowable_ppr(postfix_policy_request_message):
    return OutboundPPR(postfix_policy_request_message("ccullen@easydns.com "))


@fixture
def well_spaced_attempts():
    seconds_per_day = float(3600 * 24)

    def _wsa(number):
        delta = int(seconds_per_day / float(number - 1))
        t0 = time.time() - seconds_per_day
        return [
            t0 + float(t) + (float(delta) * random.random())
            for t in range(0, int(seconds_per_day), delta)
        ]

    return _wsa


@fixture
def well_spaced_double_attempts(well_spaced_attempts):
    wsa = well_spaced_attempts

    def _wsda(number):
        array = wsa(number - 1)
        array.append(time.time())
        return array

    return _wsda


@fixture
def rapid_attempts():
    def _ra(number):
        t0 = int(time.time()) - number
        return [t0 + t for t in range(0, number)]

    return _ra


@fixture
def populate_redis(clear_redis):
    fmtkey = OutboundQuotaPolicy._fmtkey

    def _popredis(email, limit, timestamps=[], margin=0):
        rh = redis.Redis()
        with rh.pipeline() as pipe:
            pipe.delete(
                fmtkey(email, "limit"),
                fmtkey(email, "attempts"),
                fmtkey(email, "margin"),
            )
            pipe.set(fmtkey(email, "limit"), limit)
            pipe.set(fmtkey(email, "margin"), margin)
            pipe.zadd(fmtkey(email, "attempts"), {t: t for t in timestamps})
            pipe.execute()

    yield _popredis
    rh = redis.Redis()
    keys = rh.keys("oqp:*")
    if len(keys) > 0:
        rh.delete(*keys)


@fixture
def populate_redis_multi(clear_redis):
    fmtkey = OutboundQuotaPolicy._fmtkey

    def _popredis(email, limit, timestamps=[], margin=0):
        rh = redis.Redis()
        with rh.pipeline() as pipe:
            pipe.delete(
                fmtkey(email, "limit"),
                fmtkey(email, "attempts"),
                fmtkey(email, "margin"),
            )
            pipe.set(fmtkey(email, "limit"), limit)
            pipe.set(fmtkey(email, "margin"), margin)
            pipe.zadd(
                fmtkey(email, "attempts"),
                {str(t) + ":00001": t for t in timestamps},
            )
            pipe.execute()

    yield _popredis
    rh = redis.Redis()
    keys = rh.keys("oqp:*")
    if len(keys) > 0:
        rh.delete(*keys)


@fixture
def clear_redis():
    return _clear_redis("oqp ")


@fixture
def clear_redis_grl():
    return _clear_redis("grl")


@fixture
def clear_redis_sda():
    return _clear_redis("sda")


@fixture
def populate_redis_grl(clear_redis_grl):
    yield _populate_redis_grl
    clear_redis_grl()


@fixture
def unique_instance():
    return _unique_instance()


@fixture
def mock_client_tally(unique_instance):
    return _mock_client_tally(unique_instance)


def _mock_spf_query(result, message):
    mock = Mock(name="spf_query")
    mock.check = Mock(name="check", return_value=(result, None, message))
    mock.get_header = Mock(
        name="get_header", return_value="X-CHAPPSTESTING: SPF prepend"
    )
    return mock


def mock_spf_query(result, message):
    return Mock(name="query", return_value=_mock_spf_query(result, message))


def mock_spf_queries(*tuples):
    results = [_mock_spf_query(res, msg) for res, msg in tuples]
    return Mock(name="query", side_effect=results)


@fixture
def passing_spf_query():
    return mock_spf_query("pass", "CHAPPS passing SPF message")


@fixture
def failing_spf_query():
    return mock_spf_query("fail", "CHAPPS failing SPF message")


@fixture
def temperror_spf_query():
    return mock_spf_query("temperror", "CHAPPS temperror SPF message")


@fixture
def permerror_spf_query():
    return mock_spf_query("permerror", "CHAPPS permerror SPF message")


@fixture
def none_spf_query():
    return mock_spf_query("none", "")


@fixture
def neutral_spf_query():
    return mock_spf_query("neutral", "CHAPPS neutral SPF message")


@fixture
def softfail_spf_query():
    return mock_spf_query("softfail", "CHAPPS softfail SPF message")


@fixture(scope="function")
def auto_spf_query(request):
    return mock_spf_queries(*(request.param))


@fixture
def no_helo_passing_mf():
    return mock_spf_queries(
        ("none", ""), ("pass", "CHAPPS passing SPF message")
    )


@fixture
def failing_helo_passing_mf():
    return mock_spf_queries(
        ("fail", "CHAPPS failing SPF message"),
        ("pass", "CHAPPS passing SPF message"),
    )


@fixture
def passing_helo_failing_mf():
    return mock_spf_queries(
        ("pass", "CHAPPS passing SPF message"),
        ("fail", "CHAPPS failing SPF message"),
    )


@fixture
def no_helo_softfail_mf():
    return mock_spf_queries(
        ("none", ""), ("softfail", "CHAPPS softfail SPF message")
    )


### Definitions for parameterization of SPF testing
def idfn(val):
    if type(val) == tuple:
        return f"{val[0][0]}-{val[1][0]}"
    if type(val) == PostfixPolicyRequest or type(val) == OutboundPPR:
        return f"{val.sender}"


def _spf_results():
    return dict(
        passing=("pass", "CHAPPS passing SPF message"),
        fail=("fail", "CHAPPS failing SPF message"),
        softfail=("softfail", "CHAPPS softfail SPF message"),
        permerror=("permerror", "CHAPPS permerror SPF message"),
        temperror=("temperror", "CHAPPS temperror SPF message"),
        neutral=("neutral", "CHAPPS neutral SPF message"),
        none=("none", ""),
    )


def _spf_actions():
    return dict(
        passing="PREPEND X-CHAPPSTESTING: SPF prepend",
        fail="550 5.7.1 SPF check failed: CHAPPS failing SPF message",
        softfail="DEFER_IF_PERMIT Service temporarily unavailable - greylisted CHAPPS softfail SPF message",
        none="DEFER_IF_PERMIT Service temporarily unavailable - greylisted due to SPF enforcement policy",
        neutral="DEFER_IF_PERMIT Service temporarily unavailable - greylisted CHAPPS neutral SPF message",
        permerror="550 5.5.2 SPF record(s) are malformed: CHAPPS permerror SPF message",
        temperror="451 4.4.3 SPF record(s) temporarily unavailable: CHAPPS temperror SPF message",
    )


def _auto_query_param_list(helo_list=["fail"]):
    result = []
    spf_actions = _spf_actions()
    spf_results = (
        _spf_results()
    )  # TODO: profile to see if nested for would be faster
    [
        result.extend(
            [
                (
                    (first, second),
                    spf_actions[
                        inner_key if outer_key not in helo_list else outer_key
                    ],
                )
                for inner_key, second in spf_results.items()
            ]
        )
        for outer_key, first in spf_results.items()
    ]
    return result


def _auto_ppr_param_list(*, senders=["ccullen@easydns.com"]):
    """
    Return tuples of sender and expected result,
    generally the sender domain
    """

    def count_ats(s):
        """Count the @s in a string"""
        return 0 if len(s) == 0 else len([c for c in s if c == "@"])

    ui = _unique_instance("deafbeef")  # returns a callable

    def ppr_for(s):
        pprm = _postfix_policy_request_message()  # returns a callable
        return PostfixPolicyRequest(pprm(s, instance=ui()))

    params = []
    for s in senders:
        ats = count_ats(s)
        if ats == 1:
            params.append((ppr_for(s), s[s.index("@") + 1 :]))
        elif ats > 1:
            params.append((ppr_for(s), TooManyAtsException))
        else:
            params.append((ppr_for(s), NotAnEmailAddressException))
    return params
