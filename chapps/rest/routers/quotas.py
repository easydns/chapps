from fastapi import APIRouter, status
from chapps.rest.models import Quota, QuotaResp, QuotasResp
from .common import get_item_by_id, list_items, create_item
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

api = APIRouter(
    prefix="/quotas",
    tags=["quotas"],
    responses={404: {"description": "Quota not found."}},
)


api.get("/", response_model=QuotasResp)(list_items(Quota, response_model=QuotasResp))


api.get("/{item_id}", response_model=QuotaResp)(
    get_item_by_id(Quota, response_model=QuotaResp)
)

api.post(
    "/",
    status_code=201,
    response_model=QuotaResp,
    responses={status.HTTP_400_BAD_REQUEST: {"description": "Unique key error."}},
)(create_item(Quota, response_model=QuotaResp, params=dict(name=str, quota=int)))

logger.debug("Created Quota::create_i")
# @api.post("/")
# async def create_quota(name: str=Body(...), limit: int=Body(...)):
