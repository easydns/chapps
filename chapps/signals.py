"""
Signal handlers and custom exceptions
-------------------------------------

In order to shut down gracefully, we want to provide a signal handler when a
service (handler) loop starts.  Also, CHAPPS raises a few different custom
exceptions, which are defined here.

"""
import signal
import logging

logger = logging.getLogger(__name__)


class SignalHandlerFactory:  # pragma: no cover
    """A class for containing classmethods to create signal handlers"""

    # could be organized differently; instantiating the class would return
    # an instance with __call__ defined, so that it is callable, and then
    # would in turn call the closure function;

    @classmethod
    def signal_handler(cls, loop=None) -> callable:
        """Returns a signal-checking, exiting closure

        :param loop: *Deprecated*

        :returns: a closure that looks for :const:`~signal.SIGTERM` or
          :const:`~signal.SIGINT` and raises :exc:`SystemExit` if it finds
          either one.

        .. todo::

          Since the returned closure is actually completely static, this could
          be simplified greatly.  However, it works and doesn't cost much, so
          it low on the list.

        """

        def signal_handler_closure(sig, frame=None):
            if sig in {signal.SIGTERM, sig.SIGINT}:
                logger.info(
                    f"CHAPPS exiting on {signal.Signals(sig)} ({sig})."
                )
                raise SystemExit

        return signal_handler_closure


class CHAPPSException(Exception):
    """Parent class for CHAPPS exceptions"""


class CallableExhausted(CHAPPSException):
    """A special exception for use during testing"""


class NotAnEmailAddressException(CHAPPSException):
    """An email address contained no at-signs"""


class TooManyAtsException(CHAPPSException):
    """An email address had too many at-signs in it"""


class ConfigurationError(CHAPPSException):
    """There was an error in the setting of configuration elements"""


class OutboundPolicyException(CHAPPSException):
    """Parent of exceptions which occur during outbound mail processing"""


class NullSenderException(OutboundPolicyException):
    """No sender address exists in the current policy request"""


class AuthenticationFailureException(OutboundPolicyException):
    """Lack of user-identifier being treated as authentication failure"""


class InboundPolicyException(CHAPPSException):
    """Parent of exceptions arising during inbound email processing"""


class NoRecipientsException(InboundPolicyException):
    """This is raised if the recipient field is somehow empty"""
