#!/usr/bin/env python3
"""
Starts a service on 127.0.0.1:25025 which serves to receive email which it
echoes over a UDS which it opens
"""
### requires the python-pidfile library from https://github.com/mosquito/python-pidfile
### requires aiosmtpd
import asyncio, pidfile, signal, functools
from smtplib import SMTP, SMTPRecipientsRefused
import aiosmtpd
from aiosmtpd.handlers import Sink, Debugging
from aiosmtpd.smtp import SMTP as SMTPServer
from tempfile import TemporaryDirectory
from contextlib import ExitStack
from pathlib import Path
import logging

APPNAME = "CHAPPS testing SMTP-UDS echo service"
LISTEN_PORT = 25025
# TRANSMIT_PORT = 10026

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def signal_handler(sig, *args):
    if sig in {signal.SIGTERM, sig.SIGINT}:
        logger.debug(f"CHAPPS exiting on {signal.Signals(sig)} ({sig}).")
        raise SystemExit


def install_asyncio_signal_handlers(loop):
    for signame in {"SIGTERM", "SIGINT"}:
        sig = getattr(signal, signame)
        loop.add_signal_handler(sig, functools.partial(signal_handler, sig))


async def main():
    """The grand shebang"""
    logger.debug("Starting {APPNAME}...")
    resources = ExitStack()
    tempdir = resources.enter_context(TemporaryDirectory())
    pidfile_name = Path(__file__).stem + ".pid"
    try:
        with pidfile.PIDFile(f"/tmp/{pidfile_name}"):
            echofile = Path("/tmp") / "smtp-echo.txt"
            efh = resources.enter_context(echofile.open("a"))
            logger.debug("{APPNAME} started.")
            print(f"Opened for writing.", file=efh)
            loop = asyncio.get_running_loop()
            install_asyncio_signal_handlers(loop)
            srv = await loop.create_server(
                functools.partial(SMTPServer, Debugging(efh)),
                "localhost",
                LISTEN_PORT,
                start_serving=False,
            )
            async with srv:
                await asyncio.gather(srv.serve_forever())
    except pidfile.AlreadyRunningError:
        logger.exception("mail-sink is already running. Exiting.")
    except asyncio.exceptions.CancelledError:
        logger.debug("mail-sink exiting on signal.")
    resources.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("UNEX")
