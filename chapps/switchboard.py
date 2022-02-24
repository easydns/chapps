"""chapps.switchboard

Message multiplexing objects and/or routines for CHAPPS
"""
from .config import config
from .policy import OutboundQuotaPolicy, GreylistingPolicy, SenderDomainAuthPolicy
from .spf_policy import SPFEnforcementPolicy
from .util import AttrDict, PostfixPolicyRequest
from .outbound import OutboundPPR
from .tests.conftest import CallableExhausted
import logging, chapps.logging
import asyncio

logger = logging.getLogger(__name__) # pragma: no cover
logger.setLevel( logging.DEBUG )     # pragma: no cover
logger.debug( "Request library initialized." )

class RequestHandler():
    """Wrap handling in an object-oriented factory so we can supply a policy"""
    def __init__(self, policy, *, pprclass=PostfixPolicyRequest):
        self.policy = policy
        self.config = self.policy.config # in case a custom config is in use
        self.pprclass = pprclass

    def async_policy_handler(self):
        """Returns a coroutine which handles requests according to the policy"""
        pprclass = self.pprclass
        policy = self.policy
        accept = self.config.policy.acceptance_message
        reject = self.config.policy.rejection_message
        encoding = config.chapps.payload_encoding
        logger.debug(f"Policy handler requested for {type(policy).__name__} using PPR class {pprclass.__name__}.")
        async def handle_policy_request(reader, writer) -> None:
            """Handles reading and writing the streams around policy approval messages"""
            while True:
                try:
                    policy_payload = await reader.readuntil(b'\n\n')
                except ConnectionResetError:
                    logger.debug("Postfix said goodbye. Terminating this thread.")
                    return
                except CallableExhausted as e:
                    raise e
                except Exception:
                    logger.exception("UNEXPECTED ")
                    if reader.at_eof():
                        logger.debug("Postfix said goodbye oddly. Terminating this thread.")
                        return
                    continue
                logger.debug(f"Payload received: {policy_payload.decode('utf-8')}")
                policy_data = pprclass( policy_payload.decode(encoding).split('\n') )
                if policy.approve_policy_request(policy_data):
                    resp = ("action=" + accept + "\n\n").encode()
                    logger.debug(f"  .. Accepted.  Sending {resp}")
                else:
                    resp = ("action=" + reject + "\n\n").encode()
                    logger.debug(f"  .. Rejected with {resp}")
                try:
                    writer.write( resp )
                except asyncio.CancelledError: # pragma: no cover
                    pass
                except Exception:
                    logger.exception(f"Exception raised trying to send {resp}")
                    return
        return handle_policy_request

class CascadingPolicyHandler():
    """A handler class which cascades multiple yes/no policies"""
    def __init__( self, policies=[], *, pprclass=PostfixPolicyRequest ):
        self.policies = policies
        self.pprclass = pprclass
        if not self.policies:
            raise ValueError( "A list of policy objects must be provided." )
        self.config = self.policies[0].config # all policies have all of the config
    ### an asynchronous policy handler which cascades through all the policies; fails stop execution
    def async_policy_handler( self ):
        """Returns a coroutine which handles requests according to the policies, in order"""
        pprclass = self.pprclass
        policies = self.policies
        encoding = self.config.chapps.payload_encoding
        logger.debug( f"Cascading policy handler requested for {[ type(p) for p in policies ]} using PPR class {pprclass.__name__}." )
        async def handle_policy_request( reader, writer ):
            """Handles reading and writing the streams around policy approval messages, and manages the cascade"""
            while True:
                try:
                    policy_payload = await reader.readuntil( b'\n\n' )
                except ConnectionResetError:
                    logger.debug( "Postfix said goodbye. Terminating this thread." )
                    return
                except CallableExhausted as e:
                    raise e
                except Exception:
                    logger.exception("UNEXPECTED ")
                    if reader.at_eof():
                        logger.debug( "Postfix said goodbye oddly. Terminating this thread." )
                        return
                    continue
                logger.debug( f"Payload received: {policy_payload.decode( 'utf-8' )}" )
                policy_data = pprclass( policy_payload.decode( encoding ).split( '\n' ) )
                approval = True
                for policy in policies:
                    if policy.approve_policy_request( policy_data ):
                        resp = ( "action=" + policy.config.policy.acceptance_message + "\n\n" )
                        logger.debug( f" .. Policy {type(policy)} accepted with '{resp.strip()}'" )
                    else:
                        resp = ( "action=" + policy.config.policy.rejection_message + "\n\n" )
                        approval = False
                        logger.debug( f" .. Policy {type(policy)} denied with '{resp.strip()}'" )
                    if not approval:
                        break
                try:
                    writer.write( resp.encode() )
                except asyncio.CancelledError:
                    pass
                except Exception:
                    logger.exception( f"Exception raised trying to send {resp.strip()}" )
                    return
        return handle_policy_request

