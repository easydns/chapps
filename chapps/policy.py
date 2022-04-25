"""chapps.policy

Policy routines for CHAPPS
"""
import time
from contextlib import contextmanager
from collections import deque
import functools
import redis
import logging
from expiring_dict import ExpiringDict
from chapps.config import config
from chapps.adapter import MariaDBQuotaAdapter, MariaDBSenderDomainAuthAdapter
from chapps.signals import (
    TooManyAtsException,
    NullSenderException,
    NotAnEmailAddressException,
)
from chapps.rest.models import Quota, SDAStatus

logger = logging.getLogger(__name__)
seconds_per_day = 3600 * 24
SENTINEL_TIMEOUT = 0.1
TIME_FORMAT = "%d %b %Y %H:%M:%S %z"

# There are a number of commented debug statements in this module
# This is for convenience, because in production these routines need
# to be as performant as possible, but these messages are often very
# helpful for diagnosing problems during testing and debugging


class EmailPolicy:
    redis_key_prefix = "chapps"

    @staticmethod
    def rediskey(prefix, *args):
        """Format a string to serve as a Redis key for arbitrary data"""
        return f"{ prefix }:{ ':'.join( args ) }"

    @classmethod
    def _fmtkey(cls, *args):
        return cls.rediskey(cls.redis_key_prefix, *args)

    def __init__(self, cfg=None):
        self.config = cfg if cfg else config
        self.params = self.config.get_block(self.__class__.__name__)
        self.sentinel = None
        self.redis = self._redis()  # pass True to get read-only
        self.instance_cache = ExpiringDict(3)  # entries expire after 3 seconds

    def _redis(self, read_only=False):
        """Get a Redis handle, possibly from Sentinel"""
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

    def approve_policy_request(self, ppr):
        raise NotImplementedError(
            "Subclasses of EmailPolicy must implement this function."
        )


class GreylistingPolicy(EmailPolicy):
    """Represents Greylisting policy"""

    redis_key_prefix = "grl"

    def __init__(
        self,
        cfg=None,
        *,
        minimum_deferral=60,
        cache_ttl=seconds_per_day,
        auto_allow_after=10,
    ):
        """all EmailPolicy objects expect an optional positional param for a CHAPPSConfig
           named arguments for GreylistingPolicy objects are:
             - minimum_deferral: the minimum amount of time allowed for greylisting to approve the second attempt
             - cache_ttl: how long to store data about a tracked client (source IP)
                          this is used both for auto-allow and for basic greylist impression retention
             - auto_allow_after: a count of successful greylist re-sends post-deferral, after which
                          approval will be granted automatically
        """
        super().__init__(cfg)
        self.min_defer = minimum_deferral
        self.cache_ttl = cache_ttl
        self.allow_after = auto_allow_after
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

    def tuple_key(self, ppr):
        """The names of the values in the PPR are as follows (in order):
             - client_address
             - sender
             - recipient
        """
        return self._fmtkey(ppr.client_address, ppr.sender, ppr.recipient)

    def client_key(self, ppr):
        return self._fmtkey(ppr.client_address)

    def approve_policy_request(self, ppr):
        """Expects a PostfixPolicyRequest; returns True if the email should be accepted"""
        ### TODO: memoization can be factored into the superclass if pre-evaluation hook and evaluation
        ###       can be generalized
        instance = ppr.instance
        cached_response = self.instance_cache.get(instance, None)
        if cached_response is not None:
            return cached_response
        response = self._evaluate_policy_request(ppr)
        self.instance_cache[instance] = response
        return response

    def _evaluate_policy_request(self, ppr):
        try:
            logger.debug(f"Getting control data for {self.tuple_key( ppr )}")
            tuple_seen, client_tally = self._get_control_data(ppr)
            logger.debug(f"Got values ({tuple_seen}, {client_tally})")
        except Exception:  # pragma: no cover
            logger.exception("UNEXPECTED")
            logger.debug(
                f"Returning denial for {ppr.instance} (unexpected exception)."
            )
        if client_tally is not None and client_tally >= self.allow_after:
            self._update_client_tally(ppr)
            return True
        if tuple_seen:
            # The tuple is recognized; need to check if it was long enough ago
            now = time.time()
            if now - tuple_seen >= self.min_defer:
                # the email will be approved; some housekeeping is necessary
                self._update_client_tally(ppr)
                return True
        # if we get here, the tuple either isn't stored or was stored too recently
        # either way, we update it
        self._update_tuple(ppr)
        return False

    def _get_control_data(self, ppr):
        """Extract data from Redis in order to answer the policy request"""
        now = time.time()
        client_address, sender, recipient = (
            ppr.client_address,
            ppr.sender,
            ppr.recipient,
        )
        tuple_key = self.tuple_key(ppr)
        client_key = self.client_key(ppr)
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(client_key, 0, now - float(self.cache_ttl))
        pipe.get(tuple_key)
        if self.allow_after > 0:
            pipe.zrange(client_key, 0, -1)

        result = pipe.execute()
        tuple_bits = result[1]
        if len(result) == 3:
            client_tally_bits = result[2]

        tuple_seen = (
            float(tuple_bits) if tuple_bits else None
        )  # UNIX epoch time
        client_tally = None
        if self.allow_after > 0 and client_tally_bits:
            client_tally = len(client_tally_bits)
        return (tuple_seen, client_tally)

    def _update_client_tally(self, ppr):
        """Update Redis when an email is allowed, to increase the reliability score of the client"""
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

    def _update_tuple(self, ppr):
        self.redis.setex(self.tuple_key(ppr), self.cache_ttl, time.time())


