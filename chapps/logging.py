"""
Logging
-------

This module's purpose is to ensure that CHAPPS modules
end up instantiating loggers which all share a common
formatter and handler.

It has been reworked a little bit since its inception,
and it may approach the issue from two directions, still.
It does attempt to be the first thing to get a handler,
and thereby be able to set the basic config.

But it also instantiates a logger at the top of the hierarchy,
one named simply `chapps`, so that all further CHAPPS loggers
(using the recommended pattern) will be under that parent logger
and inherit its config.

"""
import logging
from logging.handlers import SysLogHandler

DEFAULT_LEVEL = logging.DEBUG
"""Default minimum severity `DEBUG`"""

DEFAULT_FACILITY = SysLogHandler.LOG_LOCAL0
"""Default **syslog** facility `LOCAL0`"""


class LogSetup:  # pragma: no cover
    """Establish global log format and handler for CHAPPS

    For consistency, logs from different modules should all appear to come from
    CHAPPS, otherwise it may be quite a headache to make sense of them.  The
    class defines two different formatters, one for debugging and one for
    general use.  There is no fancy method in place for switching between them
    at present.

    The default formatter is very basic, simply prepending "CHAPPS:" and the
    severity level to the message.

    The default minimum severity at present is `DEBUG`.

    The default **syslog** facility is `LOCAL0`.

    It is possible to use **rsyslog** configuration to send different levels of
    the `LOCAL0` facility to different destinations, or to ignore `DEBUG`
    level messages entirely.  An example config is included in the project's
    ancillary materials.

    It had been a conscious decision not to include the :mod:`chapps.config`
    module in this module, in order to avoid circular dependencies when this
    module was included everywhere.  The rework has the config module loaded as
    part of package initialization, so it is no longer necessary to load it
    anywhere, since once it is loaded its job is done.

    .. todo::

      add configuration support for **syslog** facility and minimum severity.

    """

    debug_formatter = logging.Formatter(
        "CHAPPS:%(levelname)s %(filename)s@%(lineno)s: %(message)s"
    )
    """A formatter helpful for debugging."""

    maillog_formatter = logging.Formatter("CHAPPS:%(levelname)s %(message)s")
    """The default formatter, anticipated to go to the mail log"""

    syslog_handler = SysLogHandler(
        facility=DEFAULT_FACILITY, address="/dev/log"
    )
    """A handler which uses `/dev/log` to send messages to **syslog**"""

    syslog_handler.setLevel(DEFAULT_LEVEL)
    syslog_handler.setFormatter(maillog_formatter)  # or debug_formatter

    def __init__(self):
        """Setup logging

        If there are not yet any handlers, this routine calls
        :py:func:`logging.basicConfig` to set up basic logging configuration.

        If there are already handlers, for instance due to running within
        :mod:`pytest`, then nothing happens.

        """
        if not logging.getLogger(None).hasHandlers():
            logging.basicConfig(handlers=[self.syslog_handler])


LogSetup()
logger = logging.getLogger("chapps")
"""Create a logger in order to configure the top of the hierarchy"""
# without this, the library may not emit logs from a script
logger.setLevel(DEFAULT_LEVEL)
