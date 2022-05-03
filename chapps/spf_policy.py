"""SPF Enforcement Policy"""
import spf
from chapps.policy import EmailPolicy
from chapps.actions import PostfixSPFActions


class SPFEnforcementPolicy(EmailPolicy):
    """Enforces SPF policy"""

    ### we may never use Redis for SPF directly
    redis_key_prefix = "spf"

    def __init__(self, cfg=None):
        """
        Accepts a CHAPPSConfig instance as an optional argument.
        """
        super().__init__(cfg)
        self.actions = PostfixSPFActions()

    def approve_policy_request(self, ppr):
        """Perform SPF enforcement decision-making on the PPR"""
        ### First, check the HELO name
        helo_sender = "postmaster@" + ppr.helo_name
        query = spf.query(ppr.client_address, helo_sender, ppr.helo_name)
        result, _, message = query.check()
        if result in [
            "fail"
        ]:  ### TODO: allow configuration of HELO results to honor
            action = self.actions.action_for(result)
        else:
            ### the HELO name did not produce a definitive result, so check MAILFROM
            query = spf.query(ppr.client_address, ppr.sender, ppr.helo_name)
            result, _, message = query.check()
            action = self.actions.action_for(result)
        return action(message, ppr=ppr, prepend=query.get_header(result))