class OutboundQuotaPolicy(EmailPolicy):
    """Represents an outbound quota policy, based on sending rate"""

    redis_key_prefix = "oqp"

    def __init__(self, cfg=None, *, enforcement_interval=None, min_delta=0):
        """first, optional positional argument: a CHAPPSConfig object to use
           named arguments: enforcement_interval will default to seconds per day if not provided
                            min_delta defaults to 5 seconds, to prevent spamming; set to 0 to disable
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
        """return a closure which takes the tuple (email, quota, margin) and stores it in Redis"""
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

    @contextmanager
    def _adapter_handle(self):
        """A context manager for obtaining a database handle for acquiring policy data"""
        adapter = MariaDBQuotaAdapter(
            db_host=self.config.adapter.db_host,
            db_port=self.config.adapter.db_port,
            db_name=self.config.adapter.db_name,
            db_user=self.config.adapter.db_user,
            db_pass=self.config.adapter.db_pass,
        )
        try:
            yield adapter
        finally:
            adapter.conn.close()

    def _get_control_data(self, ppr):
        """
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
        try:
            m = int(margin_bytes)
        except:
            try:
                m = float(margin_bytes)
            except:
                m = 0
        return m

    def current_quota(self, user: str, quota: Quota):
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

    def reset_quota(self, user: str):
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

    def acquire_policy_for(self, user, quota=None):
        """Go get the policy for a sender from the relational database or
           other policy source via adapter.  If the margin needs to be
           altered on a per-sender basis, this is the place to adjust
           that.
        """
        if not quota:
            with self._adapter_handle() as adapter:
                quota = adapter.quota_for_user(user)
        if quota:
            self._store_control_data(user, quota, self.params.margin)

    def approve_policy_request(self, ppr):
        """Expects a PostfixPolicyRequest object; returns True if mail sending
           should be allowed This routine implements memoization in
           order to overcome the Postfix double-checking weirdness.
           Since it seems like the object only lives for the duration
           of the query, it doesn't get us very far.  The Postfix docs
           say it will hold open and re-use the connection, but it
           does not seem to.
        """
        user = ppr.user
        instance = ppr.instance
        cached_response = self.instance_cache.get(instance, None)
        if cached_response is not None:
            logger.debug(f"apr: returning instance cache {cached_response}")
            return cached_response
        if not self._detect_control_data(
            user
        ):  # attempt to retrieve control data if need be
            self.acquire_policy_for(user)
        response = self._evaluate_policy_request(ppr)
        self.instance_cache[instance] = response
        return response

    def _get_delta(self, ppr, attempts):
        """
        This routine gets the number of seconds between this attempt and the
        previous.  It takes into account whether we are counting each
        recipient, and parses the attempt record accordingly -- when counting
        recipients, the record is a string consisting of the timestamp and the
        recipient serial number separated by a colon, in order to ensure that
        each recipient is listed as an attempt in the log.
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
            logger.debug()
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
        """
        This actually checks to see if it's okay to send the email.
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
    """A class for encapsulation of explicit policy regarding what authenticated users are allowed to send from what domains.  Right now we match on the entire string after the @ """

    # every subclass of EmailPolicy must set a key prefix
    redis_key_prefix = "sda"
    # initialization is when we plug in the config
    def __init__(self, cfg=None):
        """first, optional positional argument: a CHAPPSConfig object to use"""
        super().__init__(cfg)  # sets attrs 'config' and 'redis'

    # every subclass has one of these, with a unique name, and fine
    # but maybe there should also be a generic single entry point
    def sender_domain_key(self, ppr):
        """Create a Redis key for each valid user->domain mapping, for speed"""
        return self._sender_domain_key(ppr.user, self._get_sender_domain(ppr))

    def sender_email_key(self, ppr):
        return self._sender_domain_key(ppr.user, ppr.sender)

    # factored out for use in API
    def _sender_domain_key(self, user, domain):
        return self._fmtkey(user, domain)

    # determine the domain of the sender address, if any
    @functools.lru_cache(maxsize=2)
    def _get_sender_domain(self, ppr):
        if ppr.sender:
            parts = ppr.sender.split("@")
            if len(parts) > 2:
                logger.info(
                    "Found sender email with more than one at-sign: "
                    f"sender={ppr.sender} instance={ppr.instance} "
                    f"parts={parts!r}"
                )
                raise TooManyAtsException(f"{ppr.sender}=>{parts!r}")
            elif len(parts) == 1:
                logger.info(
                    "Found sender string without at-sign: "
                    f"sender={ppr.sender} instance={ppr.instance} "
                    f"parts={parts!r}"
                )
                raise NotAnEmailAddressException
            return parts[-1]
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
        return self._detect_control_data(
            ppr.user, self._get_sender_domain(ppr)
        ) or self._detect_control_data(ppr.user, ppr.sender)

    # We will need to be able to store data in Redis
    def _store_control_data(self, ppr, allowed):
        # logger.debug(
        #     f"store request: {ppr.user} {self._get_sender_domain(ppr)}"
        #     f" {allowed!r}"
        # )
        with self._control_data_storage_context() as dsc:
            dsc(ppr.user, self._get_sender_domain(ppr), allowed)

    def _store_email_control_data(self, ppr, allowed):
        # logger.debug(f"store request: {ppr.user} {ppr.sender} {allowed!r}")
        with self._control_data_storage_context() as dsc:
            dsc(ppr.user, ppr.sender, allowed)

    # We will need a Redis storage context manager in order to mimic
    # the structure of OQP -- metaprogramming opportunity
    @contextmanager
    def _control_data_storage_context(self, expire_time=seconds_per_day):
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

    # We will need a database adapter context manager
    @contextmanager
    def _adapter_handle(
        self
    ):  # TODO: identical to OQP -- should be factored up into a superclass
        adapter = MariaDBSenderDomainAuthAdapter(
            db_host=self.config.adapter.db_host,
            db_port=self.config.adapter.db_port,
            db_name=self.config.adapter.db_name,
            db_user=self.config.adapter.db_user,
            db_pass=self.config.adapter.db_pass,
        )
        try:
            yield adapter
        finally:
            adapter.conn.close()

    # How to obtain control data
    def acquire_policy_for(self, ppr):
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
                    #     f" {self._get_sender_domain(ppr)}"
                    # )

        return allowed

    # This is the main purpose of the class, to answer this question
    def approve_policy_request(self, ppr):
        """
        Given a PPR, say whether this user is allowed to send as the
        apparent sender domain
        """
        result = self.instance_cache.get(
            ppr.instance, None
        )  # instances sometimes repeat
        if not result:
            result = self._get_control_data(ppr)
            if result is None:
                result = self.acquire_policy_for(ppr)
                # logger.debug(f"Obtained {result!r} from RDBMS.")
            else:
                # logger.debug(f"Returning {result!r} from Redis.")
                pass
            self.instance_cache[ppr.instance] = result
        else:
            # logger.debug(f"Returning {result!r} from instance cache.")
            pass
        return bool(int(result))

    def _decode_policy_cache(self, result):
        if result is not None:
            result = int(result)
            if result:
                return SDAStatus.AUTH
            else:
                return SDAStatus.PROH
        else:
            return SDAStatus.NONE

    # For the API -- inspect state
    def check_policy_cache(self, user, domain):
        return self._decode_policy_cache(
            self._detect_control_data(user, domain)
        )

    def clear_policy_cache(self, user, domain):
        prev = self.check_policy_cache(user, domain)
        if prev != SDAStatus.NONE:
            self.redis.delete(self._sender_domain_key(user, domain))
        return prev

    def bulk_clear_policy_cache(self, users, domains=None, emails=None):
        # there seems to be no max pipeline size
        # but if things get sketchy, we can chunk this
        domains = domains or []
        emails = emails or []
        with self.redis.pipeline() as pipe:
            for d in domains + emails:
                for u in users:
                    logger.debug(f"bulk_clear: erasing {u}:{d}")
                    pipe.delete(self._sender_domain_key(u, d))
            pipe.execute()
            pipe.reset()

    def bulk_check_policy_cache(self, users, domains=None, emails=None):
        """Build a map based on domain, full of maps from username to status"""
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
            for d in domains
        }
