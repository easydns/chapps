"""Signal handlers for CHAPPS"""
import signal, asyncio
import logging, chapps.logging
from chapps.config import config

logger = logging.getLogger(__name__)


class SignalHandlerFactory:  # pragma: no cover
    """A class for containing classmethods to create signal handlers"""

    @classmethod
    def signal_handler(cls, loop):
        """Pass in the asyncio event loop and get a closure which will end the program"""

        def signal_handler_closure(sig, frame=None):
            if sig in {signal.SIGTERM, sig.SIGINT}:
                logger.debug(f"CHAPPS exiting on {signal.Signals(sig)} ({sig}).")
                raise SystemExit

        return signal_handler_closure


class CHAPPSException(Exception):
    """Parent class for CHAPPS exceptions"""

class CallableExhausted(CHAPPSException):
    """A special exception for use during testing"""

class OutboundPolicyException(CHAPPSException):
    """Exceptions which occur during outbound mail processing"""


class NotAnEmailAddressException(CHAPPSException):
    """The string in question is not an email address"""


class TooManyAtsException(CHAPPSException):
    """An email address had too many at-signs in it"""


class ConfigurationError(CHAPPSException):
    """There was an error in the setting of configuration elements"""


class NullSenderException(OutboundPolicyException):
    """No sender address exists in the current policy request"""


class AuthenticationFailureException(OutboundPolicyException):
    """lack of user_key being treated as authentication failure"""
