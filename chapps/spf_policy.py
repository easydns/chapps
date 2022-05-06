"""SPF Enforcement policy manager"""
import spf
from chapps.policy import EmailPolicy
from chapps.actions import PostfixSPFActions
from chapps.util import PostfixPolicyRequest


class SPFEnforcementPolicy(EmailPolicy):
    """Policy manager which enforces SPF policy

    Instance attributes (in addition to those
    of :class:`~chapps.policy.EmailPolicy`):

      :actions: a :class:`~chapps.actions.PostfixSPFActions` instance

    Behavior of the SPF enforcer is configured under the
    ``[PostfixSPFActions]`` heading in the config file.

    """

    # we may never use Redis for SPF directly
    redis_key_prefix = "spf"
    """For completeness.  SPF is not expected to use Redis."""

    def __init__(self, cfg=None):
        """Setup an SPF enforcement policy manager

        :param chapps.config.CHAPPSConfig cfg: optional config override

        """
        super().__init__(cfg)
        self.actions = PostfixSPFActions()

    def approve_policy_request(self, ppr: PostfixPolicyRequest) -> str:
        """Perform SPF enforcement decision-making

        :param chapps.util.PostfixPolicyRequest ppr: a Postfix payload

        :returns: a string which contains a Postfix instruction

        :rtype: str

        The :class:`~chapps.actions.PostfixSPFActions` class translates
        between the outcome of the SPF check and the configured response
        thus indicated, which gets sent back to Postfix.

        """
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
