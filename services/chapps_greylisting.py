#!/usr/bin/env python3
"""Caching, Highly-Available Postfix Policy Service - Greylisting"""

### requires the python-pidfile library from https://github.com/mosquito/python-pidfile
import asyncio, pidfile, signal, functools
from chapps.switchboard import GreylistingHandler
from chapps.config import config
from chapps.signals import SignalHandlerFactory
import logging, chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def install_asyncio_signal_handlers(loop):
    for signame in {"SIGTERM", "SIGINT"}:
        sig = getattr(signal, signame)
        loop.add_signal_handler(
            sig, functools.partial(SignalHandlerFactory.signal_handler(loop), sig)
        )


async def main():
    """The grand shebang"""
    logger.debug("Starting CHAPPS Greylisting...")
    try:
        with pidfile.PIDFile("/tmp/chapps_greylisting.pid"):
            logger.debug("CHAPPS Greylisting service started.")
            handler = GreylistingHandler()
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
        logger.exception("CHAPPS Greylisting is already running. Exiting.")
    except asyncio.exceptions.CancelledError:
        logger.debug("CHAPPS Greylisting exiting on signal.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        logger.exception("UNEX")
