"""CHAPPS Data Validation Models
-----------------------------

This module consists of the Pydantic_ data models required to represent and
also communicate about the various database records which control CHAPPS.
There are a few types of models, and perhaps more types to come, so some short
discussion of what they are and why they are needed seems reasonable.

Representational Models
~~~~~~~~~~~~~~~~~~~~~~~

There are (currently quite simple) objects which control CHAPPS: **User**
objects are at the root of that tree, and they are linked to one (outbound)
**Quota** object each to control how much email they may send.  **User**
objects may also be linked to multiple **Domain** and **Email** objects, to
represent who they are allowed to appear to be while sending email.

FastAPI_ uses Pydantic_ for data validation during API execution.  It behooves
us to define Pydantic_ models as representations of the objects, therefore.
This could be considered the front-facing identity of the object, which has a
back-facing identity represented by its database model, defined in
:mod:`~.dbmodels`.

A metaclass is defined which implements `__getattr__`, in order to allow the
validation model to masquerade as a database model to a certain extent.  That
routine expects the validation model to define a subclass called `Meta` with a
class attribute called `orm_model` which refers to the database model for the
object.  In this way, the validation model (class) is empowered to marshall a
set of instances from the database, without a lot of messy dereferencing.

API Response Models
~~~~~~~~~~~~~~~~~~~

In order to specify to the API constructors and the automatic API documentation
generators what the response for a particular API route should look like
(contain), more Pydantic_ models are defined.

All responses contain the CHAPPS version string and UNIX epoch time stamp in
them, as well as the response to the query, and possibly optional data
regarding an object's associations.  A fair number of response models are
defined, and they also fall into a few categories.

Unitary Data Model Responses
++++++++++++++++++++++++++++

When a single object of the primary type is being returned, that object is the
value of the `response` key in the object returned by the API.  If the object
has associations to objects of other types, the expectation is that a list of
those objects will be returned as the value of a key named for the association,
as if it were to be accessed via the ORM.  Those associated objects are listed
without any of their own associations included.

Data Model Listing Responses
++++++++++++++++++++++++++++

These response models are named almost exactly the same as their unitary
counterparts, but with their model names pluralized.  They will contain a list
of objects of the relevant type in their `response` attributes, without any
associations.

Custom Live Responses
+++++++++++++++++++++

Some of the response models are meant to relay information from the
:mod:`~.live` API routes, which deal with the current state of CHAPPS as
reflected in Redis.  These are each explained in their own documentation.

Basic Datatype Responses
++++++++++++++++++++++++

Some operations return a very simple value, such as an integer or string, and
so there are some response models to use in such cases.

.. todo::

  perhaps construct as a completely separate project a framework for creating
  arbitrary 'double-ended' Pydantic_ / SQLAlchemy_ data model objects, with
  arbitrary join tables and basic route factories for FastAPI_.  There are some
  similar projects but I couldn't find one which supported compound primary
  keys.

"""

from chapps.config import config
from chapps import dbmodels
from typing import Optional, List, Dict, Union, Tuple
from pydantic import BaseModel, constr, Field, validator
from pydantic.main import ModelMetaclass
from enum import Enum
import validators
import time

VERSTR = config.chapps.version


class AssocOperation(str, Enum):
    """'add', 'subtract', or 'replace'

    use 'replace' only with unitary associations; logic in
    :class:`~.JoinAssoc` which responds
    to the `replace` operation is designed to work only with
    scalar values.

    """

    add = "add"
    subtract = "subtract"
    replace = "replace"


class SDAStatus(str, Enum):
    """sender-domain auth status: AUTH, PROH, or NONE"""

    AUTH = "AUTHORIZED"
    PROH = "PROHIBITED"
    NONE = "NOT CACHED"


class SPFResult(str, Enum):
    """SPF check results"""

    passing = "pass"
    fail = "fail"
    temperror = "temperror"
    permerror = "permerror"
    softfail = "softfail"
    none_neutral = "none_neutral"


