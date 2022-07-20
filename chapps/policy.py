"""
Policy managers
---------------

All email policy managers inherit from :class:`~.EmailPolicy`, which provides a
fair amount of base functionality useful to its subclasses.  So far, all but
the :class:`~.SPFEnforcementPolicy` are contained here.  That one has
extra dependencies which are thus kept isolated.  Find it in
:mod:`.spf_policy`.

"""
import time
from contextlib import contextmanager
from collections import deque
from typing import List, Dict, Union, Optional, Tuple
import functools
import redis
import logging
from expiring_dict import ExpiringDict
from chapps.config import config, CHAPPSConfig
from chapps.adapter import (
    MariaDBQuotaAdapter,
    MariaDBSenderDomainAuthAdapter,
    MariaDBInboundFlagsAdapter,
)
from chapps.signals import (
    TooManyAtsException,
    NullSenderException,
    NotAnEmailAddressException,
    NoRecipientsException,
)
from chapps.models import Quota, SDAStatus, PolicyResponse
from chapps.util import PostfixPolicyRequest
from chapps.outbound import OutboundPPR
from chapps.inbound import InboundPPR

policy_response = PolicyResponse.policy_response  # a parameterized decorator
logger = logging.getLogger(__name__)
seconds_per_day = 3600 * 24
SENTINEL_TIMEOUT = 0.1
TIME_FORMAT = "%d %b %Y %H:%M:%S %z"

# There are a number of commented debug statements in this module
# This is for convenience, because in production these routines need
# to be as performant as possible, but these messages are often very
# helpful for diagnosing problems during testing and debugging


class EmailPolicy:
    """Abstract policy manager

    Subclasses must:
      * set class attribute `redis_key_prefix` to a unique value.
      * define an instance method called :meth:`~.approve_policy_request`.

    This abstract superclass provides a standard framework for constructing
    Redis keys, since the main purpose of the policy manager is to make
    decisions about email by consulting Redis.

    Instance attributes:

      :config: :class:`chapps.config.CHAPPSConfig` either passed in
        during initialization or inherited from the environment

      :params: :class:`chapps.util.AttrDict` corresponding to the config
        for the policy manager

      :sentinel: a :class:`redis.Sentinel` handle, or `None` if using
        only Redis

      :redis: a :class:`redis.Redis` handle

    """

    redis_key_prefix = "chapps"
    """A placeholder value, since this class is abstract

    Subclasses should set this to a unique prefix identifying the policy
    manager.  For examples, see the included subclasses.

    """

    @staticmethod
    def rediskey(prefix: str, *args):
        """Format a string to serve as a Redis key for arbitrary data

        :param str prefix: a prefix unique to the policy manager (subclass)
        :param List[str] args: a list of strings to use to construct the rest
          of the key

        In CHAPPS, each policy has its own prefix.  What other data the policy
        uses to construct the key is not relevant to any other entities, though
        it must be sent as a string.

        This routine simply joins up all the tokens with colon (`:`)
        characters, so it is not recommended to use them as part of the
        key-components (although it should 'just work').

        """
        return f"{ prefix }:{ ':'.join( args ) }"

    @classmethod
    def _fmtkey(cls, *args):
        """Convenience classmethod for Redis key construction

        :param List[str] args: a list of key components

        Subclasses may use this method which automatically discovers the
        prefix.

        :meta public:
        """
        return cls.rediskey(cls.redis_key_prefix, *args)

    def __init__(self, cfg: CHAPPSConfig = None):
        """Sets up a new policy manager

        :param chapps.config.CHAPPSConfig cfg: optional :class:`CHAPPSConfig`
          object for config override

        Store the config and get the params for the specific policy class,
        which are in a config block named for the class.  Using that config, set
        the policy manager up with a Redis handle, and an instance cache (from
        :class:`expiring_dict.ExpiringDict`)

        """
        self.config = cfg if cfg else config
        self.params = self.config.get_block(self.__class__.__name__)
        self.sentinel = None
        self.redis = self._redis()  # pass True to get read-only
        self.instance_cache = ExpiringDict(3)  # entries expire after 3 seconds

    @contextmanager
    def _adapter_handle(self):
        """Context manager for obtaining a database handle

        In order to acquire policy configuration data, the policy manager must
        be able to reach the RDBMS or other policy-config data store.  One of
        the policy manager's priciple jobs is to obtain this data from the
        database and stuff it into Redis for future reference.

        Adapter configuration, in terms of how to access the database, is
        obtained from the config object.

        .. todo::

          It is clear now that the adapter classes should also accept an
          optional config argument, and then use it for default values, so that
          this routine need not enumerate all the options.

        :meta public:
        """
        adapter = self.adapter_class(cfg=self.config)
        try:
            yield adapter
        finally:
            adapter.conn.close()

    @contextmanager
    def _control_data_storage_context(self):
        """Context manager for storing control data in Redis

        This is the most basic of routines, provided for policies which store
        only one item in Redis, perhaps an option flag for instance.

        The context manager yields a callable which expects up to three
        arguments:

        .. code::

            dsc(token, setting, expire=seconds_per_day)

        :token: is a token unique to the resource along with the setting.  The
                `redis_key_prefix` is automatically prepended to the token.  If
                the token is otherwise compound, it should be compounded
                beforehand and presented as a string.

        :setting: is the value to be stored in Redis

        :expire: the Redis entry's TTL in seconds; defaults to 24hr

        This pattern is used throughout the policy managers to handle making
        Redis settings in pipelines.  Some policy managers declare overrides
        for this method, in order to automate creation of compound keys or to
        store more than one piece of data at once.  Where a policy has a
        per-domain enforcement flag, that flag is generally being stored on a
        Redis key formed by tacking the `redis_key_prefix` onto the front of
        the domain name.

        In practice, to use this context manager, capture its yielded output
        and call it in order to store data:

        .. code::

            resource_settings_map = {d: True for d in domains}
            with policy._control_data_storage_context() as dsc:
                for domain, option in resource_settings_map.items():
                    dsc(domain, option)

        If there are a number of settings to create, make sure to place the
        loop within the context so that all the settings will be submitted as
        part of the same pipeline.

        """
        pipe = self.redis.pipeline()
        fmtkey = self._fmtkey

        def _dsc(token, setting, expire=seconds_per_day):
            pipe.set(fmtkey(token), setting, ex=expire)

        try:
            yield _dsc
        finally:
            pipe.execute()
            pipe.reset()

    def _redis(self, read_only: bool = False):
        """Get a Redis handle, possibly from Sentinel

        :param bool read_only: if Sentinel is in use, get a read-only handle

        If you're not using Sentinel, the `read_only` parameter is
        meaningless.

        """
        try:
            if self.config.redis.sentinel_servers and not self.sentinel:
                self.sentinel = redis.Sentinel(
                    [
                        s.split(":")
                        for s in self.config.redis.sentinel_servers.split(" ")
                    ],
                    socket_timeout=SENTINEL_TIMEOUT,
                )
            if self.sentinel:
                if read_only:
                    rh = self.sentinel.slave_for(
                        self.config.redis.sentinel_dataset,
                        socket_timeout=SENTINEL_TIMEOUT,
                    )
                else:
                    rh = self.sentinel.master_for(
                        self.config.redis.sentinel_dataset,
                        socket_timeout=SENTINEL_TIMEOUT,
                    )
                return rh
        except AttributeError:
            pass
        return redis.Redis(
            host=self.config.redis.server, port=self.config.redis.port
        )

    def approve_policy_request(
        self, ppr: PostfixPolicyRequest, **opts
    ) -> Union[str, bool]:
        """Determine a policy outcome based on the PPR provided

        This routine may return a boolean PASS/FAIL response, or it may for
        some policy classes return a string, which represents the policy
        outcome and is suitable for sending to Postfix.

        The result of the policy approval is cached based on the instance value
        provided by Postfix.  The memoization is done here in the superclass in
        order to avoid duplication of memoization code.

        """
        response = self.instance_cache.get(ppr.instance, None)
        if response is None:
            response = self._approve_policy_request(ppr, **opts)
            self.instance_cache[ppr.instance] = response
        return response

    def _approve_policy_request(
        self, ppr: PostfixPolicyRequest, **opts
    ) -> Union[str, bool]:
        """Placeholder method which must be implemented by subclasses.
        """
        raise NotImplementedError(
            "Subclasses of EmailPolicy must implement this function."
        )


