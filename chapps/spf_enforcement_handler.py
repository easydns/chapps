"""SPF Enforcement Handler

This module contains the SPF handler, in order to reduce indentation and
perhaps also to separate some dependencies.

"""
from chapps.config import config
from chapps.spf_policy import SPFEnforcementPolicy
from chapps.util import PostfixPolicyRequest
from chapps.signals import CallableExhausted
import logging
import asyncio


class SPFEnforcementHandler(RequestHandler):
    """Special handler class for :class:`~chapps.spf_policy.SPFEnforcementPolicy`

    This one came along last and forced a reconsideration of how all this
    worked, because it produces more than two possible states as output.
    The plan is to retrofit all the older policies so that they also can
    use an action-translation layer, but that will also require some
    adjustment of the cascading handler.

    .. note::

      This class will not be defined if the relevant SPF libraries could
      not be loaded.  They may be installed via `pip` using the extras
      mechanism: ``pip install chapps[SPF]``

    """

    def __init__(self, policy: SPFEnforcementPolicy = None):
        """Set up an SPFEnforcementHandler

        :param chapps.spf_policy.SPFEnforcementPolicy policy: an instance
          of :class:`~chapps.spf_policy.SPFEnforcementPolicy`

        """
        p = policy or SPFEnforcementPolicy()
        super().__init__(p)

    def async_policy_handler(self):
        """Returns a coroutine which handles results according to the configuration

        The policy being enforced is stored in the SPF-related TXT record
        on the sender's domain.  The local configuration of this policy
        amounts to instructions about responses to different outcomes of
        the SPF check, along with what IP address and port to listen on.

        This policy handler is different from others in that, because it
        does not expect a PASS/FAIL response, it simply wraps the return
        value of
        :func:`~chapps.spf_policy.SPFEnforcementPolicy.approve_policy_request()`
        in a Postfix response packet, and sends it.  Rather than refer to
        pre-configured acceptance and rejection messages, it expects the
        approval routine to send a string which can be interpreted by
        Postfix as a command.

        TODO: In order to be able to cascade *through* this kind of policy,
        it is going to have to return a first-class object which can be
        annotated as being a pass or a fail, so that a cascading handler
        can decide whether to continue.  That object's `__str__()`
        method will need to return the Postfix command.

        .. todo::

          In order to support more than one MTA (tho no such support is
          planned), the action-translation layer might be refactored out of
          the policy itself, to be applied here, in order to switch between
          different types.

        """
        ### This override version for SPF enforcement does not assume a yes-or-no response pattern
        logger.debug(
            f"Policy handler requested for {type(self.policy).__name__}."
        )
        policy = self.policy
        encoding = config.chapps.payload_encoding

        async def handle_policy_request(reader, writer):
            """Handles reading and writing the streams around policy approval messages"""
            while True:
                try:
                    policy_payload = await reader.readuntil(b"\n\n")
                except ConnectionResetError:
                    logger.debug(
                        "Postfix said goodbye. Terminating this thread."
                    )
                    return
                except CallableExhausted as e:
                    raise e
                except Exception:
                    logger.exception("UNEXPECTED ")
                    if reader.at_eof():
                        logger.debug(
                            "Postfix said goodbye oddly. Terminating this thread."
                        )
                        return
                    continue
                logger.debug(
                    f"Payload received: {policy_payload.decode(encoding)}"
                )
                policy_data = PostfixPolicyRequest(
                    policy_payload.decode(encoding).split("\n")
                )
                action = policy.approve_policy_request(policy_data)
                resp = ("action=" + action + "\n\n").encode()
                logger.debug(f"  .. SPF Enforcement sending {resp}")
                try:
                    writer.write(resp)
                except asyncio.CancelledError:  # pragma: no cover
                    pass
                except Exception:
                    logger.exception(f"Exception raised trying to send {resp}")
                    return

        return handle_policy_request
