"""
Route factories and other reusable code
---------------------------------------

Factories for utility functions and API routes
are defined in this module
along with some `FastAPI`_ dependencies.

The route factories perform the repetitive grunt work required to set up the
typical 'create', 'read', 'update', 'delete' and 'list' functions needed for
basic object management.  In order to avoid extra levels of metaprogramming,
the parameter name for the record ID of the main object involved in a
factory-generated API call is ``item_id``, since it is clear, brief and
generic.  Apologies to future subclassors who want an 'items' table.

These route factories are used to create all the routes for
:mod:`~chapps.rest.routers.users`, :mod:`~chapps.rest.routers.emails`,
:mod:`~chapps.rest.routers.domains`, and :mod:`~chapps.rest.routers.quotas`.

"""
from typing import Optional, List
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from fastapi import status, Depends, Body, HTTPException
from functools import wraps
import inspect
import logging
from chapps.dbsession import sql_engine
from chapps.models import (
    CHAPPSModel,
    CHAPPSResponse,
    AssocOperation,
    DeleteResp,
    TextResp,
)
from chapps.dbmodels import JoinAssoc
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)


async def list_query_params(
    skip: Optional[int] = 0,
    limit: Optional[int] = 1000,
    q: Optional[str] = "%",
) -> dict:
    """FastAPI dependency for list queries"""
    return dict(q=q, skip=skip, limit=limit)


def model_name(cls) -> str:
    """Convenience function to get the lowercase name of a model"""
    return cls.__name__.lower()


def load_model_with_assoc(cls, assoc: List[JoinAssoc], engine=sql_engine):
    """Create a closure which loads an object along with arbitrary associations

    This isn't meant to create an API route on its own, but it may be used in
    API routes.  It is mainly used in :mod:`~chapps.rest.routers.live` routes,
    which are currently all one-offs, not created by factories.  In order to
    return a closure which can work in any context, it does not return a
    coroutine but a standard synchronous closure.

    :param ~.CHAPPSModel cls: a data model class
    :param assoc: a list of associations (as
      :class:`~.JoinAssoc` objects)
    :param Optional[~sqlalchemy.engine.Engine] engine: defaults to
      :const:`chapps.dbsession.sql_engine` if not specified
    :rtype: callable
    :returns: a closure as follows:

      .. py:function:: f(item_id: int, name: Optional[str])

        :param int item_id: if non-zero, the ID of the main record
        :param Optional[str] name: if `item_id` is 0, the `name` of the record
          to match.
        :rtype: Tuple[~.CHAPPSModel, Dict[str, List[~.CHAPPSModel]], List[str]]
        :returns: a :obj:`tuple` containing:

          1. the object loaded by ID or name

          2. that object's associations in a :obj:`dict` keyed on attribute
             name (e.g. 'quota', 'domains')

          3. a list of string remarks, which may have no contents

    """
    mname = model_name(cls)
    assoc_s = "_".join([a.assoc_name for a in assoc])
    fname = f"load_{mname}_with_{assoc_s}"
    # Session = sessionmaker(engine)

    @db_wrapper(cls=cls, engine=engine)
    def get_model_and_assoc(item_id: int, name: Optional[str]):
        remarks = []
        items = {k: None for k in [mname, *[a.assoc_name for a in assoc]]}
        # session is a global provided by the decorator
        if item_id:
            items[mname] = session.scalar(cls.select_by_id(item_id))
        if name and not items[mname]:
            items[mname] = session.scalar(cls.select_by_name(name))
            if items[mname] and item_id:
                remarks.append(
                    f"Selecting {mname} {items[mname].name} with "
                    f"id {items[mname].id} by name because "
                    "provided id does not exist."
                )
        if not items[mname] and not (item_id or name):
            logger.debug(  # log this, as it is weird
                f"{fname}({item_id!r}, {name!r}): unable to load {mname}"
            )
            raise HTTPException(  # describe error to the caller
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"One of {cls.id_name()} or name must be provided. "
                    "If both are provided, {cls.id_name()} is preferred."
                ),
            )
        if items[mname]:
            for a in assoc:
                items[a.assoc_name] = getattr(items[mname], a.assoc_name)
        else:
            detail = "No {mname} could be found with "
            if item_id:
                detail += "id {item_id}"
                if name:
                    detail += f" or with "
            if name:
                detail += "name {name}"
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=detail
            )
        return (items.pop(mname), items, remarks)

    get_model_and_assoc.__name__ = fname
    return get_model_and_assoc


