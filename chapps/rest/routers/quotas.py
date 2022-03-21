from typing import Optional, List
from fastapi import APIRouter, Body, Path, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from chapps.rest.dbsession import sql_engine
from chapps.rest.models import (
    User,
    Quota,
    Domain,
    QuotaResp,
    QuotasResp,
    DeleteResp,
    ErrorResp,
)
from chapps.rest.routers.common import (
    list_query_params,
    get_item_by_id,
    list_items,
)
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

api = APIRouter(
    prefix="/quotas",
    tags=["quotas"],
    responses={404: {"description": "Quota not found."}},
)


api.get("/")(list_items(Quota, engine=sql_engine, response_model=QuotasResp))


api.get("/{item_id}")(
    get_item_by_id(Quota, engine=sql_engine, response_model=QuotaResp)
)
