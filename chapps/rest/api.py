"""
Top level API definition
------------------------

This module includes the other API-related modules
and configures the main :mod:`FastAPI` object which
answers web requests.  That object's name is `api`,
making its absolute symbol path :const:`chapps.rest.api.api`
"""
# Note that the API is powered by FastAPI and as such, the main API object
# itself is designed to be executed by uvicorn, probably a uvicorn worker
# coordinated by gunicorn (see FastAPI deployment docs)

from chapps.config import config
from chapps._version import __version__
from chapps.rest.routers import users, domains, quotas, emails, live
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
import chapps.logging
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

rest_readme = Path(config.chapps.docpath) / "README-API.md"
# Use the VenvDetector-derived docpath to locate the API readme

desc = rest_readme.open("rt").read()
# Read in the contents of the API readme

tags_metadata = [
    dict(
        name="users",
        description=(
            "<h3>Create, list, fetch, update, and delete operations "
            "involving users.</h3><p>Use the User Replace Quota route "
            "to assign a new <b>quota</b>.  There are some special routes "
            "for listing, allowing, or denying just some <b>domains</b>"
            " or <b>emails</b> without "
            "having to handle the entire set of associations.</p>"
        ),
    ),
    dict(
        name="domains",
        description=(
            "<h3>Create, list, fetch, update and delete operations for "
            "domains.</h3><p>When creating a <b>domain</b>, "
            "it is possible to specify a list of <b>user</b> IDs to "
            "associate.  There are some special routes for managing"
            " <b>user</b> associations without having"
            " to handle the entire set of associations.</p>"
        ),
    ),
    dict(
        name="quotas",
        description=(
            "<h3>Create, list, fetch, update and delete operations for "
            "quotas.</h3><p>Since there are very "
            "few <b>quotas</b> compared to the number of <b>users</b>, there is "
            "no support planned for managing <b>users</b> from their "
            "associated <b>quotas</b>.  To change a <b>quota</b> for a <b>user</b>, "
            "make use of the User Replace Quota route.</p>"
        ),
    ),
    dict(
        name="emails",
        description=(
            "<h3>Create, list, fetch, update and delete operations for "
            "email address objects.</h3>"
            "<p>When creating an <b>email</b>, it is possible to specify "
            "a list of <b>user</b> IDs to associate.  There are some special"
            " routes for managing <b>user</b> associations without having to"
            " handle the entire set of associations.</p>"
        ),
    ),
    dict(
        name="live",
        description=(
            "<h3>Status reporting and remote command interface.</h3><p>Routes "
            "provided for obtaining real-time remaining quota, resetting "
            "quota, refreshing policy settings, adding or removing SDAs, "
            "and causing CHAPPS to rewrite its config file, in order to "
            "allow for updates post-upgrade without losing site customizations.</p>"
        ),
    ),
]

api = FastAPI(
    title="CHAPPS REST API",
    description=desc,
    version=__version__,
    contact=dict(
        name="Caleb S. Cullen",
        url="https://github.com/easydns/chapps",
        email="ccullen@easydns.com",
    ),
    license_info=dict(name="MIT License", url="https://mit-license.org/"),
    openapi_tags=tags_metadata,
)
# The top-level :class:`fastapi.FastAPI` object

verstr = config.chapps.version
api.include_router(users.api)
api.include_router(domains.api)
api.include_router(quotas.api)
api.include_router(emails.api)
api.include_router(live.api)


@api.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    """Creates a log entry upon request validation error

    Also returns a reasonable response with code 422 to the browser.

    """
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    body = await request.json()
    logging.error(f"{body!r}: {exc_str}")
    content = {"status_code": 10422, "message": exc_str, "data": None}
    return JSONResponse(
        content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )
