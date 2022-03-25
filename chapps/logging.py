"""CHAPPS module for controlling logging"""
import logging
from logging.handlers import SysLogHandler

DEFAULT_LEVEL = logging.DEBUG


class LogSetup:  # pragma: no cover
    debug_formatter = logging.Formatter(
        "CHAPPS:%(levelname)s %(filename)s@%(lineno)s: %(message)s"
    )
    maillog_formatter = logging.Formatter("CHAPPS:%(levelname)s %(message)s")

    syslog_handler = SysLogHandler(
        facility=SysLogHandler.LOG_LOCAL0, address="/dev/log"
    )
    syslog_handler.setLevel(DEFAULT_LEVEL)
    syslog_handler.setFormatter(maillog_formatter)  # or debug_formatter

    def __init__(self):
        if not logging.getLogger(None).hasHandlers():
            logging.basicConfig(handlers=[self.syslog_handler])


logsetup = LogSetup()
logger = logging.getLogger("chapps")
# without this, the library may not emit logs from a script
logger.setLevel(DEFAULT_LEVEL)
