"""routes for live access to CHAPPS state"""
from typing import List, Optional
from fastapi import status, APIRouter, Body, HTTPException
from sqlalchemy.orm import sessionmaker
from .users import user_quota_assoc, user_domains_assoc
from .common import load_model_with_assoc
from ..dbsession import sql_engine
from ..models import User, Domain, LiveQuotaResp, TextResp, DomainUserMapResp
from ...policy import OutboundQuotaPolicy, SenderDomainAuthPolicy
from ...config import config
import hashlib
import logging

logger = logging.getLogger(__name__)
Session = sessionmaker(sql_engine)

api = APIRouter(
    prefix="/live",
    tags=["live"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Resource not found."},
        status.HTTP_400_BAD_REQUEST: {
            "description": (
                "One of either user_id or name must be provided. "
                "If both are present, user_id is preferred"
            )
        },
    },
)

# define some useful functions
load_user_with_quota = load_model_with_assoc(User, assoc=[user_quota_assoc])


@api.get("/quota/{user_id}", response_model=LiveQuotaResp)
async def get_current_quota_remaining_for_user(
    user_id: int = 0, name: Optional[str] = Body(None)
):
    """
    Accepts the id of the user whose remaining quota should be checked.<br/>
    Returns the instantaneous number of available send attempts in
    `response`
    """
    user, assoc_d, remarks = load_user_with_quota(user_id, name)
    quota = assoc_d[user_quota_assoc.assoc_name]
    oqp = OutboundQuotaPolicy()
    response, more_remarks = oqp.current_quota(user.name, quota)
    return LiveQuotaResp.send(response, remarks=remarks + more_remarks)


@api.delete("/quota/{user_id}", response_model=LiveQuotaResp)
async def reset_live_quota_for_user(
    user_id: int = 0, name: Optional[str] = Body(None)
):
    """
    Accepts the id of the user whose quota should be reset.<br/>
    Returns the number of send attempts dropped in `response`
    """
    user, assoc_d, remarks = load_user_with_quota(user_id, name)
    quota = assoc_d[user_quota_assoc.assoc_name]
    oqp = OutboundQuotaPolicy()
    response, more_remarks = oqp.reset_quota(user.name)
    if not quota:
        remarks.append(f"User {user.name} has no assigned quota.")
    logger.info(" ".join(more_remarks))  # log only reset message
    return LiveQuotaResp.send(response, remarks=remarks + more_remarks)


@api.post("/quota/{user_id}", response_model=LiveQuotaResp)
async def refresh_quota_policy_for_user(
    user_id: int = 0, name: Optional[str] = Body(None)
):
    """
    Accepts the id of the user whose quota policy should be refreshed.<br/>
    Returns the new remaining quota after the policy update in `response`
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
    Writes the current effective config to disk.<br/>
    Requires the CHAPPS password to be provided as the body.<br/>
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


@api.get("/sda/", response_model=DomainUserMapResp)
async def sda_batch_peek(domain_ids: List[int], user_ids: List[int]):
    """
    Accepts `domain_ids` and `user_ids` as body arguments: lists of
    integer object ids.<br/>
    Looks at current authorizations for all domain-user combinations.<br/>
    Returns their cache status as a dict of dicts, keyed as:
    `sda[domain][user] = SDAStatus`
    """
    sda = SenderDomainAuthPolicy()
    with Session() as sess:
        domain_names = list(
            sess.scalars(Domain.select_names_by_id(domain_ids))
        )
        user_names = list(sess.scalars(User.select_names_by_id(user_ids)))
    return DomainUserMapResp.send(
        sda.bulk_check_policy_cache(user_names, domain_names)
    )


@api.get("/sda/{domain_name}/for/{user_name}", response_model=TextResp)
async def sda_peek(domain_name: str, user_name: str):
    """
    Accepts url-encoded domain name and user name as path arguments.<br/>
    Returns status of cached SDA for the named user and domain,
    i.e. is this user allowed to transmit email apparently from this domain
    """
    sda = SenderDomainAuthPolicy()
    result = sda.check_policy_cache(user_name, domain_name)
    # logger.debug(f"Peeking at {domain_name} auth for {user_name}: {result!r}")
    return TextResp.send(result)


@api.delete("/sda/", response_model=TextResp)
async def sda_batch_clear(domain_ids: List[int], user_ids: List[int]):
    """
    Clears all domain - user mappings by iterating through both lists.
    """
    sda = SenderDomainAuthPolicy()
    with Session() as sess:
        domain_names = list(
            sess.scalars(Domain.select_names_by_id(domain_ids))
        )
        user_names = list(sess.scalars(User.select_names_by_id(user_ids)))
    sda.bulk_clear_policy_cache(user_names, domain_names)
    return TextResp.send("SDA cache cleared for specified domains x users.")


@api.delete("/sda/{domain_name}/for/{user_name}", response_model=TextResp)
async def sda_clear(domain_name: str, user_name: str):
    """
    Accepts url-encoded domain name and user name of SDA to clear.</br>
    Returns the status of the SDA prior to clearing.
    """
    sda = SenderDomainAuthPolicy()
    return TextResp.send(sda.clear_policy_cache(user_name, domain_name))