def load_models_with_assoc(
    cls: CHAPPSModel, *, assoc: JoinAssoc, engine=sql_engine
) -> callable:
    """Build a map of source name => associated object id

    :param cls: source model

    :param assoc: a join association representing the associated model

    :param engine: override the SQLA engine if desired

    :returns: a mapper function which accepts a list of IDs of the source model
      and returns a list of dicts with `<source_model>_name` and
      `<assoc_model>_id` fields, mapping the source objects onto the IDs of
      their associated objects of the configured type.

    .. todo::

      Employ eager loading on the target association.

    """
    mname = model_name(cls)
    fname = f"eager_load_{mname}_with_{assoc.assoc_name}"
    # Session = sessionmaker(engine)

    @db_wrapper(cls=cls, engine=engine)
    def map_model_names_to_assoc(
        item_ids: List[int],  # name_tail: Optional[str] = None
    ):
        eager_loaded_models = session.scalars(
            cls.select_by_ids(
                item_ids, getattr(cls.Meta.orm_model, assoc.assoc_name)
            )
        )
        return list(eager_loaded_models)

    map_model_names_to_assoc.__name__ = fname
    return map_model_names_to_assoc


def db_wrapper(  # a decorator with parameters
    *,
    cls,
    engine=sql_engine,
    exception_message: str = ("{route_name}:{model}"),
    empty_set_message: str = ("Unable to find a matching {model}"),
):
    """Decorator for database interactions

    :param ~chapps.models.CHAPPSModel cls: the data model class

    :param ~sqlalchemy.engine.Engine engine: an :mod:`SQLAlchemy` engine, which
      defaults to the package-wide one declared in
      :mod:`~chapps.dbsession`

    :param str exception_message: a message to include if any untrapped
      exception occurs; defaults to ``{route_name}:{model}``.  Only those two
      symbols are available for expansion.  All arguments are appended.

    :param str empty_set_message: included if a SELECT results in an empty set;
      defaults to ``Unable to find a matching {model}`` and supports both
      substitutions that `exception_message` does

    :returns: a `decorator`_ closure, which will be called with the function to
      be `decorated`_ as its argument.  This is a regular callable decorator.

    :rtype: callable which wraps and returns a function

    The decorator sets up some global symbols for use inside the DB access function:

      :session: a :class:`~sqlalchemy.orm.Session` instance created in a
        context containing the execution of the wrapped coroutine, suitable for
        performing database interactions, and which will be automatically
        closed after the coroutine completes

      :model_name: a string containing the lowercase name of the model

    .. _decorator: https://docs.python.org/3/glossary.html#term-decorator
    .. _decorated: https://peps.python.org/pep-0318/
    .. _coroutine: https://docs.python.org/3/library/asyncio-task.html#coroutines

    """

    mname = model_name(cls)
    Session = sessionmaker(engine)

    def db_func_wrapper(db_func):
        exc = exception_message.format(
            route_name=db_func.__name__, model=mname
        )
        empty = empty_set_message.format(
            route_name=db_func.__name__, model=mname
        )

        @wraps(db_func)
        def wrapped_interaction(*args, **kwargs):
            with Session() as session:
                db_func.__globals__["session"] = session
                db_func.__globals__["model_name"] = mname

                try:
                    result = db_func(*args, **kwargs)
                    if result:
                        return result
                except HTTPException as e:
                    raise e
                except Exception:
                    logger.exception(exc + f"({args!r},{kwargs!r})")
            raise HTTPException(status_code=404, detail=empty)

        wrapped_interaction.__doc__ = db_func.__doc__
        return wrapped_interaction  # a regular function

    return db_func_wrapper  # a regular function


