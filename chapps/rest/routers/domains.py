from typing import List
from starlette import status
from fastapi import APIRouter  # , Body, Path, HTTPException
from chapps.util import AttrDict
from chapps.rest.models import User, Domain, DomainResp, DomainsResp
from .common import get_item_by_id, list_items, create_item
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

api = APIRouter(
    prefix="/domains",
    tags=["domains"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Domain not found."}
    },
)

api.get("/")(list_items(Domain, response_model=DomainsResp))

api.get("/{item_id}")(
    get_item_by_id(Domain, response_model=DomainResp, assoc=[(User, "users")])
)

api.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {
            "description": "Database integrity conflict."
        }
    },
)(
    create_item(
        Domain,  # default params argument will suffice
        response_model=DomainResp,
        assoc=[
            AttrDict(
                model=User,
                name="users",
                type_=List[int],
                join_table=Domain.metadata.tables["domain_user"],
                source_id="domain_id",
                model_id="user_id",
            )
        ],
    )
)
