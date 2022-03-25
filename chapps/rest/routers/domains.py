from typing import List
from starlette import status
from fastapi import APIRouter  # , Body, Path, HTTPException
from chapps.util import AttrDict
from chapps.rest.models import User, Domain, DomainResp, DomainsResp, DeleteResp
from .common import get_item_by_id, list_items, create_item
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

api = APIRouter(
    prefix="/domains",
    tags=["domains"],
    responses={status.HTTP_404_NOT_FOUND: {"description": "Domain not found."}},
)

api.get("/")(list_items(Domain, response_model=DomainsResp))

api.get("/{item_id}")(
    get_item_by_id(Domain, response_model=DomainResp, assoc=[(User, "users")])
)

api.post(
    "/",
    status_code=201,
    response_model=DomainResp,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Unable to create domain"},
        status.HTTP_409_CONFLICT: {"description": "Unique key error."},
    },
)(
    create_item(
        Domain,
        response_model=DomainResp,
        params=dict(name=str),
        assoc=[
            Domain.join_assoc(
                assoc_name="users",
                assoc_type=List[int],
                assoc_model=User,
                assoc_id="user_id",
                table=Domain.Meta.orm_model.metadata.tables["domain_user"],
            )
        ],
    )
)

api.delete(
    "/",
    status_code=200,
    response_model=DeleteResp,
    responses={
        status.HTTP_202_ACCEPTED: {"description": "Items will be deleted."},
        status.HTTP_204_NO_CONTENT: {"description": "No item to delete."},
        status.HTTP_409_CONFLICT: {"description": "Database integrity conflict."},
    },
)(
    delete_item(Domain)
)  # params=dict(ids=List[int]) by default