def db_interaction(  # a decorator with parameters
    *,
    cls,
    engine=sql_engine,
    exception_message: str = ("{route_name}:{model}"),
    empty_set_message: str = ("Unable to find a matching {model}"),
):
    """Decorator for database interactions

    :param ~chapps.models.CHAPPSModel cls: the data model class

    :param ~sqlalchemy.engine.Engine engine: an :mod:`SQLAlchemy` engine, which
      defaults to the package-wide one declared in
      :mod:`~chapps.dbsession`

    :param str exception_message: a message to include if any untrapped
      exception occurs; defaults to ``{route_name}:{model}``.  Only those two
      symbols are available for expansion.  All arguments are appended.

    :param str empty_set_message: included if a SELECT results in an empty set;
      defaults to ``Unable to find a matching {model}`` and supports both
      substitutions that `exception_message` does

    :returns: a `decorator`_ closure, which will be called with the function to
      be `decorated`_ as its argument.  In this case, the function is expected
      to be a coroutine which is being manufactured for use in the API, and so
      the decorator closure returned by this routine defines a `coroutine`_ to
      wrap and await its argument, which is ultimately returned and used as the
      API route.

    :rtype: callable which wraps and returns a coroutine

    The decorator sets up some global symbols for use inside the API route
    coroutines:

      :session: a :class:`~sqlalchemy.orm.Session` instance created in a
        context containing the execution of the wrapped coroutine, suitable for
        performing database interactions, and which will be automatically
        closed after the coroutine completes

      :model_name: a string containing the lowercase name of the model

    .. _decorator: https://docs.python.org/3/glossary.html#term-decorator
    .. _decorated: https://peps.python.org/pep-0318/
    .. _coroutine: https://docs.python.org/3/library/asyncio-task.html#coroutines

    """

    mname = model_name(cls)
    Session = sessionmaker(engine)

    def interaction_wrapper(rt_coro):
        exc = exception_message.format(
            route_name=rt_coro.__name__, model=mname
        )
        empty = empty_set_message.format(
            route_name=rt_coro.__name__, model=mname
        )

        @wraps(rt_coro)
        async def wrapped_interaction(*args, **kwargs):
            with Session() as session:
                rt_coro.__globals__["session"] = session
                rt_coro.__globals__["model_name"] = mname

                try:
                    result = await rt_coro(*args, **kwargs)
                    if result:
                        return result
                except HTTPException as e:
                    raise e
                except Exception:
                    logger.exception(exc + f"({args!r},{kwargs!r})")
            raise HTTPException(status_code=404, detail=empty)

        wrapped_interaction.__doc__ = rt_coro.__doc__
        return wrapped_interaction  # a coroutine

    return interaction_wrapper  # a regular function


def get_item_by_id(
    cls,
    *,
    response_model,
    engine=sql_engine,
    assoc: Optional[List[JoinAssoc]] = None,
):
    """Build a route coroutine to get an item by ID

    :param ~chapps.models.CHAPPSModel cls: the main data model for the request

    :param ~chapps.models.CHAPPSResponse response_model: the response
      model

    :param ~sqlalchemy.engine.Engine engine: defaults to
      :const:`~chapps.dbsession.sql_engine`

    :param List[~chapps.rest.dbmodels.JoinAssoc] assoc: if included, these
      associations will be included as optional keys in the response

    At present there is no provision for dealing with extremely long
    association lists.  Even if there were 500 elements, the response would not
    be extremely large.

    .. note::

      An alternate closure factory for creating routes which
      specifically list associations does provide pagination, etc.  See
      :func:`~.list_associated`

    The factory produces a coroutine decorated with the
    :func:`~.db_interaction` decorator, as do all the route factories.  Its
    signature is:

      .. code:: python

        async def get_i(item_id: int) -> response_model

    The factory sets the final closure's name and doc metadata properly to
    ensure that the automatic documentation is coherent and accurate.  All the
    route factories do this to a greater or lesser extent.

    .. todo::

      provide option for API user to suppress each association
      perhaps something like `no_list_domains` as part of the query params

    """
    mname = model_name(cls)

    @db_interaction(cls=cls, engine=engine)
    async def get_i(item_id: int):
        stmt = cls.select_by_id(item_id)
        item = session.scalar(stmt)
        if item:
            if assoc:
                extra_args = {
                    a.assoc_name: a.assoc_model.wrap(
                        getattr(item, a.assoc_name)
                    )
                    for a in assoc
                }
                return response_model.send(cls.wrap(item), **extra_args)
            else:
                return response_model.send(cls.wrap(item))

    get_i.__name__ = f"get_{model_name(cls)}"
    get_i.__doc__ = (
        f"Retrieve **{mname}** records by ID, "
        "along with all (up to 1000) associated records."
    )
    return get_i


