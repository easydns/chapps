"""Common code between routers; mainly dependencies"""
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import Depends, Body
from functools import wraps
import inspect
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)


async def list_query_params(
    skip: Optional[int] = 0,
    limit: Optional[int] = 1000,
    q: Optional[str] = "%",
):
    return dict(q=q, skip=skip, limit=limit)


def db_interaction(
    *,
    engine,
    exception_message: str = (
        "{route_coroutine.__name__}"
        "({cls.__name__}, a={args!r},"
        " kw={kwargs!r})"
    ),
    empty_set_message: str = (
        "Unable to find a matching " "{cls.__name__.lower())}"
    ),
):
    def interaction_wrapper(route_coroutine):
        @wraps(route_coroutine)
        async def wrapped_interaction(*args, **kwargs):
            with Session(engine) as session:
                route_coroutine.__globals__["session"] = session
                try:
                    return await route_coroutine(*args, **kwargs)
                except Exception:
                    logger.exception(exception_message.format(**locals()))
            raise HTTPException(
                status_code=404, detail=empty_set_message.format(**locals())
            )

        return wrapped_interaction  # a coroutine

    return interaction_wrapper  # a regular function


def get_item_by_id(cls, *, engine, response_model, assoc: dict = {}):
    """
    Build a route to get an item by ID:
    first argument is the main datamodel for the request
    named arguments supply the DB engine for session creation
    and the Pydantic response model for the output
    the optional dict assoc maps the names of associated models
    onto the data model for the associated objects
    """

    @db_interaction(
        engine=engine,
        exception_message="get_by_id({cls.__name__}, {item_id}):",
        empty_set_message=(
            "There is no {cls.__name__.lower()} " "with id {item_id}"
        ),
    )
    async def get_by_id(item_id: int):
        stmt = cls.select_by_id(item_id)
        item = session.scalar(stmt)
        if item:
            if assoc:
                extra_args = {
                    key: model.wrap(getattr(item, key))
                    for key, model in assoc.items()
                }
                return response_model.send(cls.wrap(item), **extra_args)
            else:
                return response_model.send(cls.wrap(item))

    return get_by_id


def list_items(cls, *, engine, response_model):
    """
    Build a route to list items.
    The factory just needs the control data -- the engine, the response model
    The returned closure expects to receive the query parameters as a dict,
    since that is what the dependency will yield.
    """

    @db_interaction(
        engine=engine,
        exception_message="list_i({cls.__name__}, {qparams!r}):",
        empty_set_message=(
            "No {cls.__name__.lower()} records matched '%{qparams['q']}%'"
        ),
    )
    async def list_i(qparams: dict = Depends(list_query_params)):
        stmt = cls.windowed_list(**qparams)
        items = cls.wrap(session.scalars(stmt))
        if items:
            return response_model.send(items)

    return list_i


def create_item(cls, *, engine, response_model, params=dict(name=str)):
    """
    Build a route to create items.
    """

    @db_interaction(engine=engine)
    async def create_i(*pargs, **args):
        """
        the args are k-v pairs, the keys are column names
        we sort out the annotations for FastAPI after
        """
        om = cls.Meta.orm_model
        item = om(**args)
        session.add(item)
        session.commit()
        return response_model.send(cls.wrap(item))

    routeparams = [  # assemble signature for FastAPI
        inspect.Parameter(
            name=param,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=Body(...),
            annotation=type_,
        )
        for param, type_ in params.items()
    ]
    create_i.__signature__ = inspect.Signature(routeparams)
    create_i.__annotations__ = params
    return create_i
