#!/usr/bin/env python3
"""Caching, Highly-Available Postfix Policy Service: Outbound Multi-filter"""

### requires the python-pidfile library from https://github.com/mosquito/python-pidfile
import asyncio, pidfile, signal, functools
from chapps.switchboard import OutboundMultipolicyHandler
from chapps.config import config
from chapps.signals import SignalHandlerFactory
from pathlib import Path
import logging

logger = logging.getLogger("chapps."+__name__)
APPNAME = "CHAPPS Outbound Multi"


def install_asyncio_signal_handlers(loop):
    for signame in {"SIGTERM", "SIGINT"}:
        sig = getattr(signal, signame)
        loop.add_signal_handler(
            sig, functools.partial(SignalHandlerFactory.signal_handler(loop), sig)
        )


async def main():
    """The grand shebang"""
    pidfile_name = Path(__file__).stem + ".pid"
    logger.debug(f"Starting {APPNAME} with pidfile {pidfile_name}...")
    try:
        with pidfile.PIDFile(f"/tmp/{pidfile_name}"):
            logger.debug(f"{APPNAME} service started.")
            handler = OutboundMultipolicyHandler()
            handle_policy_request = handler.async_policy_handler()
            install_asyncio_signal_handlers(asyncio.get_running_loop())
            srv = await asyncio.start_server(
                handle_policy_request,
                handler.listen_address,
                handler.listen_port,
                start_serving=False,
            )
            await srv.serve_forever()
    except pidfile.AlreadyRunningError:
        logger.exception(f"{APPNAME} is already running. Exiting.")
    except asyncio.exceptions.CancelledError:
        logger.debug(f"{APPNAME} exiting on signal.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        logger.exception("This error occurs if the application dies ungracefully.")
    except Exception:
        logger.exception("CHAPPS exiting due to UNEXPECTED exception.")