def list_items(cls, *, response_model, engine=sql_engine):
    """Build a route coroutine to list items

    :param ~chapps.models.CHAPPSModel cls: the main data model for the
      request

    :param ~chapps.models.CHAPPSResponse response_model: the response
      model

    :param ~sqlalchemy.engine.Engine engine: defaults to
      :const:`~chapps.dbsession.sql_engine`

    The returned closure expects to receive the query parameters as a dict,
    since that is what the dependency will return.  Its signature is

      .. code:: python

        async def list_i(qparams: dict = Depends(list_query_params))

    The closure's name and document metadata are updated to ensure coherence
    and accuracy of the automatic API documentation.

    For an example of using this factory, see :ref:`Listing Domains
    <listing-domains>`.

    """
    mname = model_name(cls)

    @db_interaction(cls=cls, engine=engine)
    async def list_i(qparams: dict = Depends(list_query_params)):
        stmt = cls.windowed_list(**qparams)
        items = cls.wrap(session.scalars(stmt))
        if items:
            return response_model.send(items)

    list_i.__name__ = f"list_{model_name(cls)}"
    list_i.__doc__ = f"""
        List **{mname}** records.<br/>
        Pass a substring to match as `q`.<br/>
        Paginate by providing `skip` and `limit`.
        """
    return list_i


def list_associated(
    cls: CHAPPSModel,
    *,
    assoc: JoinAssoc,
    response_model: CHAPPSResponse,
    engine=sql_engine,
):
    """Build a route to list associated items with pagination

    :param cls: the main data model

    :param assoc: the association to list

    :param response_model: the response model

    :param sqlalchemy.engine.Engine engine: defaults to
      :const:`~chapps.dbsession.sql_engine`

    The returned coroutine will paginate a list of the associated objects,
    given the ID of a main (source) object to use to select associations.  The
    `qparams` parameter is a bundle of standard listing query parameters
    defined by :func:`.list_query_params` via the :class:`fastapi.Depends`
    mechanism.

      .. code:: python

        async def assoc_list(item_id: int, qparams: dict) -> response_model

    It returns in the `response` key of its output a list of
    the associated object, goverened by the search and window parameters in
    `qparams`.

    """
    mname = model_name(cls)
    fname = f"{mname}_list_{assoc.assoc_name}"

    @db_interaction(cls=cls, engine=engine)
    async def assoc_list(
        item_id: int, qparams: dict = Depends(list_query_params)
    ):
        stmt = assoc.assoc_model.windowed_list_by_ids(
            subquery=assoc.select_ids_by_source_id(item_id), **qparams
        )
        assocs = assoc.assoc_model.wrap(session.scalars(stmt))
        if assocs:
            return response_model.send(assocs)

    assoc_list.__name__ = fname
    assoc_list.__doc__ = (
        f"List **{assoc.assoc_name}** associated with a particular **{mname}**,"
        " identified by ID.<br/>Supply standard query parameters for matching and"
        " pagination."
    )
    return assoc_list


