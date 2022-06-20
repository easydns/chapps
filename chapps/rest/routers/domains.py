"""
**Domain** record management implemented by factories
-----------------------------------------------------

This module defines the various routes for manipulating **Domain** records.  It
also defines the :class:`~.dbmodels.JoinAssoc` between **Domain** and **User**
tables.

Normally, each API route would be a decorated function or coroutine definition.
However, in this case, all the routes are created by factories from
:mod:`.common`.  This makes it impossible to attach docstrings.

In order to provide basic documentation and some examples how to use those
:mod:`~.common` API route coroutine factories, the routes will be described
below, as part of the `.api` docstring.

"""
from typing import List
from starlette import status
from fastapi import APIRouter  # , Body, Path, HTTPException
from chapps.models import (
    User,
    Domain,
    DomainResp,
    DomainsResp,
    UsersResp,
    DeleteResp,
    TextResp,
    AssocOperation,
    domain_users_assoc,
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
    prefix="/domains",
    tags=["domains"],
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Domain not found."}
    },
)
"""`FastAPI`_ :class:`~fastapi.APIRouter` object for domains

I will include a few examples here, rather than copy in all of the code.  It
seems important to provide and annotate at least a few examples in order to
ensure that others, or my later self, will understand how this is all intended
to work.

First, a simple example: the listing route.  **Domain** objects, like just
about any object represented this way, need to be listable by API so that they
can be viewed by a user before being modified, linked to other objects,
queried, destroyed, etc.  In :mod:`chapps.rest.routers.common`, coroutine
factories are defined to create all of these API routes.

.. _listing-domains:
.. rubric:: Listing Domains

Normally this would look like the route definitions in the
:mod:`~.live` module, a decorated coroutine definition.  Something like this:

.. code:: python

  @api.get("/", response_model=DomainsResp)
  async def list_domains(
    item_id: int, qparams: dict = Depends(list_query_params)
  ):
      ... some code ...
      return DomainsResp.send(response, [...])

Instead, we invoke the decorator directly as a function.  As a
decorator-with-arguments, its return value is a closure which is the actual
decorator.  That real decorator expects our route function or coroutine as an
argument.  A factory from :mod:`~.common` is used to create that route
coroutine.

Therefore, the actual route is created on the `APIRouter` like so:

.. code:: python

  api.get("/", response_model=DomainsResp)(
       list_items(Domain, response_model=DomainsResp)
  )

Please note that the main data model class is provided.  All of the routes in
this module regard **Domain** as the main data model.  Because this route is
for listing objects/records, it uses a response type which includes a list.

What about a route which makes changes, especially one which is sensitive to the model's associations to other models?  Things become a little bit more complicated, but not by much.

.. _updating-domains:
.. rubric:: Updating Domains

To update a **Domain**, we need to receive the data within a **Domain** object,
plus optionally a list of **User** IDs, to associate with the **Domain**
instead of whatever is currently associated with the **Domain**.

.. code:: python

  api.put("/", response_model=DomainResp)(
      update_item(Domain, response_model=DomainResp, assoc=domain_join_assoc)
  )

In order to specify the associations to support in the route, a list of
:class:`~.JoinAssoc` objects may be provided to the `assoc` parameter.

.. todo::

  There is a further opportunity for automation through metaprogramming, to set
  up all the expected, basic routes for a given data model in a single function
  call.

(The following parameters and return type correspond to the :class:`~fastapi.APIRouter` instance, which is callable.  Sphinx autodoc makes it quite difficult to suppress this output.)

"""

domain_join_assoc = [domain_users_assoc]
"""Join association list for **Domain** objects"""

api.get("/", response_model=DomainsResp)(
    list_items(Domain, response_model=DomainsResp)
)

api.get("/{item_id}", response_model=DomainResp)(
    get_item_by_id(Domain, response_model=DomainResp, assoc=domain_join_assoc)
)

api.get("/{item_id}/users/", response_model=UsersResp)(
    list_associated(Domain, assoc=domain_users_assoc, response_model=UsersResp)
)

api.post(
    "/",
    status_code=201,
    response_model=DomainResp,
    responses={status.HTTP_409_CONFLICT: {"description": "Unique key error."}},
)(
    create_item(
        Domain,
        response_model=DomainResp,
        params=dict(name=str, greylist=bool, check_spf=bool),
        assoc=domain_join_assoc,
    )
)

api.put("/", response_model=DomainResp)(
    update_item(Domain, response_model=DomainResp, assoc=domain_join_assoc)
)

api.put("/{item_id}/users/", response_model=TextResp)(
    adjust_associations(
        Domain, assoc=domain_join_assoc, assoc_op=AssocOperation.add
    )
)

api.delete("/{item_id}/users/", response_model=TextResp)(
    adjust_associations(
        Domain, assoc=domain_join_assoc, assoc_op=AssocOperation.subtract
    )
)

api.delete(
    "/",
    response_model=DeleteResp,
    responses={
        status.HTTP_202_ACCEPTED: {"description": "Items will be deleted."},
        status.HTTP_409_CONFLICT: {
            "description": "Database integrity conflict."
        },
    },
)(delete_item(Domain))