class PolicyResponse:
    """A wrapper for policy results"""

    @staticmethod
    def policy_response(passing: bool, decision: str):
        """Wrap an action in order to return it as a PolicyResponse

        This routine is suitable for use as a decorator
        """

        def pr_decorator(func: callable):
            def policy_response(message="", *args, **kwargs):
                return PolicyResponse(
                    response=func(message, *args, **kwargs),
                    passing=passing,
                    decision=decision,
                )

            return policy_response

        return pr_decorator

    def __init__(
        self, *, response: str, passing: bool, decision: Optional[str] = None
    ):
        self.response = response
        self.passing = passing
        self.decision = decision

    def __getattribute__(self, attr):
        if attr in dir(str):

            def method(self, *args, **kwargs):
                return getattr(self.response, attr)(*args, **kwargs)

            return method.__get__(self)
        else:
            return super().__getattribute__(attr)

    def __getitem__(self, *args, **kwargs):
        return self.response.__getitem__(*args, **kwargs)

    def __eq__(self, *args, **kwargs):
        return self.response.__eq__(*args, **kwargs)

    def __bool__(self):
        return self.passing

    def __str__(self):
        return self.response

    def __repr__(self):
        return (
            f"PolicyResponse(response='{self.response}',"
            f" passing={self.passing}"
            + (f", decision='{self.decision}'" if self.decision else "")
            + ")"
        )


# a metaclass for passing calls through to the orm_model
class CHAPPSMetaModel(ModelMetaclass):
    """Metaclass for CHAPPS Pydantic models

    We inject an override for :meth:`~.__getattr__` in order to attempt to find
    missing attributes on the ORM class attached via the `Meta` subclass of
    each model class.  This allows the Pydantic data-model class to serve as a
    proxy for the ORM class, meaning that we can handle Pydantic models in the
    API code, and still call ORM methods on them, and cause corresponding ORM
    objects to be instantiated on demand, etc.

    .. document private functions
    .. automethod:: __getattr__

    """

    def __getattr__(cls, var):
        """ORM Masquerading

        If the requested attribute exists on the :const:`~.orm_model`, return
        it, or else `None`.  Note that while the variable name used assumes the
        attribute will refer to a callable, it will work on any attribute.

        """
        orm_model = cls.Meta.orm_model
        orm_method = getattr(orm_model, var, None)
        try:
            return orm_method or super().__getattr__(var)
        except AttributeError:
            raise AttributeError(
                f"No attribute {var} could be found on "
                + ".".join([cls.__module__, cls.__name__])
                + "or on "
                + ".".join([orm_model.__module__, orm_model.__name__])
            )


# there could be a metaclass which would look for dbmodels classes matching
# the names of subclasses of CHAPPSModel and automatically hook up their
# Meta.orm_model data ... if the number of tables starts to grow
class CHAPPSModel(BaseModel, metaclass=CHAPPSMetaModel):
    """Base API data model

    All models should define a class called `Meta` and define within it a
    variable called `orm_model` as a reference to the ORM model class
    (generally defined in :mod:`.dbmodels`) corresponding to the
    data model.  In this abstract superclass, the ORM model reference is to the
    parallel abstract ORM model superclass.

    Models also define a class called `Config`, which is used by
    :mod:`Pydantic`.  In it, `orm_mode` should be set to `True`.  It is
    also possible to include additional detail for the OpenAPI documentation
    parser.

    All models have these attributes/columns:

    """

    id: int
    """integer auto-incrementing primary identifier"""
    name: str
    """unique string label"""

    class Meta:
        """Used by CHAPPS"""

        orm_model = dbmodels.DB_Base
        """The ORM model class corresponding to this data model"""

    @classmethod
    def id_name(cls) -> str:
        """:returns: name of the ID column in a join table"""
        return "_".join(str(cls.Meta.orm_model.id).lower().split("."))

    @classmethod
    def wrap(cls, orm_instance):
        """Wrap an ORM instance in its corresponding Pydantic data model

        :param cls.Meta.orm_model orm_instance: an ORM instance of the
          appropriate type

        :returns: a pydantic model created from an ORM model

        """
        if not orm_instance:  # could be None or []
            return orm_instance
        try:
            orm_iter = iter(orm_instance)
            return [cls.from_orm(oi) for oi in orm_iter]
        except TypeError:
            return cls.from_orm(orm_instance)

    @classmethod
    def join_assoc(cls, **kwargs) -> dbmodels.JoinAssoc:
        """Create a :class:`~.JoinAssoc` with this class as the source

        :param str assoc_name: attribute name of the association

        :param type assoc_type: usually :obj:`int` or :obj:`List[int]`; should
          be the type for the API to expect when setting up the route metadata

        :param DB_Base assoc_model: a reference to the dbmodel class of the
          associated object

        :param str assoc_id: label of associated object's ID column in the
          join table

        :param sqlalchemy.schema.Table table: a reference to the join table
          schema; it will be a constant in this module, generally

        This convenience routine for generating a
        :class:`~.JoinAssoc` provides the source model and
        ID-column info as it passes on the other arguments.

        """
        # if it became necessary to track some other arbitrary id-column name
        # we could accomplish that with a metaclass, and then just set it
        # in each subclass
        return dbmodels.JoinAssoc(cls, cls.__name__.lower() + "_id", **kwargs)