def delete_item(cls, *, response_model=DeleteResp, engine=sql_engine):
    """Build a route coroutine to delete an item by ID

    :param ~chapps.models.CHAPPSModel cls: the data model to manage

    :param ~chapps.models.CHAPPSResponse response_model: defaults to :class:`~chapps.models.DeleteResp`

    :param ~sqlalchemy.engine.Engine engine: defaults to :const:`~chapps.dbsession.sql_engine`

    The returned coroutine accepts a list of record IDs for the specified
    object type and delete them.  Its signature is:

      .. code:: python

        async def delete_i(item_ids: List[int]) -> DeleteResp

    """
    mname = model_name(cls)

    @db_interaction(cls=cls, engine=engine)
    async def delete_i(item_ids: List[int]):
        try:
            session.execute(cls.remove_by_id(item_ids))
            session.commit()
        except IntegrityError:
            logger.exception("trying to delete {mname} with {args!r}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Database integrity conflict.",
            )
        return response_model.send()

    delete_i.__name__ = f"delete_{mname}"
    delete_i.__doc__ = f"""
        Accepts a list of **{mname}** object IDs.
        Deletes the records with those IDs."""
    return delete_i


def adjust_associations(
    cls,
    *,
    assoc: List[JoinAssoc],
    assoc_op: AssocOperation,
    params: dict = None,
    response_model=TextResp,
    engine=sql_engine,
):
    """Build a route to add or subtract association lists, or set unitary ones

    :param ~chapps.models.CHAPPSModel cls: a data model class

    :param List[~chapps.rest.dbmodels.JoinAssoc] assoc: list of associations to
      operate on

    :param ~chapps.models.AssocOperation assoc_op: operation to perform on
      the association

    :param ~chapps.models.CHAPPSResponse response_model: the response
      model to send

    :param ~sqlalchemy.engine.Engine engine: defaults to
      :const:`~chapps.dbsession.sql_engine`

    The returned coroutine provides logic for a route which adds or subtracts
    elements to or from those already associated with the main object.  Its
    exact signature is dependent on what associations are listed.  After
    `item_id`, which is an ID to use to look up the main object, it will expect
    further arguments named as the association (`assoc_name`) which are of the
    specified type (`assoc_type`).

    If only one association is adjusted by the route, there will be just the
    one list (or scalar) as a body argument, which doesn't get a label, making
    the API call very easy to format and looking very clean in the API docs.
    If more than one are specified, :mod:`FastAPI` will expect a JSON object in
    the body with keys named as the ID columns and values which are lists of
    IDs.

    It all seems quite complicated when stated this way, but when viewed in the
    API documentation, it makes much more sense.

    For an example of using this factory, see :ref:`Handling Associations
    <handling-associations>`

    """

    mname = model_name(cls)
    assoc_s = "_".join([a.assoc_name for a in assoc])
    fname = f"{mname}_{assoc_op}_{assoc_s}"
    params = params or dict(item_id=int)
    assoc_params = {a.assoc_name: a.assoc_type for a in assoc}

    @db_interaction(cls=cls, engine=engine)
    async def assoc_op_i(*pargs, **args):
        # item_id will be used for the source object, and assoc_names will
        # be a list of associated ids to either remove or add associations
        # for, ignoring integrity errors arising from attempting to insert
        # duplicate associations; non-existent associations should not cause
        # errors when a query attempts to delete them.
        extras = {
            a.assoc_name: (a, args.pop(a.assoc_name))
            for a in assoc
            if a.assoc_name in args
        }
        item_id = args["item_id"]
        if extras:
            for assoc_name, (assc, vals) in extras.items():
                if not vals:
                    continue
                if assoc_op == AssocOperation.add:
                    stmt = assc.insert_assoc(item_id, vals)
                elif assoc_op == AssocOperation.replace:
                    stmt = assc.update_assoc(item_id, vals)
                else:
                    stmt = assc.delete_assoc(item_id, vals)
                try:
                    session.execute(stmt)
                except IntegrityError:
                    pass  # ignoring as stated above
            session.commit()
            return response_model.send("Updated.")
        return response_model.send("Empty request.")

    # this approach may seem laborious, but it supports multicolumn prikeys
    routeparams = [
        inspect.Parameter(
            name=param,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=type_,
        )
        for param, type_ in params.items()
    ]
    routeparams.extend(
        [
            inspect.Parameter(
                name=param,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=type_,
            )
            for param, type_ in assoc_params.items()
        ]
    )
    assoc_op_i.__signature__ = inspect.Signature(routeparams)
    assoc_op_i.__annotations__ = params
    assoc_op_i.__name__ = fname
    assoc_op_i.__doc__ = f"""
        {str(assoc_op).capitalize()}
        **{', '.join([a.assoc_name for a in assoc])}** objects
        {'to' if assoc_op==AssocOperation.add else 'from'} **{mname}**<br/>
        Accepts **{mname}** ID as `item_id`.
    """

    return assoc_op_i


