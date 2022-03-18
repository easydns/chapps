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
import logging, chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

api = APIRouter(
    prefix="/domains",
    tags=["domains"],
    responses={404: {"description": "Domain not found."}},
)


@api.get("/{domain_id}")
def get_domain(domain_id: int):
    with Session(sql_engine) as session:
        try:
            stmt = Domain.select_by_id(domain_id)
            d = session.scalar(stmt)
            if d:
                return DomainResp.send(Domain.wrap(d))
        except Exception:
            logger.exception("get_domain:")
    raise HTTPException(
        status_code=404, detail=f"There is no domain with id {domain_id}"
    )
