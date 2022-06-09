"""
**Email** record management implemented by factories
----------------------------------------------------

This module defines the management routes for **Email** records, and also the :class:`~.JoinAssoc` between **Email** and **User** tables.

It is implemented using factory functions from the :mod:`~.common` module, in a nearly-identical way to the :mod:`~.domains` module, just using :class:`~chapps.models.Email` as the main data model.

"""

from typing import List
from starlette import status
from fastapi import APIRouter  # , Body, Path, HTTPException
from chapps.models import (
    User,
    Email,
    EmailResp,
    EmailsResp,
    UsersResp,
    DeleteResp,
    TextResp,
    AssocOperation,
    email_users_assoc,
)
from chapps.rest.routers.common import (
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
"""The **Email** object API router"""

email_join_assoc = [email_users_assoc]
"""List of join associations for **Email** objects"""

api.get("/", response_model=EmailsResp)(
    list_items(Email, response_model=EmailsResp)
)

api.get("/{item_id}", response_model=EmailResp)(
    get_item_by_id(Email, response_model=EmailResp, assoc=email_join_assoc)
)

api.get("/{item_id}/users/", response_model=UsersResp)(
    list_associated(Email, assoc=email_users_assoc, response_model=UsersResp)
)

api.post(
    "/",
    status_code=201,
    response_model=EmailResp,
    responses={status.HTTP_409_CONFLICT: {"description": "Unique key error."}},
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

api.put("/{item_id}/users/", response_model=TextResp)(
    adjust_associations(
        Email, assoc=email_join_assoc, assoc_op=AssocOperation.add
    )
)

api.delete("/{item_id}/users/", response_model=TextResp)(
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
