"""
Communication handlers
----------------------

This module encapsulates the particular logic of:

  1. receiving data payloads from Postfix, and then

  2. sending back an appropriately-formatted response once the policy manager
     has had a chance to weigh in on the payload contents

Classes defined here exist mainly to be factories which return the main-loop
closure for :mod:`asyncio`.

TODO: :class:`.RequestHandler` should be a subclass of
`.CascadingPolicyHandler` which simply only ever has one policy within it.
This is to avoid maintaining two nearly-identical code-paths.  Running only one
policy is obviously a special case of running many.

"""
# from chapps.config import config  # the global instance of the config object
from chapps.policy import (
    EmailPolicy,
    OutboundQuotaPolicy,
    GreylistingPolicy,
    SenderDomainAuthPolicy,
)
from chapps.util import PostfixPolicyRequest
from chapps.inbound import InboundPPR
from chapps.outbound import OutboundPPR
from chapps.signals import (
    CHAPPSException,
    CallableExhausted,
    NullSenderException,
    AuthenticationFailureException,
)
from functools import cached_property
from typing import Type, Optional, List
import logging
import asyncio

try:
    from chapps.spf_policy import SPFEnforcementPolicy
except Exception:
    HAVE_SPF = False
    pass
else:
    HAVE_SPF = True

logger = logging.getLogger(__name__)  # pragma: no cover


class CascadingPolicyHandler:
    """Second-generation handler class which cascades multiple yes/no policies

    This class started out nearly identical to :class:`.RequestHandler`, but as
    the software has moved on, so has this handler, which is the main one in
    general use.

    This handler accepts a list of policy manager instances, all of which
    should produce True/False results.  The handler applies each policy to each
    request, and passes those which pass both, or returns the message from the
    policy which failed.  Once a policy has failed, no further policies are
    consulted.

    Instance attributes:

      :policies: a list of :class:`~chapps.policy.EmailPolicy` objects

      :pprclass: the class of :class:`~PostfixPolicyRequest` to instantiate
        from the Postfix request payload

      :config: a reference to the :class:`~chapps.config.CHAPPSConfig` stored
        on the first policy in the list

      :listen_address: the IP address to bind to; see :meth:`.listen_address`

      :listen_port: the port to listen on; see :meth:`.listen_port`

    """

    def __init__(
        self,
        policies: Optional[List[EmailPolicy]] = [],
        *,
        pprclass: PostfixPolicyRequest = PostfixPolicyRequest,
    ):
        self.policies = policies
        self.pprclass = pprclass
        if not self.policies:
            raise ValueError("A list of policy objects must be provided.")
        self.config = self.policies[
            0
        ].config  # all copies of the config are the same
        logger.debug(
            "Grabbing config from file "
            + self.config.chapps.config_file
            + " via "
            + self.policies[0].__class__.__name__
        )

    @cached_property
    def listen_address(self):
        return next(
            (getattr(p.params, "listen_address", None) for p in self.policies),
            None,
        )

    @cached_property
    def listen_port(self):
        return next(
            (getattr(p.params, "listen_port", None) for p in self.policies),
            None,
        )

    # an asynchronous policy handler which cascades through all the policies;
    # fails stop execution
    def async_policy_handler(self):
        """Coroutine factory

        :returns: a coroutine which handles requests according to the policies,
          in order

        """
        pprclass = self.pprclass
        policies = self.policies
        encoding = self.config.chapps.payload_encoding
        no_user_key_response = self.config.chapps.no_user_key_response
        logger.debug(
            f"Cascading policy handler requested for "
            f"{[ type(p) for p in policies ]} using PPR "
            f"class {pprclass.__name__}."
        )

        async def handle_policy_request(reader, writer):
            """Handles reading and writing the streams around policy approval messages, and manages the cascade"""
            while True:
                try:
                    policy_payload = await reader.readuntil(b"\n\n")
                except ConnectionResetError:
                    logger.debug(
                        "Postfix said goodbye. Terminating this thread."
                    )
                    return
                except asyncio.IncompleteReadError as e:
                    logger.debug(
                        "Postfix hung up before a read could be completed. Terminating this thread."
                    )
                    return
                except CallableExhausted as e:
                    raise e
                except Exception:
                    if reader.at_eof():
                        logger.debug(
                            "Postfix said goodbye oddly. Terminating this thread."
                        )
                        return
                    else:
                        logger.exception("UNEXPECTED ")
                    continue
                logger.debug(
                    f"Payload received: {policy_payload.decode( 'utf-8' )}"
                )
                policy_data = pprclass(
                    policy_payload.decode(encoding).split("\n")
                )
                approval = True
                for policy in policies:
                    try:
                        if policy.approve_policy_request(policy_data):
                            resp = (
                                "action="
                                + policy.params.acceptance_message
                                + "\n\n"
                            )
                            logger.info(
                                f"{type(policy).__name__} PASS {policy_data}"
                            )
                        else:
                            resp = (
                                "action="
                                + policy.params.rejection_message
                                + "\n\n"
                            )
                            approval = False
                            logger.info(
                                f"{type(policy).__name__} FAIL {policy_data}"
                            )
                    except NullSenderException:
                        if policy.params.null_sender_ok:
                            resp = (
                                "action="
                                + policy.params.acceptance_message
                                + "\n\n"
                            )
                            logger.info(
                                f"{type(policy).__name__} PASS NS {policy_data}"
                            )
                        else:
                            resp = (
                                "action="
                                + policy.params.rejection_message
                                + "\n\n"
                            )
                            approval = False
                            logger.info(
                                f"{type(policy).__name__} FAIL NS {policy_data}"
                            )
                    except AuthenticationFailureException:
                        resp = "action=" + no_user_key_response + "\n\n"
                        approval = False
                        logger.info(
                            f"{type(policy).__name__} FAIL NA {policy_data}"
                        )
                    except CHAPPSException:
                        logger.exception("During policy evaluation:")
                    if not approval:
                        break
                try:
                    writer.write(resp.encode())
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception(
                        f"Exception raised trying to send {resp.strip()}"
                    )
                    return

        return handle_policy_request


