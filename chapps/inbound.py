"""
InboundPPR
-----------

And possibly other classes related to outbound traffic, but right now there is
only one, which is an outbound-only subclass of
:py:class:`chapps.util.PostfixPolicyRequest`.

"""
from typing import List
from functools import cached_property
from chapps.util import PostfixPolicyRequest

# from chapps.config import config, CHAPPSConfig
from chapps.signals import NoRecipientsException
import logging

logger = logging.getLogger(__name__)


class InboundPPR(PostfixPolicyRequest):
    """Encapsulates logic to identify the client domain for inbound mail
    """

    def __init__(self, payload: List[str], **kwargs):
        """Create a new inbound policy request"""
        super().__init__(payload)

    @cached_property
    def recipient_domain(self):
        if not len(self.recipients):
            raise NoRecipientsException(
                f"PPR {ppr.instance} contains no recipients"
            )
        domains = set([self.domain_from(e) for e in self.recipients])
        if len(domains) > 1:
            # raise MultipleInboundRecipientsException ?
            logger.debug(
                f"Using first recipient {ppr.recipients[0]} for domain flags."
            )
        return self.domain_from(self.recipients[0])

    def __str__(self):
        """In certain contexts, `str(<o_ppr>)` is used for brevity

        The routine tries to use the `user` which is the point of the class,
        but if it cannot determine a non-nil user name, it falls back to
        printing a bit of extra detail.

        """
        try:
            return (
                f"i={self.instance} "
                f"domain={self.recipient_domain} "
                f"sender={self.sender or 'None'} "
                f"client_address={self.client_address} "
                f"recipient={self.recipient}"
            )
        except Exception:
            return (
                f"i={self.instance} "
                f"sender={self.sender or 'None'} "
                f"client_address={self.client_address} "
                f"recipient={self.recipient}"
            )
