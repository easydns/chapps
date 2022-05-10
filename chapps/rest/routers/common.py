"""Common code between routers

API route factories and also some :mod:`FastAPI` dependencies are defined in this module.

The route factories perform the repetitive grunt work required to set up the typical 'create', 'read', 'update', 'delete' and 'list' functions needed for basic object management.  In order to avoid extra levels of metaprogramming, the parameter name for the record ID of the main object involved in a factory-generated API call is ``item_id``, since it is clear, brief and generic.  Apologies to future subclassors who want an 'items' table.

These route factories are used to create all the routes for :mod:`~chapps.rest.routers.users`, :mod:`~chapps.rest.routers.emails`, :mod:`~chapps.rest.routers.domains`, and :mod:`~chapps.rest.routers.quotas`.

"""
from typing import Optional, List
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from fastapi import status, Depends, Body, HTTPException
from functools import wraps
import inspect
import logging
from chapps.rest.dbsession import sql_engine
from chapps.rest.models import AssocOperation, DeleteResp, TextResp
from chapps.rest.dbmodels import JoinAssoc
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)


async def list_query_params(
    skip: Optional[int] = 0,
    limit: Optional[int] = 1000,
    q: Optional[str] = "%",
):
    """FastAPI dependency for list queries"""
    return dict(q=q, skip=skip, limit=limit)


def model_name(cls):
    """Convenience function to get the lowercase name of a model"""
    return cls.__name__.lower()


def load_model_with_assoc(cls, assoc: List[JoinAssoc], engine=sql_engine):
    """Create a closure which loads an object along with arbitrary associations

    :param chapps.rest.models.CHAPPSModel cls: a data model class
    :param List[JoinAssoc] assoc: a list of associations (as
      :class:`JoinAssoc` objects)
    :param Optional[sqlalchemy.engine.Engine] engine: defaults to
      :const:`chapps.rest.dbsession.sql_engine` if not specified
    :rtype: callable
    :returns: a closure as follows:

      .. py:function:: f(item_id: int, name: Optional[str])

        :param int item_id: if non-zero, the ID of the main record
        :param Optional[str] name: if `item_id` is 0, the `name` of the record
          to match.
        :rtype: Tuple[~chapps.rest.models.CHAPPSModel, Dict[str, List[~chapps.rest.models.CHAPPSModel]], List[str]]
        :returns: a :obj:`tuple` containing:

          1. the object loaded by ID or name

          2. that object's associations in a :obj:`dict` keyed on attribute
             name (e.g. 'quota', 'domains')

          3. a list of string remarks, which may have no contents

    """
    mname = model_name(cls)
    assoc_s = "_".join([a.assoc_name for a in assoc])
    fname = f"load_{mname}_with_{assoc_s}"
    Session = sessionmaker(engine)

    def get_model_and_assoc(item_id: int, name: Optional[str]):
        remarks = []
        items = {k: None for k in [mname, *[a.assoc_name for a in assoc]]}
        with Session() as sess:
            if item_id:
                items[mname] = sess.scalar(cls.select_by_id(item_id))
            if name and not items[mname]:
                items[mname] = sess.scalar(cls.select_by_name(name))
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


