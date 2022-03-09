from chapps.config import config
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum
import time

verstr = config.chapps.version


class APIException(str, Enum):
    nonexistent = "nonexistent"
    integrity = "integrity"
    internal = "internal"


class CHAPPSModel(BaseModel):
    id: int
    name: str

    @classmethod
    def keys(model):
        return list(model.schema()["properties"].keys())

    @classmethod
    def zip_records(model, records: List[List]):
        keys = model.keys()
        return [model(**dict(zip(keys, record))) for record in records]

    @classmethod
    def select_query(model, *, where=[], window=(0, 1000), order="id"):
        """Build a select suitable for wrapping in a model"""
        keys = model.keys()
        query = f"SELECT {','.join( keys )} FROM {model.__name__.lower()}s"
        if where:
            query += f" WHERE {' AND '.join( where )}"
        query += f" ORDER BY {order} LIMIT {','.join([ str(l) for l in window])};"
        return query

    @classmethod
    def count_query(model, *, where=[]):
        """Build a generalized counting query"""
        query = f"SELECT COUNT( * ) FROM {model.__name__.lower() }s"
        if where:
            query += f" WHERE {' AND '.join( where )}"
        return query

    @classmethod
    def joined_select(
        model, filter_model, *, where: List[str], window=(0, 1000), order="m.id"
    ):  ### model table: m, join table: j
        """Build a generalized LEFT JOIN instruction, to say, get all domains for a user"""
        mm, fm = model.__name__.lower(), filter_model.__name__.lower()
        mt = mm + "s"
        mid = mm + "_id"
        jt = "_".join(sorted([mm, fm]))
        cols = ",".join([f"m.{col}" for col in model.keys()])
        query = f"SELECT {cols} FROM {mt} AS m LEFT JOIN {jt} AS j ON j.{mid} = m.id WHERE {' AND '.join( where )} ORDER BY {order} LIMIT {window[0]},{window[1]};"
        return query

    @classmethod
    def double_joined_select(
        model, filter_model, where: List[str], window=(0, 1000), order="m.id"
    ):  ### model table: m, filter_model table: f, join table: j
        """Build a generalized LEFT JOIN instruction, to say, get all domains for a user"""
        mm, fm = model.__name__.lower(), filter_model.__name__.lower()
        mt = mm + "s"
        mid = mm + "_id"
        ft = fm + "s"
        fid = fm + "_id"
        jt = "_".join(sorted([mm, fm]))
        cols = ",".join([f"m.{col}" for col in model.keys()])
        query = f"SELECT {cols} FROM {mt} AS m LEFT JOIN {jt} AS j ON j.{mid} = m.id LEFT JOIN {ft} AS f ON f.id = j.{fid} WHERE {' AND '.join( where )} ORDER BY {order} LIMIT {window[0]},{window[1]};"


class User(CHAPPSModel):
    """A model to represent users"""


class Quota(CHAPPSModel):
    """A model to represent quotas"""

    quota: int


class Domain(CHAPPSModel):
    """A model to represent domains"""


class CHAPPSResponse(BaseModel):
    version: str
    timestamp: float
    response: object

    @classmethod
    def send(model, response, **kwargs):
        """Utility function for encapsulating responses in a standard body"""
        return model(version=verstr, timestamp=time.time(), response=response, **kwargs)


class UserResp(CHAPPSResponse):
    response: User
    domains: Optional[List[Domain]] = None
    quota: Optional[Quota] = None


class UsersResp(CHAPPSResponse):
    response: List[User]


class DomainResp(CHAPPSResponse):
    response: Domain
    users: Optional[List[Domain]] = None


class DomainsResp(CHAPPSResponse):
    response: List[Domain]


class QuotaResp(CHAPPSResponse):
    response: Quota


class QuotasResp(CHAPPSResponse):
    response: List[Quota]


class IntResp(CHAPPSResponse):
    response: int


class TextResp(CHAPPSResponse):
    response: str


class ConfigResp(CHAPPSResponse):
    response: List[str]
    written: bool
    write_path: str = None


class DeleteResp(TextResp):
    status: bool


### the following classes are somewhat speculative for now
class FloatResp(CHAPPSResponse):
    response: float


class ErrorResp(CHAPPSResponse):
    response: None
    error: APIException
    message: str
