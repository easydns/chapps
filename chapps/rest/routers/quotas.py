from typing import Optional, List
from fastapi import APIRouter, Body, Path, HTTPException
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
import logging, chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

api = APIRouter(
    prefix="/quotas",
    tags=["quotas"],
    responses={404: {"description": "Quota not found."}},
)

@api.get("/{quota_id}")
def get_quota(quota_id: int):
    with Session(sql_engine) as session:
        try:
            stmt = Quota.select_by_id(quota_id)
            q = session.scalar(stmt)
            if q:
                return QuotaResp.send(Quota.wrap(q))
        except Exception:
            logger.exception("get_quota:")
    raise HTTPException(
        status_code=404, detail=f"There is no quota with id {quota_id}"
    )
