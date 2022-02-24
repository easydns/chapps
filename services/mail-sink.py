#!/usr/bin/env python3
"""
Starts a service on 127.0.0.1:25025 which serves as a sink for email
"""
### requires the python-pidfile library from https://github.com/mosquito/python-pidfile
### requires aiosmtpd
import asyncio, pidfile, signal, functools
from smtplib import SMTP, SMTPRecipientsRefused
import aiosmtpd
from aiosmtpd.handlers import Sink
from aiosmtpd.smtp import SMTP as SMTPServer
import logging

LISTEN_PORT = 25025
#TRANSMIT_PORT = 10026

logger = logging.getLogger(__name__)
logger.setLevel( logging.DEBUG )

def signal_handler( sig, *args ):
    if sig in { signal.SIGTERM, sig.SIGINT }:
        logger.debug(f"CHAPPS exiting on {signal.Signals(sig)} ({sig}).")
        raise SystemExit

def install_asyncio_signal_handlers(loop):
    for signame in { 'SIGTERM', 'SIGINT' }:
        sig = getattr( signal, signame )
        loop.add_signal_handler(
            sig,
            functools.partial( signal_handler, sig )
        )

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
    logger.debug("Starting SMTP sink...")
    try:
        with pidfile.PIDFile( '/tmp/mail-sink.pid' ):
            logger.debug('mail-sink started.')
            loop = asyncio.get_running_loop()
            install_asyncio_signal_handlers( loop )
            srv = await loop.create_server( functools.partial(SMTPServer, Sink), 'localhost', LISTEN_PORT, start_serving=False )
            async with srv:
                await srv.serve_forever()
    except pidfile.AlreadyRunningError:
        logger.exception("mail-sink is already running. Exiting.")
    except asyncio.exceptions.CancelledError:
        logger.debug("mail-sink exiting on signal.")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("UNEX")
