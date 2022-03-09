#!/usr/bin/env python3
"""
Starts a service on 127.0.0.1:10025 which serves as a null content filter
"""
### requires the python-pidfile library from https://github.com/mosquito/python-pidfile
### requires aiosmtpd
import asyncio, pidfile, signal, functools
from smtplib import SMTP, SMTPRecipientsRefused
from aiosmtpd.smtp import SMTP as SMTPServer
from aiosmtpd.handlers import Proxy, Debugging
from aiosmtpd.controller import Controller
import logging
from logging.handlers import SysLogHandler

LISTEN_ADDR = "localhost"
LISTEN_PORT = 10025
TRANSMIT_ADDR = LISTEN_ADDR
TRANSMIT_PORT = 10026


logging.basicConfig(
    handlers=[SysLogHandler(facility=SysLogHandler.LOG_LOCAL4, address="/dev/log")]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

SMTPServer_HANDLER = functools.partial(SMTPServer, Proxy(TRANSMIT_ADDR, TRANSMIT_PORT))


def signal_handler(sig, *args):
    if sig in {signal.SIGTERM, signal.SIGINT}:
        logger.debug(f"null-filter exiting on signal {sig}.")
        raise SystemExit


def install_asyncio_signal_handlers(loop):
    for signame in {"SIGTERM", "SIGINT"}:
        sig = getattr(signal, signame)
        loop.add_signal_handler(sig, functools.partial(signal_handler, sig))


# class NullFilterHandler:
#     async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
#         """Handle recipient phase"""
#         envelope.rcpt_tos.append( address )
#         return "250 OK"

#     async def handle_DATA(self, server, session, envelope):
#         """Handle DATA phase"""
#         logger.debug(f"Message from {envelope.mail_from} to ")
#         try:
#             client = SMTP.sendmail( envelope.mail_from, envelope.rcpt_tos, envelope.content )
#             return '250 Message accepted for delivery'
#         except smtplib.SMTPResponseException as e:
#             logger.exception("Upstream Postfix did not like this message.")
#             return f"{e.smtp_code} {e.smtp_error}"
#         except smtplib.SMTPException:
#             logger.exception("Raised trying to send from {envelope.mail_from} to {','.join(envelope.rcpt_tos)}")
#             return "550 Requested action not taken"


async def main():
    """The grand shebang"""
    logger.debug("Starting null-filter...")
    try:
        with pidfile.PIDFile("/tmp/null_filter.pid"):
            logger.debug("null-filter started.")
            loop = asyncio.get_running_loop()
            install_asyncio_signal_handlers(loop)
            srv = await loop.create_server(
                SMTPServer_HANDLER, LISTEN_ADDR, LISTEN_PORT, start_serving=False
            )
            await srv.serve_forever()
    except TimeoutError:
        logger.exception("SMTPServer took too long to start.")
    except pidfile.AlreadyRunningError:
        logger.exception("null-filter is already running. Exiting.")
    except asyncio.exceptions.CancelledError:
        logger.debug("null-filter exiting on signal.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("UNEXPECTED")