class PostfixActions:
    """Superclass for Postfix action adapters"""

    @staticmethod
    def dunno(*args, **kwargs):
        """Return the Postfix directive `DUNNO`"""
        return "DUNNO"

    @staticmethod
    def okay(*args, **kwargs):
        """Return the Postfix directive `OK`"""
        return "OK"

    ok = okay
    """`ok()` is an alias for `okay()`"""

    @staticmethod
    def defer_if_permit(msg, *args, **kwargs):
        """
        Return the Postfix `DEFER_IF_PERMIT` directive with the provided
        message
        """
        return f"DEFER_IF_PERMIT {msg}"

    @staticmethod
    def reject(msg, *args, **kwargs):
        """
        Return the Postfix `REJECT` directive along with the provided message
        """
        return f"REJECT {msg}"

    @staticmethod
    def prepend(*args, **kwargs):
        """
        Return the Postfix `PREPEND` directive.
        Include the header to prepend as keyword-argument `prepend`
        """
        new_header = kwargs.get("prepend", None)
        if new_header is None or len(new_header) < 5:
            raise ValueError(
                f"Prepended header expected to be at least 5 chars in length."
            )
        return f"PREPEND {new_header}"

    def __init__(self, cfg=None):
        """
        Optionally supply a :py:class:`chapps.config.CHAPPSConfig` instance as
        the first argument.
        """
        self.config = cfg or config
        self.params = self.config  # later this is overridden, in subclasses

    def _get_closure_for(
        self, decision: str, *, passing: Optional[bool] = None
    ):
        """Setup the prescribed closure for generating SMTP action directives"""
        action_config = getattr(self.params, decision, None)
        if not action_config:
            raise ValueError(
                f"Action config for {self.__class__.__name__} does not contain a key named {decision}"
            )
        action_tokens = action_config.split(" ")
        action = action_tokens[0]
        try:
            i = int(action)  #  if the first token is a number, its a directive
        except ValueError:  #  first token was a string, and therefore refers to a method
            # look for predefined or memoized version
            af = getattr(self, action, None)
            if af:
                return af
            # no local version found, find function reference
            action_func = getattr(PostfixActions, action, None)
            if not action_func:
                action_func = getattr(self.__class__, action, None)
            if not action_func:
                raise NotImplementedError(
                    f"Action {action} is not implemented by PostfixActions"
                    f" or by {self.__class__.__name__}"
                )
        else:
            # construct closure from configured message string
            action_func = lambda reason, ppr, *args, **kwargs: action_config.format(
                reason=reason
            )
        passing = (
            (action_func in [self.reject, self.defer_if_permit])
            if passing is None
            else passing
        )
        action_func = policy_response(passing, action)(action_func)
        # memoize the action function for quicker reference next time
        setattr(self, action, action_func)
        return action_func

    def _get_message_for(self, decision, config_name=None):
        """Grab a status message for a decision from the config, optionally with another name"""
        msg_key = config_name or decision
        msg = getattr(self, msg_key, None)
        if not msg:
            raise ValueError(
                f"There is no key {msg_key} in the config for {self.__class__.__name__} or its policy"
            )
        return msg

    def _mangle_action(self, action):
        """
        Policy decisions which are also reserved words need to be altered.
        Currently, this routine handles only the action 'pass'
        """
        if action == "pass":
            return "passing"
        return action

    def action_for(self, *args, **kwargs):
        """Abstract method which must be implemented in subclasses.

        This method is intended to map responses from a policy
        manager onto Postfix directives.

        Not all policy managers return only yes/no answers.  Some, like
        :py:class:`chapps.spf_policy.SPFEnforcementPolicy`, return a handful of
        different possible values, and so there must be a mechanism for
        allowing sites to determine what happens when each of those different
        outcomes occurs.

        """
        raise NotImplementedError(
            f"Subclasses of {self.__class__.__name__} must define the method"
            " action_for() for themselves, to map policy module responses"
            " (decisions) onto Postfix action directives."
        )


