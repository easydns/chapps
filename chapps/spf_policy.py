"""
SPF Enforcement policy manager
------------------------------

Isolated here to prevent the core codebase from depending upon the SPF
libraries.

"""
import spf
from chapps.signals import NoRecipientsException
from chapps.policy import InboundPolicy
from chapps.actions import PostfixSPFActions
from chapps.util import PostfixPolicyRequest
from chapps.inbound import InboundPPR
import logging

logger = logging.getLogger(__name__)


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
        self.actions = PostfixSPFActions()

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
        return action(message, ppr=ppr, prepend=query.get_header(result))
