"""
SPF Enforcement policy manager
------------------------------

Isolated here to prevent the core codebase from depending upon the SPF
libraries.

"""
import spf
from chapps.signals import NoRecipientsException
from chapps.policy import InboundPolicy, PostfixActions, GreylistingPolicy
from chapps.util import PostfixPolicyRequest
from chapps.inbound import InboundPPR
from chapps.config import CHAPPSConfig
import logging

logger = logging.getLogger(__name__)


class PostfixSPFActions(PostfixActions):
    """
    Postfix Action translator for :py:class:`chapps.policy.SPFEnforcementPolicy`

    .. caution::

        The SPF functionality of CHAPPS is not considered complete.  YMMV

    """

    def greylist_factory(self):
        greylisting_policy = GreylistingPolicy(self.config)
        greylisting_actions = greylisting_policy.actions
        spf_policy = self.spf_policy

        def greylist(msg, *args, **kwargs):
            """Greylisting closure

            This method is meant to share the same signature as the other
            action methods, mainly defined on
            :py:class:`chapps.actions.PostfixActions`

            The `greylist` action causes the email in question to be
            greylisted, according to the policy.  The `msg` is used as the
            message for the Postfix directive, or if the message has no
            contents and the email is being deferred, the string "due to SPF
            enforcement policy" is used.  Because the greylisting policy's
            message is prepended later, the actual message delivered by Postfix
            will look something like "greylisted due to SPF enforcement
            policy".

            """
            ppr = kwargs.get("ppr", None)
            if ppr is None:
                raise ValueError(
                    "PostfixSPFActions.greylist() expects a ppr= kwarg "
                    "providing the PPR for greylisting."
                )
            if greylisting_policy.approve_policy_request(ppr, force=True):
                passing = spf_policy.action_for("pass")
                return passing(msg, ppr, *args, **kwargs)
            if len(msg) == 0:
                msg = "due to SPF enforcement policy"
            return greylisting_actions.fail(msg, ppr, *args, **kwargs)

        return greylist

    _cached_actions = {}
    _action_factories = dict(greylist=greylist_factory)

    def __getattr__(self, attr):
        if attr not in self._cached_actions:
            if attr in self._action_factories:
                self._cached_actions[attr] = self._action_factories[attr](self)
            else:
                return super().__getattr__(attr)
        return self._cached_actions[attr]

    def __init__(self, spf_policy, cfg: CHAPPSConfig = None):
        """Create a new PostfixSPFActions instance

        :param ~.SPFEnforcementPolicy spf_policy: The SPF policy object which
          instantiated this actions object

        :param cfg: Optional config override

        The config is normally taken from the `~.SPFEnforcementPolicy` passed
        in as the first argument, but that config may be overridden by
        providing the config argument.

        """
        super().__init__(cfg or spf_policy.config)
        self.spf_policy = spf_policy
        self.params = self.config.actions_spf

    def _mangle_action(self, action):
        """
        Perform additional mangling to turn either of 'none' or 'neutral' into
        the same symbol, 'none_neutral'

        """
        if action == "none" or action == "neutral":
            action = "none_neutral"
        else:
            action = super()._mangle_action(action)
        return action

    def action_for(self, spf_result):
        """

        Override
        :py:meth:`chapps.actions.PostfixActions.action_for()` to provide
        action closures for the different SPF results.  The closures are
        memoized, so that they only need be constructed once per runtime.

        """
        spf_result = self._mangle_action(spf_result)
        action = getattr(self, spf_result, None)
        if action:
            return action
        return self._get_closure_for(spf_result)  #  this memoizes its result


class SPFEnforcementPolicy(InboundPolicy):
    """Policy manager which enforces SPF policy

    Instance attributes (in addition to those
    of :class:`~chapps.policy.EmailPolicy`):

      :actions: a :class:`~chapps.actions.PostfixSPFActions` instance

    Behavior of the SPF enforcer is configured under the
    `[PostfixSPFActions]` heading in the config file.

    """

    redis_key_prefix = "spf"
    """For option flag in Redis"""

    def __init__(self, cfg=None):
        """Setup an SPF enforcement policy manager

        :param chapps.config.CHAPPSConfig cfg: optional config override

        """
        super().__init__(cfg)
        self.actions = PostfixSPFActions(self)

    def acquire_policy_for(self, ppr: InboundPPR) -> bool:
        with self._adapter_handle() as adapter:
            result = adapter.check_spf_on(ppr.recipient_domain)
        self._store_control_data(ppr.recipient_domain, result)
        return result

    def _get_control_data(self, ppr: InboundPPR) -> int:
        option_key = self.domain_option_key(ppr)
        option_bits = self.redis.get(option_key)
        if option_bits is None:
            return None
        else:
            return int(option_bits)

    def enabled(self, ppr: InboundPPR) -> bool:
        option_set = None
        try:
            option_set = self._get_control_data(ppr)
        except NoRecipientsException:
            logger.exception(f"No recipient in PPR {ppr.instance}")
            return False
        except Exception:
            logger.exception("UNEXPECTED")
            return False
        if option_set is None:
            option_set = self.acquire_policy_for(ppr)
        option_set = int(option_set)
        return option_set == 1

    def _approve_policy_request(self, ppr: PostfixPolicyRequest) -> str:
        """Perform SPF enforcement decision-making

        :param ppr: a Postfix payload

        :returns: a string which contains a Postfix instruction

        The :class:`~chapps.actions.PostfixSPFActions` class translates
        between the outcome of the SPF check and the configured response
        thus indicated, which gets sent back to Postfix.

        .. todo::

          Allow configuration of the list of results of the HELO check which
          should be honored, rather than resulting in proceeding to the MAIL
          FROM check.  Currently, only `fail` is honored, meaning that any
          other result will mean that a MAIL FROM check is to be conducted, and
          its result used as the result.

        """
        if not self.enabled(ppr):
            return self.actions.dunno()

        # First, check the HELO name
        helo_sender = "postmaster@" + ppr.helo_name
        query = spf.query(ppr.client_address, helo_sender, ppr.helo_name)
        result, _, message = query.check()
        if result in [
            "fail"
        ]:  # TODO: allow configuration of HELO results to honor
            action = self.actions.action_for(result)
        else:
            # the HELO name did not produce a definitive result, so check MAILFROM
            query = spf.query(ppr.client_address, ppr.sender, ppr.helo_name)
            result, _, message = query.check()
            action = self.actions.action_for(result)
        return action(
            message,
            ppr=ppr,
            prepend="Received-SPF: " + query.get_header(result, "spfquery"),
        )
