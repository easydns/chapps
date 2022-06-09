"""
**User** record management implemented by factories
---------------------------------------------------

This module defines API routes for managing **User** records, and defines the :class:`JoinAssoc` data to describe the relationship between **User** records and other record types: **Domain**, **Email**, and **Quota**.

As such, this is the only router where the factories are used to create or update records with multiple associations.  It seems a good opportunity for another example.

"""

from typing import List, Optional
from fastapi import status, APIRouter
from chapps.models import (
    User,
    Quota,
    Domain,
    Email,
    UserResp,
    UsersResp,
    DomainsResp,
    EmailsResp,
    DeleteResp,
    IntResp,
    TextResp,
    AssocOperation,
    BulkQuotaResp,
    BulkDomainsResp,
    BulkEmailsResp,
    user_quota_assoc,
    user_domains_assoc,
    user_emails_assoc,
)
from chapps.rest.routers.common import (
    get_item_by_id,
    list_items,
    create_item,
    delete_item,
    update_item,
    adjust_associations,
    list_associated,
    load_models_with_assoc,
)
import logging
import chapps.logging

logger = logging.getLogger(__name__)

api = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "User not found."}},
)
"""The API router for **User** record maintenance

This router is once again full of calls to the factories in the :mod:`~.common`
module.  The **User** model is the most connected to other things, however, and
so seems like a good spot for examples related to associations.

.. _creating-users:
.. rubric:: Creating Users

When creating a **User** record, it seems likely that the caller might like to
automatically associate the new **User** with an existing **Quota** record, and
at least one **Domain** record, perhaps even an **Email** record.  The factory
will provide a coroutine which will optionally accept ID lists for these
associations.  That is to say, the coroutine will treat them as optional
arguments and do nothing if they are not provided.

All of the logic and magic behind making this go smoothly is hidden within the
:class:`.JoinAssoc` class.  We simply provide a list of these associations to
the factory and it handles the rest:

.. code:: python

    api.post(
        "/",
        status_code=201,
        response_model=UserResp,
        responses={status.HTTP_409_CONFLICT: {"description": "Unique key error."}},
    )(create_item(User, response_model=UserResp, assoc=user_join_assoc))

In the above example, the `FastAPI`_ code for specifying details about the POST
route takes up more space than the factory call to obtain the actual **User**
creation coroutine.

The definition of :const:`.user_join_assoc` may be found below.  It is a list
containing references to all three :class:`~.JoinAssoc` instances, relating to
a **Quota** and lists of **Domain** and **Email** records.

.. _handling-associations:
.. rubric:: Handling Associations

Sometimes there is a need to remove a specific association from a list, or add
one or a handful.  It would be helpful if it were not necessary to obtain or
manufacture a list of IDs in order to use a replacement-type edit such as the
basic model update route.  The **User** model has a number of different
associations to manage, so here is an example of adding domains:

.. code:: python

    api.put("/{item_id}/domains/", response_model=TextResp)(
        adjust_associations(
            User, assoc=[user_domains_assoc], assoc_op=AssocOperation.add
        )
    )

I chose to use PUT because it is associated with partial updates.  Within the
API router wrapper, we use a call to the :func:`~.adjust_associations` route
factory, which returns a coroutine which will take a **User** ID and a list of
**Domain** IDs as arguments.  When invoked via the API, that coroutine will
ensure that all the existing **Domain** records listed are associated to the
**User**.  :exc:`~sqlalchemy.exc.IntegrityError` is ignored during the process,
so any attempts to add an existing association or to add a nonexistent
**Domain** will not raise errors -- all existing **Domain** records identified
by ID will be associated to the **User**, and other associations to that
**User** will be preserved.

"""

user_join_assoc = [user_quota_assoc, user_domains_assoc, user_emails_assoc]

load_users_with_quota = load_models_with_assoc(User, assoc=user_quota_assoc)
load_users_with_domains = load_models_with_assoc(
    User, assoc=user_domains_assoc
)
load_users_with_emails = load_models_with_assoc(User, assoc=user_emails_assoc)

api.post(
    "/",
    status_code=201,
    response_model=UserResp,
    responses={status.HTTP_409_CONFLICT: {"description": "Unique key error."}},
)(create_item(User, response_model=UserResp, assoc=user_join_assoc))


api.delete("/", response_model=DeleteResp)(delete_item(User))


api.get("/", response_model=UsersResp)(
    list_items(User, response_model=UsersResp)
)


