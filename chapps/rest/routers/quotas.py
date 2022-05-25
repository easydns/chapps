"""
**Quota** record management implemented by factories
----------------------------------------------------

This module defines the API router for **Quota** record manipulation,
and defines the :class:`~.JoinAssoc` which describes the relationship between
**Quota** and **User** tables.

Implementation of **Quota** routes is a little simpler than for other models
because some functionality is intentionally excluded.  It is expected that a
large number of users might share the same **Quota** record, therefore it is
not supported to retrieve the **User** records associated with a **Quota**
object.

"""

from fastapi import APIRouter, status
from chapps.models import Quota, QuotaResp, QuotasResp, DeleteResp
from chapps.rest.routers.common import (
    get_item_by_id,
    list_items,
    create_item,
    delete_item,
    update_item,
)
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

api = APIRouter(
    prefix="/quotas",
    tags=["quotas"],
    responses={404: {"description": "Quota not found."}},
)
"""The **Quota** record management API router"""

api.get("/", response_model=QuotasResp)(
    list_items(Quota, response_model=QuotasResp)
)


api.get("/{item_id}", response_model=QuotaResp)(
    get_item_by_id(Quota, response_model=QuotaResp)
)

api.post(
    "/",
    status_code=201,
    response_model=QuotaResp,
    responses={status.HTTP_409_CONFLICT: {"description": "Unique key error."}},
)(
    create_item(
        Quota, response_model=QuotaResp, params=dict(name=str, quota=int)
    )
)

api.delete("/", response_model=DeleteResp)(delete_item(Quota))

api.put("/", response_model=QuotaResp)(
    update_item(Quota, response_model=QuotaResp)
)
