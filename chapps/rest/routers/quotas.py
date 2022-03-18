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
from chapps.rest.routers.common import list_query_params
import logging, chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

api = APIRouter(
    prefix="/quotas",
    tags=["quotas"],
    responses={404: {"description": "Quota not found."}},
)


@api.get("/")
async def list_quotas(lparms: dict = Depends(list_query_params)):
    with Session(sql_engine) as session:
        try:
            stmt = Quota.select_by_pattern(lparms.get('q', None) or '%').offset(lparms.get('skip')).limit(lparms.get('limit'))
            qs = [Quota.wrap(q) for q in session.scalars(stmt)]
            if qs:
                return QuotasResp.send(qs)
        except Exception:
            logger.exception("list_quotas:")
    raise HTTPException(
        status_code=404, detail=f"No quotas found with names matching {q}"
    )


@api.get("/{quota_id}")
async def get_quota(quota_id: int):
    with Session(sql_engine) as session:
        try:
            stmt = Quota.select_by_id(quota_id)
            q = session.scalar(stmt)
            if q:
                return QuotaResp.send(Quota.wrap(q))
        except Exception:
            logger.exception("get_quota:")
    raise HTTPException(status_code=404, detail=f"There is no quota with id {quota_id}")
