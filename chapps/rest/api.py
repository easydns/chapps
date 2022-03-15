"""API-related objects for CHAPPS"""
# Note that the API is powered by FastAPI and as such, the main API object
# itself is designed to be executed by uvicorn, probably a uvicorn worker
# coordinated by gunicorn (see FastAPI deployment docs)

from chapps.config import config
from chapps.rest.models import (
    User,
    Quota,
    Domain,
    UserResp,
    UsersResp,
    DomainResp,
    DomainsResp,
    QuotaResp,
    QuotasResp,
    IntResp,
    ConfigResp,
    DeleteResp,
    ErrorResp,
)
from chapps.rest.routers import users
from typing import Optional, List
from fastapi import FastAPI, Path, Query, Body
from pydantic import BaseModel
import time
import logging, chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

api = FastAPI()
verstr = config.chapps.version
api.include_router(users.api)
