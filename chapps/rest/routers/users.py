from typing import List
from fastapi import status, APIRouter, Path
from ..dbsession import sql_engine
from ..models import User, Quota, Domain, UserResp, UsersResp, DeleteResp
from .common import get_item_by_id, list_items, create_item, delete_item
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

api = APIRouter(
    prefix="/users", tags=["users"], responses={404: {"description": "User not found."}}
)


api.post(
    "/",
    status_code=201,
    response_model=UserResp,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Could not create user."},
        status.HTTP_409_CONFLICT: {"description": "Unique key error."},
    },
)(
    create_item(
        User,
        response_model=UserResp,
        assoc=[
            User.join_assoc(
                assoc_name="quota",
                assoc_type=int,
                assoc_model=Quota,
                assoc_id="quota_id",
                table=User.Meta.orm_model.metadata.tables["quota_user"],
            ),
            User.join_assoc(
                assoc_name="domains",
                assoc_type=List[int],
                assoc_model=Domain,
                assoc_id="domain_id",
                table=User.Meta.orm_model.metadata.tables["domain_user"],
            ),
        ],
    )
)


api.delete("/", response_model=DeleteResp)(delete_item(User))


api.get("/", response_model=UsersResp)(list_items(User, response_model=UsersResp))


api.get("/{item_id}", response_model=UserResp)(
    get_item_by_id(
        User, response_model=UserResp, assoc=[(Quota, "quota"), (Domain, "domains")]
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
