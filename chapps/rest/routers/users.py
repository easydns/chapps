from typing import Optional, List
from fastapi import APIRouter, Body, Path, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from chapps.rest.dbsession import sql_engine
from chapps.rest.models import (
    User,
    Quota,
    Domain,
    UserResp,
    UsersResp,
    DeleteResp,
    ErrorResp,
)
import logging, chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

api = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Resource not found."}},
)


@api.post(
    "/", status_code=201, responses={400: {"description": "Could not create user"}}
)
async def create_user(
    user: User,
    quota_id: int = Body(None, gt=0, title="Optionally supply a quota ID to link"),
    domain_ids: List[int] = Body(
        None, gt=0, title="Optionally supply a list of domain IDs to link"
    ),
):
    return UserResp.send(new_user, **extra_keys)


@api.delete("/{user_id}", response_model=DeleteResp)
async def delete_user(
    user_id: int = Path(..., gt=0, title="The ID of the user to delete")
):
    return DeleteResp.send(response, status=status)


@api.get("/")
async def list_all_users(skip: int = 0, limit: int = 1000, q: str = None):
    query = User.select_query(where=[f"name LIKE '%(pattern)s'"], window=(skip, limit))
    with pca.adapter_context() as cur:
        cur.execute(query)
        results = User.zip_records(cur.fetchall())
    return UsersResp.send(results)


@api.get("/{user_id}")
async def get_user(user_id: int):
    with Session(sql_engine) as session:
        try:
            stmt = User.select_by_id(user_id)
            u = session.scalar(stmt)
            if u:
                return UserResp.send(
                    User.wrap(u),
                    quota=Quota.wrap(u.quota),
                    domains=Domain.wrap(u.domains),
                )
        except Exception:
            logger.exception("get_user:")
    raise HTTPException(status_code=404, detail=f"There is no user with id {user_id}")


@api.get("/user-count/")
async def count_all_users():
    return await count_users("%")


@api.get("/user-count/{pattern}")
async def count_users(pattern: str):
    cur = pca.conn.cursor()
    sanitized_pattern = pattern
    query = f"SELECT COUNT( * ) FROM users WHERE name LIKE '%{sanitized_pattern}%';"
    cur.execute(query)
    results = cur.fetchone()[0]
    cur.close()
    return IntResp.send(results)
