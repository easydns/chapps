"""routes for live access to CHAPPS state"""
from typing import List, Optional
from fastapi import status, APIRouter, Body, HTTPException
from ..models import User, Quota, Domain, LiveQuotaResp
from ...policy import OutboundQuotaPolicy
from ..dbsession import sql_engine
from sqlalchemy.orm import sessionmaker
from time import strftime, gmtime
import logging

logger = logging.getLogger(__name__)
Session = sessionmaker(sql_engine)

api = APIRouter(
    prefix="/live",
    tags=["live"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found."}
    },
)


@api.get(
    "/quota/{user_id}",
    response_model=LiveQuotaResp,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": (
                "One of user_id or q must be provided. "
                "If both are provided, user_id is preferred."
            )
        }
    },
)
async def get_current_quota_remaining_for_user(
    user_id: int = 0, name: Optional[str] = Body(None)
):
    remarks = []
    user, quota = None, None
    with Session() as sess:
        if user_id:  # prefer to select by id
            user = sess.scalar(User.select_by_id(user_id))
        if name and not user:  # if user hasn't been loaded, look for a name
            user = sess.scalars(User.select_by_name(name))
            if user and user_id:
                remarks.append(
                    f"Selecting user {user.name} with "
                    f"id {user.id} by name because "
                    "provided id has no record."
                )
        if not user and not (user_id or name):
            logger.debug(  # log this, as it is weird
                "get_current_quota_remaining_for_user"
                f"({user_id!r}, {name!r}): unable to load user"
            )
            raise HTTPException(  # describe error to the caller
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "One of user_id or name must be provided. "
                    "If both are provided, user_id is preferred."
                ),
            )
        if user:
            quota = user.quota
        else:
            detail = "No user could be found with "
            if item_id:
                detail += "id {user_id}"
                if name:
                    detail += f" or with "
            if name:
                detail += "name {name}"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=detail
            )
    # unfortunately, due to the nature of querying Redis, we have little
    # choice but to indulge in some code duplication.  The other routine
    # from chapps.policy.OutboundQuotaPolicy that this routine is based on
    # must be atomic, and so it cannot be factored into more than one function
    oqp = OutboundQuotaPolicy()
    response, more_remarks = oqp.current_quota(user.name, quota)
    remarks.extend(more_remarks)
    return LiveQuotaResp.send(response, remarks=remarks)