class User(CHAPPSModel):
    """**User** objects represent entities authorized to send email"""

    # The **User** is central to CHAPPS's policy-enforcement strategy.
    # When a **User** attempts to send email, CHAPPS is able to check:

    # 1. That **User**\ 's **Quota**

    # 2. Whether the **User** is authorized to send email from the proposed
    #    email's apparent sender-\ **Domain**, or whether they might be
    #    authorized to send email appearing to come from the entire **Email**
    #    address.

    name: constr(strip_whitespace=True, min_length=5, max_length=127) = Field(
        ...,
        title="user identifier",
        description="may be an email address, or some other unique identifier",
    )
    """user identifiers may be from 5 to 127 chars long"""

    class Config:
        orm_mode = True
        schema_extra = dict(
            example=dict(id=0, name=("[user.identifier@]domain.name"))
        )

    class Meta:
        orm_model = dbmodels.User


class Quota(CHAPPSModel):
    """**Quota** objects represent transmission count limits"""

    # The time-interval over which **Quota** objects are enforced is 24 hr.
    # They therefore have an integer `quota` field which contains the limit
    # of transmissions per 24 hours.  A sliding window is applied to a
    # transmission-attempt history, in order to avoid having a daily reset.

    # **Quota** objects also have `id` and `name` fields, like all models.

    name: constr(strip_whitespace=True, min_length=3, max_length=31) = Field(
        title="quota label", description="a descriptive tag"
    )
    """quota labels may be up to 31 chars long"""
    quota: int
    """unique integer outbound transmission limit"""

    class Config:
        orm_mode = True
        schema_extra = dict(
            example=dict(id=0, name="fiftyPerHour", quota=1200)
        )

    class Meta:
        orm_model = dbmodels.Quota


class Domain(CHAPPSModel):
    """Domain objects have a name and ID; the name never contains an `@`"""

    name: constr(
        strip_whitespace=True, to_lower=True, min_length=5, max_length=63
    ) = Field(title="domain name")
    """domain names may be up to 63 chars long"""
    greylist: bool = Field(title="perform greylisting")
    """flag indicating whether to greylist all domain's inbound email"""
    check_spf: bool = Field(title="enforce SPF")
    """flag indicating whether to check SPF for domain's inbound email"""

    class Config:
        orm_mode = True
        schema_extra = dict(
            example=dict(
                id=0, name="[sub.]domain.tld", greylist=False, check_spf=True
            )
        )

    class Meta:
        orm_model = dbmodels.Domain

    @validator("name")
    def domain_validator(cls, val):
        result = validators.domain(val)
        if result:
            return val
        raise ValueError("The name field must be a valid domain name.")


class Email(CHAPPSModel):
    """Email objects have a name and ID; the name always contains an `@`"""

    name: constr(strip_whitespace=True, min_length=6, max_length=127) = Field(
        ..., title="email address"
    )

    class Config:
        orm_mode = True
        schema_extra = dict(example=dict(id=0, name="someone@example.com"))

    class Meta:
        orm_model = dbmodels.Email

    @validator("name")
    def email_validator(cls, val):
        if validators.email(val):
            return val
        raise ValueError("The name field must be an email address.")


class CHAPPSResponse(BaseModel):
    """Base :mod:`Pydantic` model for API responses"""

    version: str = VERSTR
    """The CHAPPS version as a string"""
    timestamp: float = time.time()
    """When this response was generated"""
    response: object
    """Whatever piece of data was requested"""

    class Config:
        schema_extra = dict(version=VERSTR, timestamp=time.time())

    @classmethod
    def send(model, response=None, **kwargs):
        """Utility function for encapsulating responses in a standard body"""
        mkwargs = dict(version=VERSTR, timestamp=time.time())
        if response:
            mkwargs["response"] = response
        return model(**mkwargs, **kwargs)


class UserResp(CHAPPSResponse):
    """Data model for responding with a single **User** record"""

    response: User
    """The `response` field contains a **User** record"""
    domains: Optional[List[Domain]] = None
    """A list of associated **Domain** records may be included"""
    emails: Optional[List[Email]] = None
    """A list of associated **Email** records may be included"""
    quota: Optional[Quota] = None
    """The **Quota** record associated with the **User** may be included"""


class UsersResp(CHAPPSResponse):
    """Data model for responding with a list of **User** records"""

    response: List[User]
    """A list of **User** objects"""


class DomainResp(CHAPPSResponse):
    """Data model for responding with a single **Domain** record"""

    response: Domain
    """A **Domain** object"""
    users: Optional[List[User]] = None
    """A list of **User** objects associated to the **Domain** may be included
    """