class PostfixPassfailActions(PostfixActions):
    """Postfix Actions adapter for PASS/FAIL policy responses.

    Many policies return `True` if the email should be accepted/forwarded and
    return `False` if the email should be rejected/dropped.  This class
    encapsulates the common case, and includes some logic to extract precise
    instructions from the config.

    """

    def __init__(self, cfg=None):
        super().__init__(cfg)

    def _get_closure_for(
        self, decision, *, passing: bool = None, msg_key: str = None
    ):
        """Create a closure for formatting these messages and store it on
        self.<decision>, and also return it
        """
        msg_key = msg_key or decision
        msg = getattr(self.params, msg_key, None)
        if not msg:
            raise ValueError(
                f"The key '{msg_key}' is not defined in the config for"
                f" {self.__class__.__name__} or its policy"
            )
        msg_tokens = msg.split(" ")
        msg_text = ""
        if msg_tokens[0] == "OK":
            func = PostfixActions.okay
        elif msg_tokens[0] == "DUNNO":
            func = PostfixActions.dunno
        elif msg_tokens[0] == "DEFER_IF_PERMIT":
            func = PostfixActions.defer_if_permit
            msg_text = " ".join(msg_tokens[1:])
        elif msg_tokens[0] == "REJECT" or msg_tokens[0] == "554":
            func = PostfixActions.reject
            msg_text = " ".join(msg_tokens[1:])
        else:
            raise NotImplementedError(
                "Pass-fail closure creation for Postfix directive"
                f" {msg_tokens[0]} is not yet available."
            )
        action = policy_response(
            (
                passing
                if passing is not None
                else (func != PostfixActions.reject)
            ),
            decision,
        )(self.__prepend_action_with_message(func, msg_text))
        setattr(self, decision, action)
        return action

    def __prepend_action_with_message(self, func, prepend_msg_text):
        """Wrap an action func in order to prepend an additional message"""
        # avoiding use of nonlocal required if definition is embedded inline
        # in calling procedure
        def action(message="", *args, **kwargs):
            msg_text = prepend_msg_text
            if len(message) > 0:
                msg_text = " ".join([msg_text, message])
            return func(msg_text, *args, **kwargs)

        return action

    def action_for(self, pf_result):
        """Return an action closure for a pass/fail policy

        Evaluates its argument `pf_result` as a boolean and returns the
        action closure for 'passing' if True, otherwise the action closure for
        'fail'.  To provide backwards-compatibility with older versions, and to
        allow for more descriptive configuration elements, the actions may be
        attached to keys named `acceptance_message` or `rejection_message`
        instead of `passing` and `fail` respectively.  This is only true
        of policies with action factories inheriting from
        :py:class:`chapps.actions.PostfixPassfailActions`

        """
        if pf_result:  # True / pass
            action_name = "passing"
        else:  # False / fail
            action_name = "fail"
        return getattr(self, action_name, None)

    def __getattr__(self, attrname, *args, **kwargs):
        """Allow use of old config elements with long descriptive names."""
        attrname = self._mangle_action(attrname)
        if attrname == "passing":
            msg_key = "acceptance_message"
        elif attrname == "fail":
            msg_key = "rejection_message"
        else:
            raise NotImplementedError(
                f"Pass-fail actions do not include {attrname}"
            )
        return self._get_closure_for(
            attrname, msg_key=msg_key, passing=(attrname == "passing")
        )


class PostfixOQPActions(PostfixPassfailActions):
    """Postfix Action translator for :py:class:`chapps.policy.OutboundQuotaPolicy`"""

    def __init__(self, cfg=None):
        """
        Optionally provide an instance of :py::class`chapps.config.CHAPPSConfig`.

        All this class does is wire up `self.config` to
        point at the :py:class:`chapps.policy.OutboundQuotaPolicy` config block.
        """
        super().__init__(cfg)
        self.params = self.config.policy_oqp


class PostfixGRLActions(PostfixPassfailActions):
    """Postfix Action translator for :py:class:`chapps.policy.GreylistingPolicy`"""

    def __init__(self, cfg=None):
        """
        Optionally provide an instance of :py:class:`chapps.config.CHAPPSConfig`.

        All this class does is wire up `self.config` to
        point at the :py:class:`chapps.policy.GreylistingPolicy` config block.
        """
        super().__init__(cfg)
        self.params = self.config.policy_grl


class InboundPolicy(EmailPolicy):
    adapter_class = MariaDBInboundFlagsAdapter

    def domain_option_key(self, ppr: InboundPPR):
        """Return the Redis key for the domain's Greylisting option

        Uses the first of the list of tokenized recipients.  Generally,
        inbound mail is expected to contain only one recipient per email.
        """
        return self._domain_option_key(ppr.recipient_domain)

    def _domain_option_key(self, recipient_domain):
        return self._fmtkey(recipient_domain)

    def _store_control_data(self, domain: str, flag: bool):
        with self._control_data_storage_context() as dsc:
            dsc(domain, 1 if flag else 0)


