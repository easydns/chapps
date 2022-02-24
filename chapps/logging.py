"""CHAPPS module for controlling logging"""
import logging
from logging.handlers import SysLogHandler

class LogSetup(): # pragma: no cover
    ROOT_LOG_FORMAT = "CHAPPS:%(levelname)s %(filename)s@%(lineno)s: %(message)s"
    MAIN_LOG_FORMAT = "CHAPPS:%(levelname)s %(name)s@%(funcName)s: %(message)s"

    def __init__(self):
        if not logging.getLogger( None ).hasHandlers():
            logging.basicConfig(format=self.ROOT_LOG_FORMAT, handlers=[
                SysLogHandler(
                    facility=SysLogHandler.LOG_LOCAL0,
                    address='/dev/log'
                )
            ])

logsetup = LogSetup() # pragma: no cover
