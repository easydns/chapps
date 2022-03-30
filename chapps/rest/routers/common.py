"""Common code between routers; mainly dependencies"""
from typing import Optional, List
from sqlalchemy.orm import Session
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
    return dict(q=q, skip=skip, limit=limit)


def model_name(cls):
    return cls.__name__.lower()


def db_interaction(  # a decorator with parameters
    *,
    cls,
    engine=sql_engine,
    exception_message: str = ("{route_name}:{model}"),
    empty_set_message: str = ("Unable to find a matching {model}"),
):
    """
    the db_interaction decorator requires a couple of parameters,
    and provides optional arguments to override the messages for
    either of two eventualities:
    1. any exception occurs; the argument list is automatically appended
    2. the set of return values (from an access operation) is empty, OR
       a delete operation could not find any objects to delete
    """

    mname = model_name(cls)

    def interaction_wrapper(rt_coro):
        logger.debug(f"Wrapping {rt_coro.__name__} for {cls.__name__}")

        exc = exception_message.format(
            route_name=rt_coro.__name__, model=mname
        )
        empty = empty_set_message.format(
            route_name=rt_coro.__name__, model=mname
        )

        @wraps(rt_coro)
        async def wrapped_interaction(*args, **kwargs):
            with Session(engine) as session:
                rt_coro.__globals__["session"] = session
                rt_coro.__globals__["model_name"] = mname

                try:
                    result = await rt_coro(*args, **kwargs)
                    if result:
                        return result
                except Exception:
                    logger.exception(exc + f"({args!r},{kwargs!r})")
            raise HTTPException(status_code=404, detail=empty)

        return wrapped_interaction  # a coroutine

    return interaction_wrapper  # a regular function


def get_item_by_id(cls, *, response_model, engine=sql_engine, assoc=None):
    """
    Build a route to get an item by ID:
    first argument is the main datamodel for the request
    named arguments supply the DB engine for session creation
    and the Pydantic response model for the output
    the optional dict assoc maps the names of associated models
    onto the data model for the associated objects
    """

    @db_interaction(cls=cls, engine=engine)
    async def get_i(item_id: int):
        f"""
        Retrieve {cls.__name__} records by ID,
        with any associated records
        """
        stmt = cls.select_by_id(item_id)
        item = session.scalar(stmt)
        if item:
            if assoc:
                extra_args = {
                    key: model.wrap(getattr(item, key)) for model, key in assoc
                }
                return response_model.send(cls.wrap(item), **extra_args)
            else:
                return response_model.send(cls.wrap(item))

    get_i.__name__ = f"get_{model_name(cls)}"
    return get_i


def list_items(cls, *, response_model, engine=sql_engine):
    """
    Build a route to list items.
    The factory just needs the control data -- the engine, the response model
    The returned closure expects to receive the query parameters as a dict,
    since that is what the dependency will yield.
    """

    @db_interaction(cls=cls, engine=engine)
    async def list_i(qparams: dict = Depends(list_query_params)):
        f"""List {cls.__name__}s"""
        stmt = cls.windowed_list(**qparams)
        items = cls.wrap(session.scalars(stmt))
        if items:
            return response_model.send(items)

    list_i.__name__ = f"list_{model_name(cls)}"
    return list_i


def delete_item(
    cls, *, response_model=DeleteResp, params=None, engine=sql_engine
):
    f"""Delete {cls.__name__}"""
    params = params or dict(ids=List[int])

    @db_interaction(cls=cls, engine=engine)
    async def delete_i(item_ids: List[int]):
        f"""Delete {cls.__name__}"""
        try:
            session.execute(cls.remove_by_id(item_ids))
            session.commit()
        except IntegrityError:
            logger.exception(
                "trying to delete {model_name(cls)} with {args!r}"
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Database integrity conflict.",
            )
        return response_model.send()

    delete_i.__name__ = f"delete_{model_name(cls)}"
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
    assoc_s = assoc[0].assoc_name if len(assoc) == 1 else "assoc"
    fname = f"{mname}_{assoc_op}_{assoc_s}"
    params = params or dict(item_id=int)
    assoc_params = {a.assoc_name: a.assoc_type for a in assoc}

    @db_interaction(cls=cls, engine=engine)
    async def assoc_op_i(*pargs, **args):
        (
            f"{str(assoc_op).capitalize()} "
            f"{', '.join([a.assoc_name for a in assoc])} objects "
            f"{'to' if assoc_op==AssocOperation.add else 'from'} {mname}"
        )
        # item_id will be used for the source object, and assoc_ids will
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
    logger.debug(f"{fname} got routeparams {routeparams!r}")
    assoc_op_i.__signature__ = inspect.Signature(routeparams)
    assoc_op_i.__annotations__ = params
    assoc_op_i.__name__ = fname
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
        f"""Update {cls.__name__}"""
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
    logger.debug(f"{fname} got routeparams {routeparams!r}")
    update_i.__signature__ = inspect.Signature(routeparams)
    update_i.__annotations__ = params
    update_i.__name__ = fname
    return update_i


def create_item(
    cls, *, response_model, params=None, assoc=None, engine=sql_engine
):
    """
    Build a route to create items.
    """
    params = params or dict(name=str)
    fname = f"create_{model_name(cls)}"

    @db_interaction(cls=cls, engine=engine)
    async def create_i(*pargs, **args):
        f"""Create {cls.__name__}"""
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
                detail="Unique key conflict.",
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
    logger.debug(f"{fname} got routeparams: {routeparams!r}")
    create_i.__signature__ = inspect.Signature(routeparams)
    create_i.__annotations__ = params
    create_i.__name__ = fname
    return create_i