class GreylistingPolicy(InboundPolicy):
    """Policy manager which implements greylisting

    `Greylisting <https://en.wikipedia.org/wiki/Greylisting_(email)>`_ is a
    `well-defined <https://datatracker.ietf.org/doc/html/rfc6647>`_ and
    frequently-implemented pattern.  This implementation stores the tracking
    information in Redis.

    Instance attributes (in addition to those of :class:`.EmailPolicy`):

      :min_defer: minimum time between retries, in seconds

      :cache_ttl: how long to store tracking data, in seconds

      :allow_after: success threshold, after which the client may be
        whitelisted

    """

    redis_key_prefix = "grl"
    """Greylisting Redis key prefix"""

    def __init__(
        self,
        cfg: CHAPPSConfig = None,
        *,
        minimum_deferral: int = 60,
        cache_ttl: int = seconds_per_day,
        auto_allow_after: int = None,
    ):
        """Initialize a greylisting policy manager

        :param chapps.config.CHAPPSConfig cfg: optional config override

        :param int minimum_deferral: min time between retries, in seconds

        :param int cache_ttl: tracking data cache expiration time in seconds

        :param int auto_allow_after: number of successful attempts needed
          before source client is considered trusted, and no longer incurs
          deferrals

        """
        super().__init__(cfg)
        self.actions = PostfixGRLActions(self.config)
        self.min_defer = minimum_deferral
        self.cache_ttl = cache_ttl
        self.allow_after = (
            auto_allow_after
            if auto_allow_after is not None
            else self.params.whitelist_threshold
        )
        if self.cache_ttl <= self.min_defer:
            logger.warning(
                f"Cache TTL (={datetime.timedelta(seconds=self.cache_ttl)}) is not allowed to be smaller than or equal to the minimum deferral window (={datetime.timedelta(seconds=self.min_defer)}).  Defaulting to 24 hr."
            )
            self.cache_ttl = seconds_per_day
        if self.min_defer > 60 * 15:
            logger.warning(
                f"It may be unreasonable to expect the sending server to defer for more than 15 minutes. (={self.min_defer/60.0:.2f}m)"
            )
        if self.allow_after == 0:
            logger.warning(f"Sender auto-approval is turned off.")
        elif self.allow_after < 2:
            logger.warning(
                f"Sender auto-approval is set to a fairly low threshold. (={self.allow_after})"
            )

    def tuple_key(self, ppr: PostfixPolicyRequest) -> str:
        """Return the greylisting tuple as a Redis key

        The names of the values taken from `ppr` are as follows (in order):

             - `client_address`
             - `sender`
             - `recipient`

        """
        return self._tuple_key(ppr.client_address, ppr.sender, ppr.recipient)

    def _tuple_key(self, client_address, sender, recipient):
        return self._fmtkey(client_address, sender, recipient)

    def client_key(self, ppr: PostfixPolicyRequest):
        """Return the greylisting client key

        This key indicates whether the client has enough successful
        resubmissions to be whitelisted.

        """
        return self._client_key(ppr.client_address)

    def _client_key(self, client_address):
        return self._fmtkey(client_address)

    def acquire_policy_for(self, ppr: InboundPPR):
        with self._adapter_handle() as adapter:
            result = adapter.do_greylisting_on(ppr.recipient_domain)
        logger.debug(
            "Got greylisting option flag "
            + str(result)
            + " from RDBMS for domain "
            + ppr.recipient_domain
        )
        self._store_control_data(ppr.recipient_domain, 1 if result else 0)
        return result

    def _approve_policy_request(self, ppr: InboundPPR, **opts):
        """Perform greylisting

        .. todo::

            It would be possible to allow domains to set the whitelisting
            threshhold, since this routine has to obtain option flag data from
            the policy config source at this point anyway.  Because we're also
            concerned with time between attempts, we could also do some
            time-based things here, such as starting to refuse clients who
            retry much too quickly, implementing per-domain rules about how
            frequently a client is allowed to send email to their addresses,
            etc.

        :meta public:
        """
        option_set, tuple_seen, client_tally = None, None, None
        try:
            option_set, tuple_seen, client_tally = self._get_control_data(ppr)
            if option_set is None:
                option_set = self.acquire_policy_for(ppr)
        except NoRecipientsException:
            logger.exception(f"No recipient in PPR {ppr.instance}.")
            return False
        except Exception:  # pragma: no cover
            logger.exception("UNEXPECTED")
            logger.debug(
                f"Returning denial for {ppr.instance} (unexpected exception)."
            )
        if opts.get("force", False):
            option_set = True
        if not option_set:
            logger.debug(
                "Not enforcing greylisting for domain "
                f"{ppr.recipient_domain or 'N/A'}"
            )
            return "DUNNO"  # not enforcing this policy
        # if not whitelisting, client_tally will be None
        if client_tally is not None and client_tally >= self.allow_after:
            self._update_client_tally(ppr)
            return self.actions.action_for(True)("", ppr=ppr)
        if tuple_seen:
            # The tuple is recognized; need to check if it was long enough ago
            now = time.time()
            if now - tuple_seen >= self.min_defer:
                # the email will be approved; some housekeeping is necessary
                self._update_client_tally(ppr)
                return self.actions.action_for(True)("", ppr=ppr)
        # if we get here, the tuple either isn't stored or was stored too
        # recently; either way, we update it
        self._update_tuple(ppr)
        return self.actions.action_for(False)("", ppr=ppr)

    def _get_control_data(self, ppr: InboundPPR):
        """Extract data from Redis in order to answer the policy request"""
        now = time.time()
        tuple_key = self.tuple_key(ppr)
        client_key = self.client_key(ppr)
        option_key = self.domain_option_key(ppr)
        logger.debug(
            f"Redis keys: tuple={tuple_key} opt={option_key} client={client_key} (zrange)"
        )
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(client_key, 0, now - float(self.cache_ttl))
        pipe.get(tuple_key)
        pipe.get(option_key)
        if self.allow_after > 0:
            pipe.zrange(client_key, 0, -1)

        result = pipe.execute()
        logger.debug(f"Redis result: {result!r}")
        tuple_bits = result[1]
        option_bits = result[2]
        if len(result) == 4:
            client_tally_bits = result[3]

        tuple_seen = (
            float(tuple_bits) if tuple_bits else None
        )  # UNIX epoch time
        option_set = int(option_bits) if option_bits else None
        client_tally = None
        if self.allow_after > 0 and client_tally_bits:
            client_tally = len(client_tally_bits)
        return (option_set, tuple_seen, client_tally)

    def _update_client_tally(self, ppr: InboundPPR):
        """Update client reliability score in Redis

        When an email is allowed, increment the reliability score of the
        client.

        """
        if self.allow_after == 0:  # if we're not keeping a tally, return
            return
        now = time.time()
        client_key = self.client_key(ppr)
        with self.redis.pipeline() as pipe:
            pipe.zadd(client_key, {ppr.instance: now})
            pipe.zremrangebyrank(
                client_key, 0, -(self.allow_after + 2)
            )  # keep one extra
            pipe.expire(client_key, self.cache_ttl)
            pipe.execute()

    def _update_tuple(self, ppr: InboundPPR):
        """Set or update a greylisting tuple in Redis"""
        self.redis.setex(self.tuple_key(ppr), self.cache_ttl, time.time())


