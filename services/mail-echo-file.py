#!/usr/bin/env python3
"""
Starts a service on 127.0.0.1:25025 which serves to receive email which it
echoes into a file which the test may open
"""
### requires the python-pidfile library from https://github.com/mosquito/python-pidfile
### requires aiosmtpd
import asyncio
import pidfile
import signal
import functools
from aiosmtpd.handlers import Debugging
from aiosmtpd.smtp import SMTP as SMTPServer
from contextlib import ExitStack
from pathlib import Path
import logging

APPNAME = "CHAPPS testing SMTP-file echo service"
LISTEN_PORT = 25025
ECHO_FILE = Path("/tmp/smtp-echo.txt")
# TRANSMIT_PORT = 10026

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def signal_handler(sig, *args):
    if sig in {signal.SIGTERM, sig.SIGINT}:
        logger.debug(f"{APPNAME} exiting on {signal.Signals(sig)} ({sig}).")
        raise SystemExit


def install_asyncio_signal_handlers(loop):
    for signame in {"SIGTERM", "SIGINT"}:
        sig = getattr(signal, signame)
        loop.add_signal_handler(sig, functools.partial(signal_handler, sig))


class SavingEmailHandler(Debugging):
    def __init__(self, pathname: str = None):
        super().__init__()
        self.echo_file = Path(pathname or ECHO_FILE)

    async def handle_DATA(self, server, session, envelope):
        data = envelope.original_content.decode("utf-8")
        self.echo_file.write_text(data)
        return "250 Message saved"


async def main():
    """The grand shebang"""
    logger.debug("Starting {APPNAME}...")
    resources = ExitStack()
    pidfile_name = Path(__file__).stem + ".pid"
    try:
        with pidfile.PIDFile(f"/tmp/{pidfile_name}"):
            echofile = ECHO_FILE
            try:
                echofile.unlink()
            except OSError:
                if echofile.exists():
                    raise
            logger.debug("{APPNAME} started.")
            loop = asyncio.get_running_loop()
            install_asyncio_signal_handlers(loop)
            srv = await loop.create_server(
                functools.partial(SMTPServer, SavingEmailHandler(echofile)),
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
