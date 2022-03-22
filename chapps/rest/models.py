from chapps.config import config
from chapps.rest import dbmodels
from typing import Optional, List
from pydantic import BaseModel
from pydantic.main import ModelMetaclass
from enum import Enum
import time

verstr = config.chapps.version


class APIException(str, Enum):
    """Not sure if needed, leaving for now"""

    nonexistent = "nonexistent"
    integrity = "integrity"
    internal = "internal"


# a metaclass for passing calls through to the orm_model
class CHAPPSMetaModel(ModelMetaclass):
    def __getattr__(cls, var):
        orm_method = getattr(cls.Meta.orm_model, var, None)
        return orm_method or super().__getattr__(var)


# there could be a metaclass which would look for dbmodels classes matching
# the names of subclasses of CHAPPSModel and automatically hook up their
# Meta.orm_model data ... if the number of tables starts to grow
class CHAPPSModel(BaseModel, metaclass=CHAPPSMetaModel):
    """Base API data model"""

    id: int
    name: str

    class Meta:
        orm_model = dbmodels.DB_Base

    @classmethod
    def _o(cls):
        return cls.Meta.orm_model

    @classmethod
    def wrap(cls, orm_instance):
        """create a pydantic model from an ORM model"""
        if not orm_instance:  # could be None or []
            return orm_instance
        try:
            orm_iter = iter(orm_instance)
            return [cls.from_orm(oi) for oi in orm_iter]
        except TypeError:
            return cls.from_orm(orm_instance)


class User(CHAPPSModel):
    """API model to represent users"""

    class Config:
        orm_mode = True

    class Meta:
        orm_model = dbmodels.User


class Quota(CHAPPSModel):
    """API model to represent quotas"""

    quota: int

    class Config:
        orm_mode = True

    class Meta:
        orm_model = dbmodels.Quota


class Domain(CHAPPSModel):
    """A model to represent domains"""

    class Config:
        orm_mode = True

    class Meta:
        orm_model = dbmodels.Domain


class CHAPPSResponse(BaseModel):
    version: str
    timestamp: float
    response: object

    @classmethod
    def send(model, response, **kwargs):
        """Utility function for encapsulating responses in a standard body"""
        return model(
            version=verstr, timestamp=time.time(), response=response, **kwargs
        )


class UserResp(CHAPPSResponse):
    response: User
    domains: Optional[List[Domain]] = None
    quota: Optional[Quota] = None


class UsersResp(CHAPPSResponse):
    response: List[User]


class DomainResp(CHAPPSResponse):
    response: Domain
    users: Optional[List[User]] = None


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
