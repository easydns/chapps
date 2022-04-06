"""routes for live access to CHAPPS state"""
from typing import List, Optional
from fastapi import status, APIRouter, Body, HTTPException
from .users import user_quota_assoc, user_domains_assoc
from .common import load_model_with_assoc
from ..models import User, LiveQuotaResp, TextResp
from ...policy import OutboundQuotaPolicy, SenderDomainAuthPolicy
from ...config import config
import hashlib
import logging

logger = logging.getLogger(__name__)

api = APIRouter(
    prefix="/live",
    tags=["live"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found."},
        status.HTTP_400_BAD_REQUEST: {
            "description": (
                "One of either user_id of name must be provided. "
                "If both are present, user_id is preferred"
            )
        },
    },
)

# define some useful functions
load_user_with_quota = load_model_with_assoc(User, assoc=[user_quota_assoc])


@api.get("/quota/remaining/{user_id}", response_model=LiveQuotaResp)
async def get_current_quota_remaining_for_user(
    user_id: int = 0, name: Optional[str] = Body(None)
):
    user, assoc_d, remarks = load_user_with_quota(user_id, name)
    quota = assoc_d[user_quota_assoc.assoc_name]
    oqp = OutboundQuotaPolicy()
    response, more_remarks = oqp.current_quota(user.name, quota)
    return LiveQuotaResp.send(response, remarks=remarks + more_remarks)


@api.post("/quota/reset/{user_id}", response_model=LiveQuotaResp)
async def reset_live_quota_for_user(
    user_id: int = 0, name: Optional[str] = Body(None)
):
    user, assoc_d, remarks = load_user_with_quota(user_id, name)
    quota = assoc_d[user_quota_assoc.assoc_name]
    oqp = OutboundQuotaPolicy()
    response, more_remarks = oqp.reset_quota(user.name)
    if not quota:
        remarks.append(f"User {user.name} has no assigned quota.")
    logger.info(" ".join(more_remarks))  # log only reset message
    return LiveQuotaResp.send(response, remarks=remarks + more_remarks)


@api.post("/quota/refresh/{user_id}", response_model=LiveQuotaResp)
async def refresh_quota_policy_for_user(
    user_id: int = 0, name: Optional[str] = Body(None)
):
    """
    Returns the new remaining quota after the policy update as the
    numerical response.
    """
    user, assoc_d, remarks = load_user_with_quota(user_id, name)
    quota = assoc_d[user_quota_assoc.assoc_name]
    oqp = OutboundQuotaPolicy()
    if not quota:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cannot load quota for user {user.name}: none assigned.",
        )
    remarks.append(f"Quota policy config cache reset for {user.name}")
    response, more_remarks = oqp.refresh_policy_cache(user.name, quota)
    return LiveQuotaResp.send(response, remarks=remarks + more_remarks)


@api.post(
    "/config/write/",
    response_model=TextResp,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Password does not match."
        }
    },
)
async def refresh_config_on_disk(passcode: str = Body(...)):
    """
    Writes the current effective config to disk.
    Requires the CHAPPS password to be provided.
    If line transmission security is an issue, an SSL proxy layer will
      be required.  This is true for the entire application.
    """
    if (
        hashlib.sha256(
            passcode.encode(config.chapps.payload_encoding)
        ).hexdigest()
        == config.chapps.password
    ):
        response = config.write()
        return TextResp.send(str(response))
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Password does not match.",
    )


@api.get("/sda/{domain_name}/for/{user_name}", response_model=TextResp)
async def sda_peek(domain_name: str, user_name: str):
    """
    Returns status of cached SDA for the named user and domain,
    i.e. is this user allowed to transmit email apparently from this domain
    """
    sda = SenderDomainAuthPolicy()
    return TextResp.send(sda.check_policy_cache(user_name, domain_name))