class OutboundMultipolicyHandler( CascadingPolicyHandler ):
    """Could be thought of as a concrete subclass of CPH, but meant more as a convenience"""
    def __init__( self, policies=[], *, pprclass=OutboundPPR ):                       # note that we default to OutboundPPR here
        policies = policies or [ SenderDomainAuthPolicy(), OutboundQuotaPolicy() ]    # create a list of relevant outbound y/n policies
        super().__init__( policies, pprclass=pprclass )

class OutboundQuotaHandler(RequestHandler):
    def __init__( self, policy=None ):
        p = policy or OutboundQuotaPolicy()
        super().__init__( p, pprclass=OutboundPPR )
        self.config.policy = self.config.policy_oqp # setup for outbound quota

class GreylistingHandler(RequestHandler):
    def __init__( self, policy=None ):
        p = policy or GreylistingPolicy()
        super().__init__( p )
        self.config.policy = self.config.policy_grl # setup for greylisting

class SenderDomainAuthHandler(RequestHandler):
    def __init__( self, policy=None ):
        p = policy or SenderDomainAuthPolicy()
        super().__init__( p, pprclass=OutboundPPR )
        self.config.policy = self.config.policy_sda # setup for sender domain authorization

class SPFEnforcementHandler(RequestHandler):
    def __init__(self, policy=None):
        p = policy or SPFEnforcementPolicy()
        super().__init__( p )
        self.config.policy = self.config.policy_spf # setup for SPF enforcement

    def async_policy_handler(self):
        """Returns a coroutine which handles requests according to the policy"""
        ### This override version for SPF enforcement does not assume a yes-or-no response pattern
        logger.debug(f"Policy handler requested for {type(self.policy).__name__}.")
        policy = self.policy
        encoding = config.chapps.payload_encoding
        async def handle_policy_request(reader, writer):
            """Handles reading and writing the streams around policy approval messages"""
            while True:
                try:
                    policy_payload = await reader.readuntil(b'\n\n')
                except ConnectionResetError:
                    logger.debug("Postfix said goodbye. Terminating this thread.")
                    return
                except CallableExhausted as e:
                    raise e
                except Exception:
                    logger.exception("UNEXPECTED ")
                    if reader.at_eof():
                        logger.debug("Postfix said goodbye oddly. Terminating this thread.")
                        return
                    continue
                logger.debug(f"Payload received: {policy_payload.decode(encoding)}")
                policy_data = PostfixPolicyRequest( policy_payload.decode(encoding).split('\n') )
                action = policy.approve_policy_request( policy_data )
                resp = ("action=" + action + "\n\n").encode()
                logger.debug(f"  .. SPF Enforcement sending {resp}")
                try:
                    writer.write( resp )
                except asyncio.CancelledError: # pragma: no cover
                    pass
                except Exception:
                    logger.exception(f"Exception raised trying to send {resp}")
                    return
        return handle_policy_request