class OutboundQuotaPolicy(EmailPolicy):
    """Policy manager which implements an outbound quota limitation

    Outbound email is controlled based on the count of (attempted)
    transmissions in the last 24 hours.  Some parameters are provided to
    fine-tune the behavior of the limiting algorithm.

    Instance attributes (in addition to those of :class:`.EmailPolicy`):

      :interval: number of seconds to store transmission attemps, and
          to use for quota evaluation; defaults to one day

      :counting_recipients: a boolean determined from the config; whether to
        count each recipient of a multi-recipient email as a separate
        transmission for quota purposes

      :min_delta: defaults to 0; if set, the number of seconds which
        must elapse between send attempts.  **Currently experimental**

    """

    adapter_class = MariaDBQuotaAdapter
    redis_key_prefix = "oqp"
    """OutboundQuotaPolicy Redis prefix"""

    def __init__(self, cfg=None, *, enforcement_interval=None, min_delta=0):
        """Set up an outbound quota policy manager

        :param chapps.config.CHAPPSConfig cfg: optional config override

        :param int enforcement_interval: number of seconds to store
          transmission attemps, and to use for quota evaluation; defaults to
          one day

        :param int min_delta: Minimum time which must pass between
          transmission attempts; defaults to 5 seconds to prevent spamming.
          Set to 0 to disable

        """
        super().__init__(cfg)  # sets attrs 'config', 'params', and 'redis'
        self.interval = (
            enforcement_interval if enforcement_interval else seconds_per_day
        )
        if hasattr(self.params, "min_delta"):
            self.min_delta = self.params.min_delta
        elif min_delta:
            self.min_delta = min_delta
        else:
            self.min_delta = 0
        self.min_delta = float(self.min_delta)
        self.counting_recipients = (
            self.params.counting_recipients
            if hasattr(self.params, "counting_recipients")
            else False
        )

    @contextmanager
    def _control_data_storage_context(self):
        """Atomic context manager for Redis updates

        Yields a closure which takes the tuple (email, quota, margin) and
        adds it to a Redis pipeline, which will set it in Redis once the
        context is closed.

        Intended to be used as a context manager, like so:

        .. code::python
            with self._control_data_storage_context() as store:
                store(user_identifier, quota_count, margin_count)

        This is most useful when collections of data are involved, but also
        encapsulates and hides the pipeline management foo required by the
        Redis library.

        """
        pipe = self.redis.pipeline()
        fmtkey = self._fmtkey

        def _dsc(user, quota, margin):
            pipe.set(fmtkey(user, "limit"), quota, ex=seconds_per_day)
            pipe.set(fmtkey(user, "margin"), margin, ex=seconds_per_day)

        try:
            yield _dsc
        finally:
            pipe.execute()
            pipe.reset()

    def _get_control_data(self, ppr):
        """Obtain essential data for policy decisionmaking

        This is the routine which keeps track of emails in Redis.  It
        combines all of its requests into a single pipelined (atomic)
        transaction.  When counting recipients, the record is a string
        consisting of the timestamp and the recipient serial number
        separated by a colon, in order to ensure that each recipient
        is listed as an attempt in the log.  The score is always the
        floating-point return value of time.time()
        """
        # cache the current(ish) time
        time_now = time.time()
        time_now_s = str(time_now)

        user = ppr.user

        # create a dict for Redis.zadd()
        if self.counting_recipients:
            tries_dict = {
                (time_now_s + f":{i:05d}"): time_now
                for i, r in enumerate(ppr.recipients)
            }
        else:
            tries_dict = {time_now_s: time_now}
        # set up the Redis keys
        tries_key = self._fmtkey(user, "attempts")
        limit_key = self._fmtkey(user, "limit")
        margin_key = self._fmtkey(user, "margin")
        # Create a Redis pipeline to atomize a set of instructions
        pipe = self.redis.pipeline()
        # Clear the list down to just the last interval seconds, generally a day
        pipe.zremrangebyscore(tries_key, 0, time_now - float(self.interval))
        # Add this/these try(es)
        pipe.zadd(tries_key, tries_dict)
        # Get control data: the limit, the margin, the attempts list
        pipe.get(limit_key)
        pipe.get(margin_key)
        pipe.zrange(tries_key, 0, -1)
        # Set expires on all this stuff so that if they don't send
        # email for a day, their data won't still be sitting around
        # takin' up space; these return nil values so we have to
        # ignore them when we get the results
        pipe.expire(tries_key, self.interval)
        pipe.expire(limit_key, self.interval)
        pipe.expire(margin_key, self.interval)
        # Do the thing!
        results = pipe.execute()
        # The non-retrieval operations still have return values, so we ignore them
        removed, _, limit, margin, attempts, _, _, _ = results
        # Always polite to reset your pipe
        pipe.reset()
        # Attempt typecasting on the margin number, which is allowed
        # to be either int or float
        m = self._cast_margin(margin)
        # If no limit is defined, that means there is no quota profile
        # for the user, and we just return None here; we must test against
        # None because it might be 0
        return (int(limit) if limit is not None else None, m, attempts)

    def _cast_margin(self, margin_bytes):
        """Convenience method

        :param bytes margin_bytes: margin value from Redis

        Get the correct type (int or float) from the provided bytestring.

        """
        try:
            m = int(margin_bytes)
        except:
            try:
                m = float(margin_bytes)
            except:
                m = 0
        return m

    def current_quota(
        self, user: str, quota: Optional[Quota] = None
    ) -> Tuple[int, List[str]]:
        """Provide real-time remaining quota for a user

        :param str user: user-identifier

        :param chapps.models.Quota quota: optional
          :class:`~chapps.models.Quota` record

        :returns: (*remaining quota count*, [*remarks*,...])

        :rtype: Tuple[int, List[str]]

        The caller is anticipated to be the API.  The **User** and **Quota**
        are both available, so the **Quota** may be provided, but it is not
        required.  The `user` parameter is expected to contain a string at
        present, though this may change as the :mod:`pydantic` data models
        become more tightly integrated into the codebase.

        The return value, intended for wrapping by the API and transmission to a client, is a tuple composed of:

          1. the number of transmission attempts remaining to the user at the
             moment the query executed

          2. a list of remarks created by the inspection routine

        """
        attempts_key = self._fmtkey(user, "attempts")
        limit_key = self._fmtkey(user, "limit")
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(
            attempts_key, 0, time.time() - float(self.interval)
        )
        pipe.get(limit_key)
        pipe.zrange(attempts_key, 0, -1)
        results = pipe.execute()
        _, limit_bytes, attempts_bytes = results
        pipe.reset()
        limit = (
            int(limit_bytes)
            if limit_bytes is not None
            else quota.quota
            if quota is not None
            else None
        )
        response = limit - len(attempts_bytes) if limit else 0
        remarks = []
        if attempts_bytes:
            last = attempts_bytes[-1]
            try:
                last = float(last)
            except ValueError:
                last = float(last.split(b":")[0])
            last_try = time.strftime(TIME_FORMAT, time.gmtime(last))
            remarks.append(f"Last send attempt was at {last_try}")
        if not limit_bytes:
            remarks.append(f"There is no cached quota limit for {user}.")
        if not quota:
            remarks.append(f"There is no quota configured for user {user}.")
        if not limit:
            remarks.append(
                f"No limit could be found; returning zero xmits remaining."
            )
        return (response, remarks)

    def reset_quota(self, user: str) -> Tuple[int, List[str]]:
        """Reset quota for user

        :param str user: user-identifier

        :returns: (*number of records dropped*, [*remarks*,...])

        :rtype: Tuple[int,List[str]]

        This method is intended for real-time management of the Redis
        configuration mirror.  It will drop all the attempts from the
        outbound-quota transmission-tracking list for the named user.

        """
        attempts_key = self._fmtkey(user, "attempts")
        pipe = self.redis.pipeline()
        pipe.zrange(attempts_key, 0, -1)
        pipe.delete(attempts_key)
        results = pipe.execute()
        pipe.reset()
        attempts = results[0]
        if attempts:
            msg = f"Attempts (quota) reset for {user}:"
            n_att = len(attempts)
        else:
            n_att = 0
            msg = f"No attempts to reset for {user}:"
        msg += f" {n_att} xmits dropped"
        return (n_att, [msg])

    def refresh_policy_cache(self, user: str, quota: Quota):
        """API adapter method for refreshing policy config cache"""
        self.acquire_policy_for(user, quota.quota)
        return self.current_quota(user, quota)

    def _store_control_data(self, user, quota, margin=0):
        """Using a context manager, build up a set of instructions to store control data"""
        with self._control_data_storage_context() as dsc:
            if type(margin) == float:
                if margin > 1.0:
                    if margin < 100.0:
                        margin = margin / 100.0
                    else:
                        raise TypeError(
                            "margin must be a positive integer or a positive float less than 1 (a percentage)"
                        )  # pragma: no cover
                margin = int(margin * float(quota))
            dsc(user, quota, margin)

    def _detect_control_data(self, user):
        """See if there is control data in Redis for a particular sender"""
        key = self._fmtkey(user, "limit")
        res = None
        try:
            res = self.redis.get(key)
        except redis.exceptions.ResponseError:  # pragma: no cover
            # sometimes a key which should not exist still shows up,
            # and accessing them causes this error.  we choose to
            # pretend nothing happened and just delete the key
            self.redis.delete(key)
        return res

    def acquire_policy_for(self, user: str, quota: Optional[int] = None):
        """Populate Redis with policy config data for a user

        :param str user: user-identifier

        :param int quota: optional quota to load for the user.  This is
          provided mainly to optimize actions taken by the API.

        Go get the policy for a sender from the policy adapter.

        If the margin needs to be configured on a per-sender basis, this is the
        place to adjust that.  Right now, the margin is set in the config file,
        and applied to each user as policy config is loaded.

        """
        if not quota:
            with self._adapter_handle() as adapter:
                quota = adapter.quota_for_user(user)
        if quota:
            self._store_control_data(user, quota, self.params.margin)

    def _approve_policy_request(self, ppr: OutboundPPR):
        """Determine whether this email falls within the quota

        :param chapps.outbound.OutboundPPR ppr: the Postfix payload

        Returns True if this email is within the quota.

        This routine implements memoization on `ppr.instance` in order to
        overcome the Postfix double-checking weirdness.  Sometimes, Postfix
        sends a request about a given email twice, but this is easy to spot
        because they will have the same value for `ppr.instance`.

        :meta public:
        """
        user = ppr.user
        if not self._detect_control_data(user):
            self.acquire_policy_for(user)
        return self._evaluate_policy_request(ppr)

    def _get_delta(self, ppr, attempts):
        """Obtain the number of seconds between successive attempts

        This routine should calculate the number of seconds between this
        attempt and the previous.  To do so, it must take into account whether
        we are counting each recipient, and parse the attempt record
        accordingly.  When counting recipients, the record is a string
        consisting of the timestamp and the recipient serial number separated
        by a colon, in order to ensure that each recipient is listed as an
        attempt in the log.

        .. admonition: Experimental

          There is some subtle problem with either or both of the logic here
          and in the tests, and so since it was initially provided as an
          interesting extra feature, it is currently disabled and considered
          experimental.  At some point, I intend to come back to it.

        """
        if len(attempts) < 2:
            return float("inf")
        delta_index = [-1, -2]
        if not self.counting_recipients:
            if len(attempts) < 2:
                return float("inf")
        elif len(attempts) > len(ppr.recipients):
            # skip back all but one recipient
            recipients_offset = 0 - len(ppr.recipients)
            delta_index = [d + recipients_offset for d in delta_index]
        else:
            return float("inf")  # automatically wins
        logger.debug(
            f"Looking at time-delta for {ppr}: indices {delta_index!r}"
        )
        try:
            timestamps = [
                float(t.decode("utf-8").split(":")[0])
                if ":" in t.decode("utf-8")
                else float(t.decode("utf-8"))
                for t in [
                    attempts[i] for i in delta_index if i < len(attempts)
                ]
            ]
        except IndexError:
            msg = (
                f"Recipients={-recipients_offset}"
                f" delta_indices={delta_index!r}"
                f" Attempts: (#{len(attempts)})"
            )
            if len(attempts) < 10:
                msg += f" {attempts!r}"
            logger.exception(msg)
            return float("inf")
        if len(timestamps) == 2:
            logger.debug(
                f"attempts: {[attempts[i] for i in delta_index]}; timestamps: {timestamps!r}"
            )
            return timestamps[0] - timestamps[1]
        return float("inf")  # return a large value

    def _evaluate_policy_request(self, ppr):
        """This actually checks to see if it's okay to send the email.

        .. todo::

          in this routine, it would be possible to send pub/sub messages via
          Redis to consumers who might be interested to know that a particular
          user's send-attempts list is over a certain length

        """
        instance, user = ppr.instance, ppr.user
        try:  # this may raise TypeError if the user is unknown
            limit, margin, attempts = self._get_control_data(ppr)
        except Exception:  # pragma: no cover
            logger.exception("UNEXPECTED")
            logger.debug(
                f"Returning denial indicator for {instance} (unexpected exception)."
            )
            return False
        if not limit:  # user does not have a quota profile
            return False
        if len(attempts) < 2:  # this is the first attempt in the Redis history
            logger.debug(f"Returning OK for {instance} (first attempt).")
            return True
        if self.min_delta != 0:  # set up for checking on throttle
            logger.debug(
                f"Checking throttle: {ppr.user}:{instance} limit: {limit} margin: {margin} tries: {len(attempts)}"
            )
            this_delta = self._get_delta(ppr, attempts)
            if this_delta < float(self.min_delta):  # trying too fast
                logger.debug(
                    f"Rejecting {instance} of {user} for trying too fast. ({this_delta}s since last attempt)"
                )
                return False
        if (
            len(attempts) > limit
        ):  # not too fast, check how many send attempts on record
            ### TODO: alert when the attempts list is really long -- perhaps via Redis pub/sub
            if (
                len(attempts) - margin > limit
                or len(attempts) - len(ppr.recipients) >= limit
            ):
                logger.debug(
                    f"Rejecting {instance} of {user} for having too many attempts in the last interval: recip: {len(ppr.recipients)} limit: {limit}; tries: {len(attempts)}"
                )
                return False
            else:
                logger.debug(
                    f"Returning OK for {instance} recip: {len(ppr.recipients)} limit: {limit}; tries: {len(attempts)} (within margin)."
                )
        logger.debug(f"Returning OK for {instance} (under quota).")
        return True


