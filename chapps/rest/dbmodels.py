"""SQLAlchemy ORM Models to correspond to Pydantic models for API"""
from typing import List
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Table,
    select,
    update,
    tuple_,
    delete,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
    backref,
    DeclarativeMeta,
)
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)


class JoinAssoc:
    """
    A class for representing joins via jointable
    There is probably some way to use SQLA for this
    but I am using it wrongly, to avoid loading associations
    just in order to link them to other objects
    via a join table
    """

    def __init__(
        self,
        source_model,
        source_id: str,
        *,
        assoc_name: str,
        assoc_type,
        assoc_model,
        assoc_id: str,
        table,
    ):
        self.source_model = source_model
        self.source_id = source_id
        self.assoc_name = assoc_name
        self.assoc_type = assoc_type
        self.assoc_model = assoc_model
        self.assoc_id = assoc_id
        self.table = table

    def __repr__(self):
        return (
            f"JoinAssoc({self.source_model.__name__}, "
            f"{self.assoc_model.__name__}, "
            f"{self.assoc_name}, {self.assoc_type!r})"
        )

    def insert(self):
        return self.table.insert()

    def delete(self):
        return self.table.delete()

    def values(self, item, assoc):
        item_id = item if type(item) == int else item.id
        try:
            i = iter(assoc)
            ins = [{self.source_id: item_id, self.assoc_id: val} for val in i]
        except TypeError:
            ins = [{self.source_id: item_id, self.assoc_id: assoc}]
        return ins

    def where_tuples(self, item_id, assoc):
        try:
            i = iter(assoc)
            res = [(item_id, val) for val in i]
        except TypeError:
            res = [(item_id, assoc)]
        return res

    @property
    def source_col(self):
        return getattr(self.table.c, self.source_id)

    @property
    def assoc_col(self):
        return getattr(self.table.c, self.assoc_id)

    def insert_assoc(self, item_id, vals):
        return (
            self.insert()
            .prefix_with("IGNORE")
            .values(self.values(item_id, vals))
        )

    def delete_assoc(self, item_id, vals):
        return self.delete().where(
            tuple_(self.source_col, self.assoc_col).in_(
                self.where_tuples(item_id, vals)
            )
        )


# declare subclass of the SQLAlchemy DeclarativeMeta class
# in order to attach custom routines to the ORM objects
class DB_Customizations(DeclarativeMeta):
    """Metaclass for adding custom code to ORM models"""

    def select_by_id(cls, id: int):
        return select(cls).where(cls.id == id)

    def select_by_pattern(cls, q: str):
        return select(cls).where(cls.name.like(q))

    def windowed_list(cls, q: str = "%", skip: int = 0, limit: int = 1000):
        return (
            cls.select_by_pattern(q).offset(skip).limit(limit).order_by(cls.id)
        )

    def remove_by_id(cls, ids: List[int]):  # (i,) creates a tuple w/ 1 element
        return delete(cls).where(tuple_(cls.id).in_([(i,) for i in ids]))

    def update_by_id(cls, item):
        print(f"Got item:{item!r}")
        args = {
            k: getattr(item, k) for k in item.schema()["properties"].keys()
        }
        id = args.pop("id")
        return update(cls).where(cls.id == id).values(**args)


# declare DB model base class
DB_Base = declarative_base(metaclass=DB_Customizations)
"""DB_Base serves as the base of all ORM classes"""

quota_user = Table(
    "quota_user",
    DB_Base.metadata,
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE", onupdate="RESTRICT"),
        primary_key=True,
    ),
    Column(
        "quota_id",
        ForeignKey("quotas.id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
    ),
)
domain_user = Table(
    "domain_user",
    DB_Base.metadata,
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE", onupdate="RESTRICT"),
        primary_key=True,
    ),
    Column(
        "domain_id",
        ForeignKey("domains.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    ),
)


class Quota(DB_Base):
    """ORM Model for quota definitions"""

    __tablename__ = "quotas"

    id = Column(Integer, primary_key=True)
    name = Column(String(32), unique=True)
    quota = Column(Integer, unique=True)

    def __repr__(self):
        return f"Quota[ORM](id={self.id!r}, name={self.name!r}, quota={self.quota!r})"


class Domain(DB_Base):
    """ORM Model for domain definitions"""

    __tablename__ = "domains"

    id = Column(Integer, primary_key=True)
    name = Column(String(64))

    def __repr__(self):
        return f"Domain[ORM](id={self.id!r}, name={self.name!r})"


class User(DB_Base):
    """ORM model for user entities within CHAPPS"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True)
    quota = relationship(
        Quota,
        secondary=quota_user,  # using m2m mainly for optimization
        backref="users",  # wants to be efficient and non-eager
        passive_deletes=True,  # prevent loading during deletion
        single_parent=True,  # only one association to quota
        uselist=False,  # one quota per user
        primaryjoin=id == quota_user.c.user_id,
        secondaryjoin=Quota.id == quota_user.c.quota_id,
    )
    domains = relationship(
        Domain,
        secondary=domain_user,  # really m2m
        backref=backref("users", order_by="User.id"),  # reverse associate
        order_by=Domain.id,  # order by id
        passive_deletes=True,  # protect domains
    )

    def __repr__(self):
        return f"User[ORM](id={self.id!r}, name={self.name!r})"


### for testing purposes:
import urllib.parse
from sqlalchemy import select, text, create_engine, insert
from sqlalchemy.orm import Session

password = urllib.parse.quote_plus("screwy%pass${word}")
engine = create_engine(
    f"mariadb+pymysql://chapps_test:{password}@localhost/chapps_test"
)


def proc_run(stmt):
    results = []
    with engine.connect() as conn:
        for row in conn.execute(stmt):
            print(row)
            results.append(row)
    return results


def orm_run(stmt):
    results = []
    with Session(engine) as session:
        for row in session.execute(stmt).scalars():
            print(row)
            results.append(row)
    return results
