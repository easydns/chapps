"""API-related objects for CHAPPS"""
# Note that the API is powered by FastAPI and as such, the main API object
# itself is designed to be executed by uvicorn, probably a uvicorn worker
# coordinated by gunicorn (see FastAPI deployment docs)

from chapps.config import config
from chapps._version import __version__
from chapps.rest.routers import users, domains, quotas, live
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
import chapps.logging
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

restpath = Path(__file__).resolve().parent
rest_readme = restpath / "README.md"
desc = rest_readme.open("rt").read()

tags_metadata = [
    dict(
        name="users",
        description=(
            "CRUD operations involving users.  Update a user "
            "to assign a new quota.  Some special routes are "
            "planned for adding/removing just some domains without "
            "having to handle the entire set of associations."
        ),
    ),
    dict(
        name="domains",
        description=(
            "CRUD operations for domains.  When creating a domain, "
            "it is possible to specify a list of user-ids to "
            "associate.  Some special routes are planned for managing"
            " user associations (add/remove arbitrary) without having"
            " to handle the entire set of associations."
        ),
    ),
    dict(
        name="quotas",
        description=(
            "CRUD operations for quotas.  Since there are very "
            "few quotas compared to the number of users, there is "
            "no support planned for managing users from their "
            "associated quotas.  To change a quota for a user, "
            "update the user."
        ),
    ),
    dict(
        name="live",
        description=(
            "Status reporting and remote command interface.  Routes "
            "provided for obtaining real-time remaining quota, resetting "
            "quota, refreshing policy settings, adding or removing SDAs, "
            "and causing CHAPPS to rewrite its config file, in order to "
            "allow for updates post-upgrade without losing site customizations."
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
verstr = config.chapps.version
api.include_router(users.api)
api.include_router(domains.api)
api.include_router(quotas.api)
api.include_router(live.api)


@api.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    body = await request.json()
    logging.error(f"{body!r}: {exc_str}")
    content = {"status_code": 10422, "message": exc_str, "data": None}
    return JSONResponse(
        content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )
