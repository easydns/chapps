"""API-related objects for CHAPPS"""
### Note that the API is powered by FastAPI and as such, the main API object itself is designed to be
###   executed by uvicorn, probably a uvicorn worker coordinated by gunicorn (see FastAPI deployment docs)

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


##### Domains


@api.get("/domain/{domain_id}", response_model=DomainResp)
async def get_domain(domain_id: int = Path(..., gt=0)):
    query = Domain.select_query(where=[f"id={domain_id}"])
    with pca.adapter_context() as cur:
        cur.execute(query)
        results = Domain.zip_records(cur.fetchall())
        if results:
            results = results[0]
            return DomainResp.send(results)
    return ErrorResp.send(
        None, error="nonexistent", message=f"There is no user with id {user_id}"
    )


@api.get("/domains/", response_model=List[Domain])
async def list_all_domains(skip: int = 0, limit: int = 1000, ids: List[int] = None):
    return await list_domains("%", skip, limit, ids)


@api.get("/domains/{pattern}", response_model=List[Domain])
async def list_domains(
    pattern: str, skip: int = 0, limit: int = 1000, ids: List[int] = None
):
    sanitized_pattern = pattern
    where = [f"name LIKE '%{sanitized_pattern}%'"]
    if ids:
        where.append(f"id IN ({','.join(ids)})")
    query = Domain.select_query(where=where, window=(skip, limit))
    with pca.adapter_context() as cur:
        cur.execute(query)
        results = Domain.zip_records(cur.fetchall())
    return DomainsResp.send(results)
