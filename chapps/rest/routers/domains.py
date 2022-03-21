from typing import Optional, List
from fastapi import APIRouter, Body, Path, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from chapps.rest.dbsession import sql_engine
from chapps.rest.models import (
    User,
    Quota,
    Domain,
    DomainResp,
    DomainsResp,
    DeleteResp,
    ErrorResp,
)
from .common import get_item_by_id, list_items
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

api = APIRouter(
    prefix="/domains",
    tags=["domains"],
    responses={404: {"description": "Domain not found."}},
)

api.get("/")(list_items(Domain, engine=sql_engine, response_model=DomainsResp))

api.get("/{item_id}")(
    get_item_by_id(
        Domain,
        engine=sql_engine,
        response_model=DomainResp,
        assoc=dict(users=User),
    )
)