def db_interaction(  # a decorator with parameters
    *,
    cls,
    engine=sql_engine,
    exception_message: str = ("{route_name}:{model}"),
    empty_set_message: str = ("Unable to find a matching {model}"),
):
    """Decorator for database interactions

    :param ~chapps.rest.models.CHAPPSModel cls: the data model class

    :param ~sqlalchemy.engine.Engine engine: an :mod:`SQLAlchemy` engine, which
      defaults to the package-wide one declared in
      :mod:`~chapps.rest.dbsession`

    :param str exception_message: a message to include if any untrapped
      exception occurs; defaults to '{route_name}:{model}'.  Only those two
      symbols are available for expansion.  All arguments are appended.

    :param str empty_set_message: included if a SELECT results in an empty set;
      defaults to 'Unable to find a matching {model}' and supports both
      substitutions that `exception_message` does

    :returns: a `decorator`_ closure, which will be called with the function to
      be `decorated`_as its argument.  In this case, the function is expected
      to be an async closure which is being manufactured for use in the API,
      and so the decorator closure returned by this routine defines a coroutine
      as the inner function, which is ultimately returned and used as the API
      route.

    :rtype: callable

    The decorator sets up some global symbols for use inside the API route
    closure coroutines:

      :session: a :class:`~sqlalchemy.orm.Session` instance created in a
        context containing the execution of the wrapped coroutine, suitable for
        performing database interactions, and which will be automatically
        closed after the coroutine completes

      :model_name: a string containing the lowercase name of the model

    .. _decorator: https://docs.python.org/3/glossary.html#term-decorator
    .. _decorated: https://peps.python.org/pep-0318/

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
    """Build a route coroutine closure to get an item by ID

    :param ~chapps.rest.models.CHAPPSModel: the main data model for the request

    :param ~chapps.rest.models.CHAPPSResponse response_model: the response
      model

    :param ~sqlalchemy.engine.Engine engine: defaults to
      :const:`~chapps.rest.dbsession.sql_engine`

    :param List[~chapps.rest.dbmodels.JoinAssoc] assoc: if included, these
      associations will be included in the return

    At present there is no provision for dealing with extremely long
    association lists.  Even if there were 500 elements, the response would not
    be extremely large.  TODO: provide option to suppress each association

    .. note::

      An alternate closure factory for creating route closures which
      specifically list associations does provide pagination, etc.  See
      :func:`~.`list_associated`

    The factory produces a coroutine closure decorated with the
    :func:`~.db_interaction` decorator, with a signature of ``(item_id: int)``.
    The final closure's name and doc metadata (dunder attributes) are set
    properly to ensure that the automatic documentation is coherent and
    accurate.

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
    """Build a route coroutine closure to list items

    :param ~chapps.rest.models.CHAPPSModel: the main data model for the request

    :param ~chapps.rest.models.CHAPPSResponse response_model: the response
      model

    :param ~sqlalchemy.engine.Engine engine: defaults to
      :const:`~chapps.rest.dbsession.sql_engine`

    The returned closure expects to receive the query parameters as a dict,
    since that is what the dependency will yield.  Its signature is

      .. code:: python

        async def list_i(qparams: dict = Depends(list_query_params))

    The closure's name and document metadata are updated to ensure coherence
    and accuracy of the automatic API documentation.

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
    cls, *, assoc: JoinAssoc, response_model, engine=sql_engine
):
    """
    Build a route to list associated items with pagination
    """
    mname = model_name(cls)
    fname = f"{mname}_list_{assoc.assoc_name}"
    params = dict(item_id=int, qparams=dict)
    p_dfls = dict(item_id=None, qparams=Depends(list_query_params))

    @db_interaction(cls=cls, engine=engine)
    async def assoc_list(*pargs, **args):
        # item_id for source object of type cls
        # the specified association is listed according to qparams
        stmt = assoc.assoc_model.windowed_list_by_ids(
            subquery=assoc.select_ids_by_source_id(args["item_id"]),
            **args["qparams"],
        )
        assocs = assoc.assoc_model.wrap(session.scalars(stmt))
        if assocs:
            return response_model.send(assocs)

    routeparams = [
        inspect.Parameter(
            name=param,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=type_,
            default=p_dfls[param],
        )
        for param, type_ in params.items()
    ]
    assoc_list.__signature__ = inspect.Signature(routeparams)
    assoc_list.__annotations__ = params
    assoc_list.__name__ = fname
    assoc_list.__doc__ = (
        f"List **{assoc.assoc_name}** associated with a particular **{mname}**,"
        " identified by ID.<br/>Supply standard query parameters for matching and"
        " pagination."
    )
    return assoc_list


def delete_item(
    cls, *, response_model=DeleteResp, params=None, engine=sql_engine
):
    f"""Delete {cls.__name__}"""
    params = params or dict(ids=List[int])
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
    """Build a route to add or subtract associations"""
    mname = model_name(cls)
    assoc_s = "_".join([a.assoc_name for a in assoc])
    fname = f"{mname}_{assoc_op}_{assoc_s}"
    params = params or dict(item_id=int)
    assoc_params = {a.assoc_id: a.assoc_type for a in assoc}

    @db_interaction(cls=cls, engine=engine)
    async def assoc_op_i(*pargs, **args):
        # item_id will be used for the source object, and assoc_ids will
        # be a list of associated ids to either remove or add associations
        # for, ignoring integrity errors arising from attempting to insert
        # duplicate associations; non-existent associations should not cause
        # errors when a query attempts to delete them.
        extras = {
            a.assoc_name: (a, args.pop(a.assoc_id))
            for a in assoc
            if a.assoc_id in args
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


def update_item(cls, *, response_model, assoc=None, engine=sql_engine):
    """
    Build a route to update items.
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
    """
    Build a route to create items.
    """
    params = params or dict(name=str)
    mname = model_name(cls)
    fname = f"create_{mname}"

    @db_interaction(cls=cls, engine=engine)
    async def create_i(*pargs, **args):
        """Bogus create item docstring"""
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
