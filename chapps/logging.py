"""CHAPPS module for controlling logging"""
import logging
from logging.handlers import SysLogHandler

DEFAULT_LEVEL = logging.DEBUG
MAILLOG_LEVEL = logging.INFO


class LogSetup:  # pragma: no cover
    syslog_formatter = logging.Formatter("CHAPPS:%(levelname)s %(filename)s@%(lineno)s: %(message)s")
    maillog_formatter = logging.Formatter("CHAPPS:%(levelname)s %(message)s")

    syslog_handler = SysLogHandler(facility=SysLogHandler.LOG_LOCAL0, address="/dev/log")
    syslog_handler.setLevel(DEFAULT_LEVEL)
    syslog_handler.setFormatter(syslog_formatter)

    maillog_handler = SysLogHandler(facility=SysLogHandler.LOG_MAIL, address="/dev/log")
    maillog_handler.setLevel(MAILLOG_LEVEL)
    maillog_handler.setFormatter(maillog_formatter)

    def __init__(self):
        if not logging.getLogger(None).hasHandlers():
            logging.basicConfig(
                handlers=[self.syslog_handler, self.maillog_handler]
            )


logsetup = LogSetup()  # pragma: no cover
logger = logging.getLogger("chapps")