def update_item(
    cls, *, response_model, assoc: List[JoinAssoc] = None, engine=sql_engine
):
    """Build a route to update items.

    :param ~chapps.models.CHAPPSModel cls: the main data model

    :param ~chapps.models.CHAPPSResponse response_model: the response
      model

    :param ~chapps.rest.dbmodels.JoinAssoc assoc: the association to list

    :param ~sqlalchemy.engine.Engine engine: defaults to
      :const:`~chapps.dbsession.sql_engine`

    The returned coroutine implements an API route for updating an item by ID,
    optionally including any associations included when the route coroutine is
    built.  If association data is provided to the route, it will completely
    replace any existing associations to that type of record with the new list
    of IDs.

    Its signature is determined by the contents of the
    :class:`~chapps.rest.dbmodels.JoinAssoc` passed to it.  The factory
    constructs :mod:`~inspect.Parameter` elements and uses them to create a
    correct :mod:`~inspect.Signature` for the new, decorated closure.  It also
    sets the `__doc__` and `__name__` metadata so that `FastAPI`_ will be able
    to find all the required data to create an API route with good
    documentation.

    For an example of how to use this factory, see :ref:`Updating Domains
    <updating-domains>`

    .. todo::

      in a generalized version of this for wider use in gluing `SQLAlchemy`_ to
      `FastAPI`_, it would need to allow arbitrary attributes of the model to
      be optional/required/defaulted.  This might easily be achieved through
      the use of an additional alternate Pydantic_ data model for updates,
      wherein those elements which ought to be optional may be marked as such.

    """
    mname = model_name(cls)
    fname = f"update_{mname}"
    params = {mname: cls}  # we are updating objects of this type

    @db_interaction(cls=cls, engine=engine)
    async def update_i(*pargs, **args):
        extras = {}
        assoc_ret = {}
        if assoc:
            extras = {
                a.assoc_name: (a, args.pop(a.assoc_name))
                for a in assoc
                if a.assoc_name in args
            }
        item_id = args[mname].id
        stmt = cls.update_by_id(args[mname])
        try:
            result = session.execute(stmt)
            if result.rowcount > 0:  # commit if changes were made
                session.commit()
            else:  # return None if there is no record to update -> 404
                return
        except Exception:
            logger.exception(f"{fname}: {args!r}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        item = session.scalar(cls.select_by_id(item_id))
        if extras:
            for assoc_name, (assc, vals) in extras.items():
                if not vals:
                    continue
                try:
                    session.execute(
                        assc.delete().where(
                            getattr(assc.table.c, assc.source_id) == item_id
                        )
                    )
                    session.execute(assc.insert(), assc.values(item, vals))
                    session.commit()
                    assoc_ret[assoc_name] = assc.assoc_model.wrap(
                        getattr(item, assoc_name)
                    )
                except IntegrityError:
                    logger.exception(
                        f"{fname}: associating {item} with"
                        f" {assoc_name}s {vals!r}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Unable to create requested association to"
                            f"{assc.assoc_model.__name__.lower()} entries."
                            "  Please check object ids and try again."
                        ),
                    )
        return response_model.send(cls.wrap(item), **assoc_ret)

    routeparams = [
        inspect.Parameter(
            name=param,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=Body(...),
            annotation=type_,
        )
        for param, type_ in params.items()
    ]
    if assoc:
        routeparams.extend(
            [
                inspect.Parameter(
                    name=a.assoc_name,
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=Body(None),
                    annotation=a.assoc_type,
                )
                for a in assoc
            ]
        )
    update_i.__signature__ = inspect.Signature(routeparams)
    update_i.__annotations__ = params
    update_i.__name__ = fname
    update_i.__doc__ = f"""
        Update a **{mname}** record by ID.<br/>
        All **{mname}** attributes are required.<br/>
        Associations are not required, but if provided (by ID), will
        completely replace any existing association relationships
        of the same type.
        """
    return update_i


