"""API-related objects for CHAPPS"""
# Note that the API is powered by FastAPI and as such, the main API object
# itself is designed to be executed by uvicorn, probably a uvicorn worker
# coordinated by gunicorn (see FastAPI deployment docs)

from chapps.config import config
from chapps.rest.routers import users, domains, quotas
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

api = FastAPI()
verstr = config.chapps.version
api.include_router(users.api)
api.include_router(domains.api)
api.include_router(quotas.api)


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