class RequestHandler(CascadingPolicyHandler):
    """Refactored intermediate base class for wrapping policy managers in an event loop

    This class has been reimplemented as a subclass of
    :class:`.CascadingPolicyHandler`, as a special case which has only one
    policy to handle.

    Instance attributes:

      :policy: the :class:`~chapps.policy.EmailPolicy` manager instance

      :config: a reference to the :class:`~chapps.config.CHAPPSConfig` stored
        on the policy instance.

      :pprclass: a reference to the particular kind of
        :class:`~chapps.util.PostfixPolicyRequest` to instantiate

    """

    def __init__(
        self,
        policy: EmailPolicy,
        *,
        pprclass: Type[PostfixPolicyRequest] = PostfixPolicyRequest,
    ):
        """Setup a Postfix policy request handler

        :param chapps.policy.EmailPolicy policy: an instance of a policy
          manager (a subclass of :class:`~chapps.policy.EmailPolicy`)

        :param Type[PostfixPolicyRequest] pprclass: the subclass of :class:`~chapps.util.PostfixPolicyRequest` to instantiate from the Postfix payloads; defaults to :class:`~chapps.util.PostfixPolicyRequest`

        .. note::

          Unlike other class families within CHAPPS, the handlers in this
          module do not accept config-override arguments.  They obtain their
          references to the config from their attached policy managers.

        """
        super().__init__([policy], pprclass=pprclass)

    @cached_property
    def listen_address(self):
        return self.policy.params.listen_address

    @cached_property
    def listen_port(self):
        return self.policy.params.listen_port

    @cached_property
    def policy(self):
        return self.policies[0]


class OutboundMultipolicyHandler(CascadingPolicyHandler):
    """Convenience subclass for combining outbound P/F policies

    Could be thought of as a concrete subclass of
    :class:`~.CascadingPolicyHandler`, but meant more as a convenience.

    """

    def __init__(self, policies=[], *, pprclass=OutboundPPR):
        """Setup an OutboundMultipolicyHandler

        :param List[EmailPolicy] policies: a list of policy manager instances

        :param Type[PostfixPolicyRequest] pprclass: kind of
          :class:`~chapps.util.PostfixPolicyRequest` to instantiate from
          Postfix request payloads; defaults to
          :class:`~chapps.outbound.OutboundPPR`

        If none are provided, default-configured instances of
        :class:`~chapps.policy.SenderDomainAuthPolicy` and
        :class:`~chapps.policy.OutboundQuotaPolicy` are used, in that order.

        """
        # note that we default to OutboundPPR here
        policies = policies or [
            SenderDomainAuthPolicy(),
            OutboundQuotaPolicy(),
        ]  # create a list of relevant outbound y/n policies
        super().__init__(policies, pprclass=pprclass)


class OutboundQuotaHandler(RequestHandler):
    """Convenience class for wrapping :class:`~chapps.policy.OutboundQuotaPolicy`"""

    def __init__(self, policy: OutboundQuotaPolicy = None):
        """Setup an OutboundQuotaHandler

        :param chapps.policy.OutboundQuotaPolicy policy: an instance of
          :class:`~chapps.policy.OutboundQuotaPolicy`

        """
        p = policy or OutboundQuotaPolicy()
        super().__init__(p, pprclass=OutboundPPR)


class GreylistingHandler(RequestHandler):
    """Convenience class for wrapping :class:`~chapps.policy.GreylistingPolicy`"""

    def __init__(self, policy: GreylistingPolicy = None):
        """Setup a GreylistingHandler

        :param chapps.policy.GreylistingPolicy policy: an instance of
          :class:`~chapps.policy.GreylistingPolicy`

        """
        p = policy or GreylistingPolicy()
        super().__init__(p, pprclass=InboundPPR)


class SenderDomainAuthHandler(RequestHandler):
    """Convenience class for wrapping :class:`~chapps.policy.SenderDomainAuthPolicy`"""

    def __init__(self, policy: SenderDomainAuthPolicy = None):
        """Setup a SenderDomainAuthHandler

        :param chapps.policy.SenderDomainAuthPolicy policy: an instance of
          :class:`~chapps.policy.SenderDomainAuthPolicy`

        """
        p = policy or SenderDomainAuthPolicy()
        super().__init__(p, pprclass=OutboundPPR)


class CascadingMultiresultPolicyHandler(CascadingPolicyHandler):
    """Cascading handler for policies which produce more than two results

    Some policies, such as the SPF enforcement policy, need to be able to
    generate responses with more nuance than simply pass/fail, and so there is
    a need for a handler which can deal with policies which return strings
    (Postfix directives), or possibly a custom class to encapsulate also some
    idea of pass/fail, in order to know whether to abort the policy-evaluation
    loop early.

    """

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
            "Policy handler requested for"
            f" {[type(p).__name__ for p in self.policies]!r}."
        )
        pprclass = self.pprclass
        policies = self.policies
        encoding = self.config.chapps.payload_encoding

        logger.debug(
            "Cascading Multipolicy handler requested for "
            f"{[type(p) for p in policies]} using PPR "
            f"class {pprclass.__name__}."
        )

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
                except asyncio.IncompleteReadError as e:
                    logger.debug(
                        "Postfix hung up before a read could be completed."
                        " Terminating this thread."
                    )
                    return
                except CallableExhausted as e:
                    raise e
                except Exception:
                    if reader.at_eof():
                        logger.debug(
                            "Postfix said goodbye oddly."
                            " Terminating this thread."
                        )
                        return
                    else:
                        logger.exception("UNEXPECTED ")
                    continue
                logger.debug(
                    f"Payload received: {policy_payload.decode(encoding)}"
                )
                policy_data = pprclass(
                    policy_payload.decode(encoding).split("\n")
                )

                actions = ["DUNNO"]
                # TODO:
                # track all responses, and then extract non-DUNNO ones if any
                for policy in policies:
                    try:
                        action = policy.approve_policy_request(policy_data)
                        actions.append(action)
                        logger.info(
                            f"{type(policy).__name__} "
                            # + ("PASS" if action else "FAIL")
                            + f" {action!r} {policy_data}"
                        )
                    except CHAPPSException:
                        logger.exception("During policy evaluation:")
                    if not action:
                        break

                if action:  # i.e. the mail will be forwarded
                    non_dunno = [a for a in actions if a != "DUNNO"]
                    action = non_dunno[-1] if non_dunno else "DUNNO"
                try:
                    writer.write((f"action={action}\n\n").encode(encoding))
                except asyncio.CancelledError:  # pragma: no cover
                    pass
                except Exception:
                    logger.exception(
                        f"Exception raised trying to send {action}"
                    )
                    return

        return handle_policy_request


class MultiresultPolicyHandler(CascadingMultiresultPolicyHandler):
    """A subclass for handling just one policy"""

    def __init__(
        self,
        policy: EmailPolicy,
        *,
        pprclass: Optional[PostfixPolicyRequest] = PostfixPolicyRequest,
    ):
        super().__init__([policy], pprclass=pprclass)


if HAVE_SPF:

    class SPFEnforcementHandler(MultiresultPolicyHandler):
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

        def __init__(
            self,
            policy: Optional[SPFEnforcementPolicy] = None,
            pprclass: Optional[PostfixPolicyRequest] = InboundPPR,
        ):
            """Set up an SPFEnforcementHandler

            :param chapps.spf_policy.SPFEnforcementPolicy policy: an instance
              of :class:`~chapps.spf_policy.SPFEnforcementPolicy`

            """
            p = policy or SPFEnforcementPolicy()
            super().__init__(p, pprclass=pprclass)

        @cached_property
        def policy(self):
            return self.policies[0]

    class InboundMultipolicyHandler(CascadingMultiresultPolicyHandler):
        """Implements SPF and Greylisting simultaneously

        This is a template for an inbound multipolicy handler, which by default
        checks SPF and also performs Greylisting, each of which depends upon
        options which the email account administrator may set about whether
        either of SPF or Greylisting or both should be applied to inbound mail
        for the particular domain.

        """

        def __init__(
            self,
            policies: Optional[List[EmailPolicy]] = None,
            *,
            pprclass: Optional[PostfixPolicyRequest] = InboundPPR,
        ):
            """Create an inbound policy handler for SPF + Greylisting"""
            policies = policies or [
                SPFEnforcementPolicy(),
                GreylistingPolicy(),
            ]
            super().__init__(policies, pprclass=pprclass)