def create_item(
    cls, *, response_model, params=None, assoc=None, engine=sql_engine
):
    """Build a route coroutine to create new item records

    :param ~chapps.models.CHAPPSModel cls: the main data model

    :param ~chapps.models.CHAPPSResponse response_model: the response
      model

    :param dict params: defaults to ``dict(name=str)``; specify to provide
      additional column names and types, and be sure to include `name`, as all
      models currently are expected to have a `name` column, which is not
      allowed to be null.

    :param ~.JoinAssoc assoc: the associations to attach,
      if any

    :param ~sqlalchemy.engine.Engine engine: defaults to
      :const:`~chapps.dbsession.sql_engine`

    The returned coroutine implements an API route for creating an item,
    setting all its elements (other than ID) to whatever values are provided.
    Currently all values must be provided.  If desired, associations may also
    be provided to the factory, and they will be accommodated by the coroutine.

    For an example invocation of this factory, see :ref:`Creating Users <creating-users>`

    """
    params = params or dict(name=str)
    mname = model_name(cls)
    fname = f"create_{mname}"

    @db_interaction(cls=cls, engine=engine)
    async def create_i(*pargs, **args):
        extras = {}
        assoc_ret = {}
        if assoc:
            extras = {
                a.assoc_name: (a, args.pop(a.assoc_name))
                for a in assoc
                if a.assoc_name in args
            }
        item = cls.Meta.orm_model(**args)
        try:
            session.add(item)
            session.commit()
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Unique key conflict creating {mname}.",
            )
        except Exception:
            logger.exception(f"{fname}: {args!r}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        if extras:
            for assoc_name, (assc, vals) in extras.items():
                if not vals:  # no empty inserts
                    continue
                try:
                    session.execute(assc.insert(), assc.values(item, vals))
                    session.commit()
                    assoc_ret[assoc_name] = assc.assoc_model.wrap(
                        getattr(item, assoc_name)
                    )
                except IntegrityError:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Unable to create requested association to"
                            f"{assc.assoc_model.__name__.lower()} entries."
                            "  Please check object ids and try again."
                        ),
                    )

        return response_model.send(cls.wrap(item), **assoc_ret)

    routeparams = [  # assemble signature for FastAPI
        inspect.Parameter(
            name=param,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=Body(...),
            annotation=type_,
        )
        for param, type_ in params.items()
    ]
    if assoc:
        routeparams.extend(
            [
                inspect.Parameter(
                    name=a.assoc_name,
                    kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=Body(None),
                    annotation=a.assoc_type,
                )
                for a in assoc
            ]
        )
    create_i.__signature__ = inspect.Signature(routeparams)
    create_i.__annotations__ = params
    create_i.__name__ = fname
    create_i.__doc__ = f"""
        Create a new **{mname}** record in the database.<br/>
        All attributes are required.<br/>
        The new object will be returned, including its ID.<br/>
        Raises descriptive errors on 409; checking the detail
          of the error may aid in debugging.
        """
    return create_i
