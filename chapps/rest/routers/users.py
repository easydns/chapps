from typing import List
from fastapi import status, APIRouter
from ..models import (
    User,
    Quota,
    Domain,
    Email,
    UserResp,
    UsersResp,
    DomainsResp,
    DeleteResp,
    IntResp,
    TextResp,
    AssocOperation,
)
from .common import (
    get_item_by_id,
    list_items,
    create_item,
    delete_item,
    update_item,
    adjust_associations,
    list_associated,
)
import logging
import chapps.logging

logger = logging.getLogger(__name__)

api = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "User not found."}},
)

user_quota_assoc = User.join_assoc(
    assoc_name="quota",
    assoc_type=int,
    assoc_model=Quota,
    assoc_id=Quota.id_name(),
    table=User.Meta.orm_model.metadata.tables["quota_user"],
)

user_domains_assoc = User.join_assoc(
    assoc_name="domains",
    assoc_type=List[int],
    assoc_model=Domain,
    assoc_id=Domain.id_name(),
    table=User.Meta.orm_model.metadata.tables["domain_user"],
)

user_emails_assoc = User.join_assoc(
    assoc_name="emails",
    assoc_type=List[int],
    assoc_model=Email,
    assoc_id=Email.id_name(),
    table=User.Meta.orm_model.metadata.tables["email_user"],
)

user_join_assoc = [user_quota_assoc, user_domains_assoc, user_emails_assoc]

api.post(
    "/",
    status_code=201,
    response_model=UserResp,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Could not create user."},
        status.HTTP_409_CONFLICT: {"description": "Unique key error."},
    },
)(create_item(User, response_model=UserResp, assoc=user_join_assoc))


api.delete("/", response_model=DeleteResp)(delete_item(User))


api.get("/", response_model=UsersResp)(
    list_items(User, response_model=UsersResp)
)


api.get("/{item_id}", response_model=UserResp)(
    get_item_by_id(User, response_model=UserResp, assoc=user_join_assoc)
)

api.get("/{item_id}/allowed/", response_model=DomainsResp)(
    list_associated(User, assoc=user_domains_assoc, response_model=DomainsResp)
)

api.put("/", response_model=UserResp)(
    update_item(User, response_model=UserResp, assoc=user_join_assoc)
)

api.put("/{item_id}/allow/", response_model=TextResp)(
    adjust_associations(
        User, assoc=[user_domains_assoc], assoc_op=AssocOperation.add
    )
)

api.put("/{item_id}/deny/", response_model=TextResp)(
    adjust_associations(
        User, assoc=[user_domains_assoc], assoc_op=AssocOperation.subtract
    )
)

api.put("/{item_id}/quota/{quota_id}")(
    adjust_associations(
        User, assoc=[user_quota_assoc], assoc_op=AssocOperation.replace
    )
)

# commenting out to get a clean release without these non-working routes
#
# we will provide these routes in a future release
# along with routes to count a user's domain authorizations
# and paginate the list of those authorizations


# @api.get("/count/", response_model=IntResp)
# async def count_all_users():
#     return await count_users("%")


# @api.get("/count/{pattern}", response_model=IntResp)
# async def count_users(pattern: str):
#     cur = pca.conn.cursor()
#     sanitized_pattern = pattern
#     query = f"SELECT COUNT( * ) FROM users WHERE name LIKE ?"
#     logger.debug(
#         f"Attempting to count users like {pattern} with query {query}"
#     )
#     cur.execute(query, (f"%{pattern}%",))
#     results = cur.fetchone()[0]
#     cur.close()
#     return IntResp.send(results)
