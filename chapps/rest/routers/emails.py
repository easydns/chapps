from typing import List
from starlette import status
from fastapi import APIRouter  # , Body, Path, HTTPException
from chapps.rest.models import (
    User,
    Email,
    EmailResp,
    EmailsResp,
    UsersResp,
    DeleteResp,
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
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

api = APIRouter(
    prefix="/emails",
    tags=["emails"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Email not found."}},
)

email_join_assoc = [
    Email.join_assoc(
        assoc_name="users",
        assoc_type=List[int],
        assoc_model=User,
        assoc_id="user_id",
        table=Email.Meta.orm_model.metadata.tables["email_user"],
    )
]

api.get("/", response_model=EmailsResp)(
    list_items(Email, response_model=EmailsResp)
)

api.get("/{item_id}", response_model=EmailResp)(
    get_item_by_id(Email, response_model=EmailResp, assoc=email_join_assoc)
)

api.get("/{item_id}/allowed/", response_model=UsersResp)(
    list_associated(Email, assoc=email_join_assoc[0], response_model=UsersResp)
)

api.post(
    "/",
    status_code=201,
    response_model=EmailResp,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Unable to create email"},
        status.HTTP_409_CONFLICT: {"description": "Unique key error."},
    },
)(
    create_item(
        Email,
        response_model=EmailResp,
        params=dict(name=str),
        assoc=email_join_assoc,
    )
)

api.put("/", response_model=EmailResp)(
    update_item(Email, response_model=EmailResp, assoc=email_join_assoc)
)

api.put("/{item_id}/allow/", response_model=TextResp)(
    adjust_associations(
        Email, assoc=email_join_assoc, assoc_op=AssocOperation.add
    )
)

api.put("/{item_id}/deny/", response_model=TextResp)(
    adjust_associations(
        Email, assoc=email_join_assoc, assoc_op=AssocOperation.subtract
    )
)

api.delete(
    "/",
    response_model=DeleteResp,
    responses={
        status.HTTP_202_ACCEPTED: {"description": "Items will be deleted."},
        status.HTTP_204_NO_CONTENT: {"description": "No item to delete."},
        status.HTTP_409_CONFLICT: {
            "description": "Database integrity conflict."
        },
    },
)(
    delete_item(Email)
)  # params=dict(ids=List[int]) by default
