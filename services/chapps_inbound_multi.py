#!/usr/bin/env python3
"""Caching, Highly-Available Postfix Policy Service: Inbound Multi-filter"""

# requires the python-pidfile library from
# https://github.com/mosquito/python-pidfile
import asyncio
import pidfile
import signal
import functools
from chapps.switchboard import CHAPPSServer, InboundMultipolicyHandler
from chapps.signals import SignalHandlerFactory
from pathlib import Path
import logging

logger = logging.getLogger("chapps." + __name__)
APPNAME = "CHAPPS Inbound Multi"


def install_asyncio_signal_handlers(loop):
    for signame in {"SIGTERM", "SIGINT"}:
        sig = getattr(signal, signame)
        loop.add_signal_handler(
            sig,
            functools.partial(SignalHandlerFactory.signal_handler(loop), sig),
        )


async def main():
    """The grand shebang"""
    pidfile_name = Path(__file__).stem + ".pid"
    logger.debug(f"Starting {APPNAME} with pidfile {pidfile_name}...")
    try:
        with pidfile.PIDFile(f"/tmp/{pidfile_name}"):
            logger.debug(f"{APPNAME} service started.")
            handler = InboundMultipolicyHandler()
            handle_policy_request = handler.async_policy_handler()
            chapps_server = CHAPPSServer(handle_policy_request)
            main_loop = chapps_server.main_loop()
            install_asyncio_signal_handlers(asyncio.get_running_loop())
            srv = await asyncio.start_server(
                main_loop,
                handler.listen_address,
                handler.listen_port,
                backlog=handler.listener_backlog,
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
        logger.exception(
            "This error occurs if the application dies ungracefully."
        )
    except Exception:
        logger.exception("CHAPPS exiting due to UNEXPECTED exception.")