class DomainsResp(CHAPPSResponse):
    """Data model for responding with a list of **Domain** records"""

    response: List[Domain]
    """A list of **Domain** objects"""


class EmailResp(CHAPPSResponse):
    """Data model for responding with a single **Email** record"""

    response: Email
    """An **Email** object"""
    users: Optional[List[User]] = None
    """A list of associated **User** objects may be included"""


class EmailsResp(CHAPPSResponse):
    """Data model for responding with a list of **Email** records"""

    response: List[Email]
    """A list of **Email** objects"""


class QuotaResp(CHAPPSResponse):
    """Data model for responding with a single **Quota** record"""

    response: Quota
    """A **Quota** object"""


class QuotasResp(CHAPPSResponse):
    """Data model for responding with a list of **Quota** records"""

    response: List[Quota]
    """A list of **Quota** objects"""


class IntResp(CHAPPSResponse):
    """Data model for responding with an integer"""

    response: int
    """An integer"""


class FloatResp(CHAPPSResponse):
    """Data model for responding with a float"""

    response: float
    """A floating-point number"""


class TextResp(CHAPPSResponse):
    """Data model for responding with a string"""

    response: str
    """A string"""


class TimeResp(FloatResp):
    """Data model for responding with a UNIX epoch time value"""

    response: float = time.time()
    """UNIX epoch time (UTC)"""


class InstanceTimesResp(CHAPPSResponse):
    """Data model for returning a list of instances and timestamps"""

    response: List[Tuple[str, float]]
    """A list of (instance, timestamp) tuples"""

    class Config:
        schema_extra = {
            "example": {
                "response": [
                    ["instance001", time.time() - 12000.0],
                    ["instance002", time.time() - 6000.0],
                ],
                "timestamp": time.time(),
                "version": config.chapps.version,
            }
        }


class LiveQuotaResp(CHAPPSResponse):
    """Data model for responses from the Live API"""

    response: int
    """An integer"""
    remarks: List[str] = []
    """A list of string remarks may be included"""


class SourceUserMapResp(CHAPPSResponse):
    """
    A source-user map is a dict-of-dicts:
      - top level key is domain or email name
      - second key is user
      - value is SDAStatus
    """

    response: Dict[str, Dict[str, SDAStatus]]
    """A map of auth-subject to dicts of username mapping to status"""


class BulkQuotaResp(CHAPPSResponse):
    """
    Maps **User** `name` onto **Quota** `id`

    With descriptive labels and optional remarks (from the live API)
    """

    response: List[Dict[str, Union[str, int, None]]]
    remarks: List[str] = []


class BulkDomainsResp(CHAPPSResponse):
    """
    Maps **User** `name` onto lists of **Domain** `id`

    With descriptive labels and optional remarks (from the live API)
    """

    response: List[Dict[str, Union[str, List[int], None]]]
    remarks: List[str] = []


class BulkEmailsResp(BulkDomainsResp):
    """
    Maps **User** `name` onto lists of **Email** `id`

    With descriptive labels and optional remarks (from the live API)
    """


class DeleteResp(TextResp):
    """Data model for responding to deletion requests"""

    response: str = "deleted"
    """The string 'deleted'"""


# the following classes are somewhat speculative for now
# class FloatResp(CHAPPSResponse):
#     """Data model for responding with a float"""

#     response: float
#     """A float"""

user_quota_assoc = User.join_assoc(
    assoc_name="quota",
    assoc_type=int,
    assoc_model=Quota,
    assoc_id=Quota.id_name(),
    table=User.Meta.orm_model.metadata.tables["quota_user"],
)

user_domains_assoc = User.join_assoc(
    assoc_name="domains",
    assoc_type=List[int],
    assoc_model=Domain,
    assoc_id=Domain.id_name(),
    table=User.Meta.orm_model.metadata.tables["domain_user"],
)

user_emails_assoc = User.join_assoc(
    assoc_name="emails",
    assoc_type=List[int],
    assoc_model=Email,
    assoc_id=Email.id_name(),
    table=User.Meta.orm_model.metadata.tables["email_user"],
)

domain_users_assoc = Domain.join_assoc(
    assoc_name="users",
    assoc_type=List[int],
    assoc_model=User,
    assoc_id="user_id",
    table=Domain.Meta.orm_model.metadata.tables["domain_user"],
)

email_users_assoc = Email.join_assoc(
    assoc_name="users",
    assoc_type=List[int],
    assoc_model=User,
    assoc_id="user_id",
    table=Email.Meta.orm_model.metadata.tables["email_user"],
)

# there is no quota_users_assoc because we don't list users by quota association
