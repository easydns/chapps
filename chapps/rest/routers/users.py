from typing import Optional, List
from fastapi import APIRouter, Body, Path, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..dbsession import sql_engine
from ..models import (
    User,
    Quota,
    Domain,
    UserResp,
    UsersResp,
    DeleteResp,
    ErrorResp,
)
from .common import get_item_by_id, list_items, list_query_params
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

api = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "User not found."}},
)


@api.post(
    "/",
    status_code=201,
    responses={400: {"description": "Could not create user"}},
)
async def create_user(
    user: User,
    quota_id: int = Body(
        None, gt=0, title="Optionally supply a quota ID to link"
    ),
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


api.get("/")(list_items(User, engine=sql_engine, response_model=UsersResp))


api.get("/{item_id}")(
    get_item_by_id(
        User,
        engine=sql_engine,
        response_model=UserResp,
        assoc=dict(quota=Quota, domains=Domain),
    )
)


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