class SenderDomainAuthPolicy(EmailPolicy):
    """Policy manager implementing domain and whole-email matching for senders

    This class encapsulates explicit policy regarding what sorts of
    masquerading authenticated users are allowed to do.  Currently, two sorts
    of matches are handled, in succession.

    First, the domain part of the email address, the entire string after the
    `@`, is matched against **Domain** entries linked to the **User**.

    If there is no **Domain** match, then **Email** entries linked to the
    **User** are checked.  **Email** entries must match the entirety of a
    policy request's `sender` attribute in order to pass.

    """

    adapter_class = MariaDBSenderDomainAuthAdapter
    redis_key_prefix = "sda"
    """Sender domain auth Redis key prefix"""
    # initialization is when we plug in the config
    def __init__(self, cfg: CHAPPSConfig = None):
        """Set up a new sender domain authorization policy manager

        :param chapps.config.CHAPPSConfig cfg: optional config override

        """
        super().__init__(cfg)  # sets attrs 'config' and 'redis'

    # every subclass has one of these, with a unique name, and fine
    # but maybe there should also be a generic single entry point
    def sender_domain_key(self, ppr: OutboundPPR) -> str:
        """Create a Redis key for a user->domain mapping

        :param chapps.outbound.OutboundPPR ppr: a Postfix payload

        :returns: the sender domain key, by obtaining the domain part of the
          email address from `ppr.sender`

        :rtype: str

        """
        return self._sender_domain_key(ppr.user, self._get_sender_domain(ppr))

    def sender_email_key(self, ppr) -> str:
        """Create a Redis key for a user->email mapping

        :param chapps.outbound.OutboundPPR ppr: a Postfix payload

        :returns: the sender email key, by obtaining the email address from
          `ppr.sender`

        :rtype: str

        """
        return self._sender_domain_key(ppr.user, ppr.sender)

    # factored out for use in API
    def _sender_domain_key(self, user: str, domain: str) -> str:
        """Passes its two string params to _fmtkey

        :meta public:
        :param str user: user-identifier

        :param str domain: origin domain or email address

        :returns: a Redis key

        :rtype: str

        Should be called `_sender_auth_key` since it works with both domains
        and email addresses.

        """
        return self._fmtkey(user, domain)

    # determine the domain of the sender address, if any
    @functools.lru_cache(maxsize=2)
    def _get_sender_domain(self, ppr: OutboundPPR) -> str:
        """Returns the domain portion of `ppr.sender`

        :param chapps.outbound.OutboundPPR ppr: a Postfix payload

        :returns: the domain part of `ppr.sender`

        :rtype: str

        :raise chapps.signals.TooManyAtsException: if there are more than one
          `@` in `ppr.sender`

        :raise chapps.signals.NotAnEmailAddressException: if there is no `@`
          in `ppr.sender`

        :raise chapps.signals.NullSenderException: if `ppr.sender` is
          `None`

        :meta public:

        """
        if ppr.sender:
            return ppr.domain_from(ppr.sender)
        raise NullSenderException

    # We will need to be able to access policy data in the RDBMS
    def _detect_control_data(self, user, domain):
        """Look for SDA control data for a user"""
        key = self._sender_domain_key(user, domain)
        res = None
        try:
            res = self.redis.get(key)
        except redis.exceptions.ResponseError:  # pragma: no cover
            self.redis.delete(key)
        # logger.debug(f"Found {key} = {res!r} in Redis")
        return res if res is None else int(res)

    def _get_control_data(self, ppr):
        """Cascade through control data searches: domain, email"""
        return self._detect_control_data(
            ppr.user, self._get_sender_domain(ppr)
        ) or self._detect_control_data(ppr.user, ppr.sender)

    # We will need to be able to store data in Redis
    def _store_control_data(self, ppr: OutboundPPR, allowed: int):
        """Stuff control data into Redis for domain auth"""
        # logger.debug(
        #     f"store request: {ppr.user} {self._get_sender_domain(ppr)}"
        #     f" {allowed!r}"
        # )
        with self._control_data_storage_context() as dsc:
            dsc(ppr.user, self._get_sender_domain(ppr), allowed)

    def _store_email_control_data(self, ppr, allowed):
        """Stuff control data into Redis for email auth"""
        # logger.debug(f"store request: {ppr.user} {ppr.sender} {allowed!r}")
        with self._control_data_storage_context() as dsc:
            dsc(ppr.user, ppr.sender, allowed)

    # We will need a Redis storage context manager in order to mimic
    # the structure of OQP -- metaprogramming opportunity
    @contextmanager
    def _control_data_storage_context(
        self, expire_time: int = seconds_per_day
    ):
        """Context manager for storing SDA policy cache data in Redis"""
        pipe = self.redis.pipeline()
        fmtkey = self._fmtkey

        def _dsc(user, domain, allowed):
            key = fmtkey(user, domain)
            # logger.debug(f"Storing {key} = {allowed} in Redis")
            pipe.set(key, allowed, ex=seconds_per_day)

        try:
            yield _dsc
        finally:
            pipe.execute()
            pipe.reset()

    # How to obtain control data
    def acquire_policy_for(self, ppr) -> bool:
        """Populate Redis with policy config

        :param chapps.outbound.OutboundPPR ppr: a Postfix payload

        :returns: whether the policy allows `ppr`

        :rtype: bool

        Populates Redis and return the policy result for `ppr`.

        """
        # logger.debug(f"acq pol for {ppr!r}")
        with self._adapter_handle() as adapter:
            allowed = adapter.check_domain_for_user(
                ppr.user, self._get_sender_domain(ppr)
            )
            self._store_control_data(ppr, 1 if allowed else 0)
            # logger.debug(
            #     f"RDBMS: policy {allowed!r} for {ppr.user} from domain"
            #     f" {self._get_sender_domain(ppr)}"
            # )
            if not allowed:  # domain not allowed, check email
                allowed = adapter.check_email_for_user(ppr.user, ppr.sender)
                if allowed is not None:
                    self._store_email_control_data(ppr, 1 if allowed else 0)
                    # logger.debug(
                    #     f"RDBMS: policy {allowed!r} for {ppr.user} as"
                    #     f" {ppr.sender}"
                    # )
        return allowed

    # This is the main purpose of the class, to answer this question
    def _approve_policy_request(self, ppr: OutboundPPR) -> bool:
        """Returns true if `ppr` represents an authorized email

        :param chapps.outbound.OutboundPPR ppr: a Postfix payload

        :returns: whether the email represented by `ppr` should be
          transmitted

        :rtype: bool

        Given a PPR, say whether this user is allowed to send as the
        apparent sender domain or address.  Memoize result in the
        instance cache.

        """
        result = self._get_control_data(ppr)
        if result is None:
            result = self.acquire_policy_for(ppr)
            # logger.debug(f"Obtained {result!r} from RDBMS.")
        else:
            # logger.debug(f"Returning {result!r} from Redis.")
            pass
        return bool(int(result))

    def _decode_policy_cache(self, result) -> SDAStatus:
        """Decode the {None, 0, 1} response from Redis into an Enum

        :params int result: b'0', b'1', or None

        :returns: an SDAStatus corresponding to `result`

        :rtype: chapps.models.SDAStatus

        The :class:`Enum` :class:`~chapps.models.SDAStatus` represents
        these results as nonexistent, prohibited or authorized respectively.

        """
        if result is not None:
            result = int(result)
            if result:
                return SDAStatus.AUTH
            else:
                return SDAStatus.PROH
        else:
            return SDAStatus.NONE

    # For the API -- inspect state
    def check_policy_cache(self, user: str, domain: str) -> SDAStatus:
        """Check a particular policy cache entry for the API

        :param str user: user-identifier

        :param str domain: domain or email to check

        :returns: the cached policy

        :rtype: chapps.models.SDAStatus

        """
        return self._decode_policy_cache(
            self._detect_control_data(user, domain)
        )

    def clear_policy_cache(self, user: str, domain: str) -> SDAStatus:
        """Clear a specific policy cache entry

        :param str user: user-identifier

        :param str domain: domain or email to clear

        :returns: the previous policy

        :rtype: SDAStatus

        """
        prev = self.check_policy_cache(user, domain)
        if prev != SDAStatus.NONE:
            self.redis.delete(self._sender_domain_key(user, domain))
        return prev

    def bulk_clear_policy_cache(
        self,
        users: List[str],
        domains: List[str] = None,
        emails: List[str] = None,
    ):
        r"""Clear SDA policy cache
        for **User**\ s x [**Domain**\ s + **User**\ s]

        :param List[str] users: a list of user-identifiers
        :param Optional[List[str]] domains: a list of domain names
        :param Optional[List[str]] emails: a list of email addresses
        :rtype: None

        """
        # there seems to be no max pipeline size
        # but if things get sketchy, we can chunk this
        domains = domains or []
        emails = emails or []
        with self.redis.pipeline() as pipe:
            for d in domains + emails:
                for u in users:
                    # logger.debug(f"bulk_clear: erasing {u}:{d}")
                    pipe.delete(self._sender_domain_key(u, d))
            pipe.execute()
            pipe.reset()

    def bulk_check_policy_cache(
        self,
        users: List[str],
        domains: List[str] = None,
        emails: List[str] = None,
    ) -> Dict[str, Dict[str, SDAStatus]]:
        """Map auth subject onto user status

        :param List[str] users: a list of user-identifiers
        :param Optional[List[str]] domains: a list of domain names
        :param Optional[List[str]] emails: a list of email addresses

        :returns: an auth subject => user => status map as described below

        :rtype: Dict[str, Dict[str, SDAStatus]]

        Builds a map keyed on auth subject (**Domain** and/or **Email**), full
        of maps from username to status.  It looks a bit like this:

        .. code::python

            bulk_check_result = {
                'example.com': { 'user@example.com': SDAStatus.AUTH,
                                 'terminated@example.com': SDAStatus.PROH,
                },
                'chapps.io': { 'user@example.com': SDAStatus.NONE,
                               'terminated@example.com': SDAStatus.NONE,
                }
            }

        Mainly intended for use by the API.

        """
        emails = emails or []
        domains = domains or []
        with self.redis.pipeline() as pipe:
            for d in domains + emails:
                for u in users:
                    # logger.debug(f"bcpc seeking SDA for {u} from {d}")
                    pipe.get(self._sender_domain_key(u, d))
            results = deque(pipe.execute())
            pipe.reset()
        # logger.debug(f"bcpc results: {results!r}")
        return {
            d: {u: self._decode_policy_cache(results.popleft()) for u in users}
            for d in domains + emails
        }
