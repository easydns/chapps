"""Common code between routers; mainly dependencies"""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy.engine.base import Engine


async def list_query_params(skip: int = 0, limit: int = 1000, q: Optional[str] = "%"):
    return dict(q=q, skip=skip, limit=limit)


def get_item_by_id(cls, *, engine, response_model, assoc: dict = {}):
    """
    Build a route to get an item by ID:
    first argument is the main datamodel for the request
    named arguments supply the DB engine for session creation
    and the Pydantic response model for the output
    the optional dict assoc maps the names of associated models
    onto the data model for the associated objects
    """

    async def get_by_id(item_id: int):
        with Session(engine) as session:
            try:
                stmt = cls.select_by_id(item_id)
                item = session.scalar(stmt)
                if item:
                    if assoc:
                        extra_args = {
                            key: model.wrap(getattr(item, ak))
                            for key, model in assoc.items()
                        }
                        return response_model.send(
                            cls.wrap(item), **extra_args)
                    else:
                        return response_model.send(cls.wrap(item))
            except Exception:
                logger.exception(f"get_by_id({cls.__class__.__name__}):")
        raise HTTPException(
            status_code=404,
            detail=f"There is no {cls.__class__.__name__.lower()} with id {item_id}",
        )
    return get_by_id