@api.get("/quotas/", response_model=BulkQuotaResp)
async def map_usernames_to_quota_ids(user_ids: List[int]):
    """Map **User** identfiers onto **Quota** ids

    If a display requires a large matrix of users with their quota settings,
    this routine may be helpful.  The **Quota** records may be fetched before
    or after, just once for each kind of quota, and then cross-referenced much
    more efficiently than requesting each separately.

    The `response` contains a list of JSON objects (hashes or dictionaries),
    with the keys `user_name` and `quota_id`.  Only existing users are
    returned, possibly with `quota_id` set to `None` if the user has no quota
    policy assigned.  They are sorted by the user's ID value.

    """
    users_with_quotas = load_users_with_quota(user_ids)
    if not users_with_quotas:
        return BulkQuotaResp.send([], ["No listed user IDs existed."])
    uqm = [
        {"user_name": u.name, "quota_id": u.quota.id if u.quota else None}
        for u in users_with_quotas
        if u
    ]
    return BulkQuotaResp.send(uqm)


@api.get("/domains/", response_model=BulkDomainsResp)
async def map_usernames_to_domain_ids(user_ids: List[int]):
    """Map **User** identfiers onto **Domain** id lists

    If a display requires a large matrix of users with their domain authorizations,
    this routine may be helpful.  The **Domain** records may be fetched before
    or after, just once for each domain, and then cross-referenced much
    more efficiently than requesting each separately.

    The `response` contains a list of JSON objects (hashes or dictionaries),
    with the keys `user_name` and `domain_ids`.  Only existing users are
    returned, possibly with `domain_ids` set to `None` if the user has no
    domain authorizations.  They are sorted by the user's ID value.

    """
    users_with_domains = load_users_with_domains(user_ids)
    if not users_with_domains:
        return BulkDomainsResp.send([], ["No listed user IDs existed."])
    udm = [
        {"user_name": u.name, "domain_ids": [d.id for d in u.domains]}
        for u in users_with_domains
        if u
    ]
    return BulkDomainsResp.send(udm)


@api.get("/emails/", response_model=BulkEmailsResp)
async def map_usernames_to_email_ids(user_ids: List[int]):
    """Map **User** identfiers onto **Email** id lists

    If a display requires a large matrix of users with their email authorizations,
    this routine may be helpful.  The **Email** records may be fetched before
    or after, just once for each email, and then cross-referenced much
    more efficiently than requesting each separately.

    The `response` contains a list of JSON objects (hashes or dictionaries),
    with the keys `user_name` and `email_ids`.  Only existing users are
    returned, possibly with `email_ids` set to `None` if the user has no
    email authorizations.  They are sorted by the user's ID value.

    """
    users_with_emails = load_users_with_emails(user_ids)
    if not users_with_emails:
        return BulkEmailsResp.send([], ["No listed user IDs existed."])
    uem = [
        {"user_name": u.name, "email_ids": [d.id for d in u.emails]}
        for u in users_with_emails
        if u
    ]
    return BulkEmailsResp.send(uem)


api.get("/{item_id}", response_model=UserResp)(
    get_item_by_id(User, response_model=UserResp, assoc=user_join_assoc)
)

api.get("/{item_id}/domains/", response_model=DomainsResp)(
    list_associated(User, assoc=user_domains_assoc, response_model=DomainsResp)
)

api.get("/{item_id}/emails/", response_model=EmailsResp)(
    list_associated(User, assoc=user_emails_assoc, response_model=EmailsResp)
)

api.put("/", response_model=UserResp)(
    update_item(User, response_model=UserResp, assoc=user_join_assoc)
)

api.put("/{item_id}/domains/", response_model=TextResp)(
    adjust_associations(
        User, assoc=[user_domains_assoc], assoc_op=AssocOperation.add
    )
)

api.put("/{item_id}/emails/", response_model=TextResp)(
    adjust_associations(
        User, assoc=[user_emails_assoc], assoc_op=AssocOperation.add
    )
)

api.delete("/{item_id}/emails/")(
    adjust_associations(
        User, assoc=[user_emails_assoc], assoc_op=AssocOperation.subtract
    )
)


api.delete("/{item_id}/domains/", response_model=TextResp)(
    adjust_associations(
        User, assoc=[user_domains_assoc], assoc_op=AssocOperation.subtract
    )
)

# note that the correct name of the quota parameter is necessary here
api.put("/{item_id}/quota/{quota}")(
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
