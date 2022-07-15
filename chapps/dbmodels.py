"""
CHAPPS data schemata
--------------------

Database schema expressed as `SQLAlchemy`_ `ORM Models`_

Basic data models correspond to Pydantic models for API, but more models are
required for the database side:

  * There is a subclass of the metaclass,
    :class:`~sqlalchemy.orm.DeclarativeMeta`, which provides extra logic to
    the database models to automate common queries and tasks.

  * There are table definitions for the join tables.

  * There is a special class for generalizing the logic of joining the tables.

.. todo::

    it seems like there must be some way to obtain more of the data
    tracked by :class:`.JoinAssoc` from the :mod:`SQLAlchemy` metadata but I
    have not figured much of it out yet.)

.. _orm models: https://docs.sqlalchemy.org/en/14/orm/quickstart.html

"""
from typing import Dict, List, Union, Optional, Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
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
    selectinload,
)
from sqlalchemy.schema import MetaData
import logging
import chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(chapps.logging.DEFAULT_LEVEL)

convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",  # or column_0_name
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
"""SQLA's recommended naming convention for constraints"""

# declare subclass of the SQLAlchemy DeclarativeMeta class
# in order to attach custom routines to the ORM objects
class DB_Customizations(DeclarativeMeta):
    """Custom ORM metaclass

    In order to make common tasks more concise, and to conceal the need for
    complex data massaging in order to produce appropriate data structures for
    the different kinds of queries, a fair amount of custom code is introduced
    into the ORM models via this metaclass.  These routines allow calls to the
    ORM class itself, to get it to return statement objects (objects defined in
    :mod:`sqlalchemy.sql.expression`).

    """

    def select_by_id(cls, id: int):
        """SELECT (load) a single object by ID"""
        return select(cls).where(cls.id == id)

    def windowed_list_by_ids(
        cls,
        *,
        ids: List[int] = [],
        subquery=None,
        skip: int = 0,
        limit: int = 1000,
        q: str = "%",
    ):
        """SELECT a window of objects

        :param Optional[List[int]] ids: a list of IDs
        :param Optional[~sqlalchemy.sql.expression.Subquery] subquery: a
          sub-SELECT which yields IDs
        :param Optional[int] skip: start the window after `skip` entries
        :param Optional[int] limit: include up to `limit` entries in the
          result
        :param Optional[str] q: a substring to match against the `name` field

        :raises ValueError: unless one of `ids` or `subquery` is provided

        :returns: a :class:`~sqlalchemy.sql.expression.Select` implementing the window

        :rtype: sqlalchemy.sql.expression.Select

        If both of `subquery` and `ids` are not empty, `subquery`
        prevails and `ids` is ignored.

        """
        if subquery is not None:
            stmt = select(cls).where(cls.id.in_(subquery))
        elif ids:
            stmt = select(cls).where(tuple_(cls.id).in_([(i,) for i in ids]))
        else:
            raise ValueError("Supply one of ids or subquery.")
        stmt = (
            stmt.where(cls.name.like(q))
            .offset(skip)
            .limit(limit)
            .order_by(cls.id)
        )
        return stmt

    def select_by_ids(cls, ids: List[int], assoc: Optional[Any] = None):
        """Return a select statement for a list of objects,
           optionally with eager-loaded associations
        """
        stmt = select(cls).where(tuple_(cls.id).in_([(i,) for i in ids]))
        if assoc:
            stmt = stmt.options(selectinload(assoc))
        stmt = stmt.order_by(cls.id)
        return stmt

    def select_names_by_id(cls, ids: List[int]):
        """Return a Select for the names corresponding to the provided IDs"""
        return select(cls.name).where(tuple_(cls.id).in_([(i,) for i in ids]))

    def select_by_pattern(cls, q: str):
        """Return a Select for all records with names which include `q` as a substring"""
        return select(cls).where(cls.name.like(q))

    def select_by_name(cls, q: str):
        """Return a Select for the record whose name exactly matches `q`"""
        return select(cls).where(cls.name == q)

    def windowed_list(cls, q: str = "%", skip: int = 0, limit: int = 1000):
        """Return a Select for a window of :meth:`.select_by_pattern`"""
        return (
            cls.select_by_pattern(q).offset(skip).limit(limit).order_by(cls.id)
        )

    def remove_by_id(
        cls, ids: Union[int, List[int]]
    ):  # (i,) creates a tuple w/ 1 element
        """Return a Delete for the listed IDs (`ids` may be a scalar ID also)"""
        if type(ids) == int:
            ids = [ids]
        return delete(cls).where(tuple_(cls.id).in_([(i,) for i in ids]))

    def update_by_id(cls, item):
        """Return an Update statement for the specified item

        :param type cls: an ORM model class (subclass of :const:`~.DB_Base`)
        :param cls item: an instance of an ORM model of the type stored in `cls`

        :returns: an :class:`~sqlalchemy.sql.expression.Update` statement object representing the new values of `item`

        :rtype: sqlalchemy.sql.expression.Update

        """
        print(f"Got item:{item!r}")
        args = {
            k: getattr(item, k) for k in item.schema()["properties"].keys()
        }
        id = args.pop("id")
        return update(cls).where(cls.id == id).values(**args)


# declare DB model base class
DB_Base = declarative_base(
    metaclass=DB_Customizations,
    metadata=MetaData(naming_convention=convention),
)
"""DB_Base serves as the base of all `ORM models`_

This class itself contains literally no code apart from documentation.
All of the magic provided for the ORM layer is implemented in the metaclass,
:class:`~.DB_Customizations`.  To be clear, all of the methods defined in
the metaclass become available as class methods on the classes derived from
:class:`~.DB_Base`, because it is of type :class:`.DB_Customizations`.

"""


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
"""the `quota_user` join table"""

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
"""the `domain_user` join table"""

email_user = Table(
    "email_user",
    DB_Base.metadata,
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE", onupdate="RESTRICT"),
        primary_key=True,
    ),
    Column(
        "email_id",
        ForeignKey("emails.id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    ),
)
"""the `email_user` join table"""


class Quota(DB_Base):
    """ORM Model for **Quota** definitions

    Each record/instance has these columns/attributes:

    """

    __tablename__ = "quotas"

    id = Column(Integer, primary_key=True)
    """integer primary key"""
    name = Column(String(32), unique=True, nullable=False, index=True)
    """unique string of 32 chars or less"""
    quota = Column(Integer, unique=True, nullable=False, index=True)
    """unique integer transmission attempt limit"""

    def __repr__(self):
        return f"Quota[ORM](id={self.id!r}, name={self.name!r}, quota={self.quota!r})"


class Domain(DB_Base):
    """ORM Model for **Domain** definitions

    Each record/instance has these columns/attributes:

    """

    __tablename__ = "domains"

    id = Column(Integer, primary_key=True)
    """integer primary key"""
    name = Column(String(64), unique=True, nullable=False, index=True)
    """unique string of 64 chars or less"""
    greylist = Column(Boolean(name="greylist"), nullable=False, default=0)
    """if True perform greylisting"""
    check_spf = Column(Boolean(name="check_spf"), nullable=False, default=0)
    """if True perform SPF enforcement"""

    def __repr__(self):
        return (
            f"Domain[ORM](id={self.id!r}, "
            f"name={self.name!r}, "
            f"greylist={'Y' if self.greylist else 'N'}, "
            f"check_spf={'Y' if self.check_spf else 'N'})"
        )


class Email(DB_Base):
    """ORM Model for **Email** definitions

    Each record/instance has these columns/attributes:

    """

    __tablename__ = "emails"

    id = Column(Integer, primary_key=True)
    """integer primary key"""
    name = Column(String(128), unique=True, nullable=False, index=True)
    """unique string of 128 chars or less"""

    def __repr__(self):
        return f"Email[ORM](id={self.id!r}, name={self.name!r})"


class User(DB_Base):
    """ORM model for **User** objects

    Each record/instance has these columns/attributes:

    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    """integer auto-incremented primary key"""
    name = Column(String(128), unique=True, nullable=False, index=True)
    """unique string of up to 128 chars"""
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
    """associated **Quota** object; there can be only one **Quota** associated to a **User**"""
    domains = relationship(
        Domain,
        secondary=domain_user,  # really m2m
        backref=backref("users", order_by="User.id"),  # reverse associate
        order_by=Domain.id,  # order by id
        passive_deletes=True,  # protect domains
    )
    """list of associated **Domain** objects

    a **User** may be associated to more than one **Domain**, and
    a **Domain** may be associated to more than one **User**

    """
    emails = relationship(
        Email,
        secondary=email_user,
        backref=backref("users", order_by="User.id"),
        order_by=Email.id,
        passive_deletes=True,
    )
    """list of associated **Email** objects

    a **User** may be associated to more than one **Email**, and
    an **Email** may be associated to more than one **User**

    """

    def __repr__(self):
        return f"User[ORM](id={self.id!r}, name={self.name!r})"


class JoinAssoc:
    """Represent joining two data tables via a two-column join table

    There is probably some way to use SQLA for this but I am using it wrongly,
    to avoid loading associations just in order to link them to other objects
    via a join table

    """

    def __init__(
        self,
        source_model: DB_Base,
        source_id: str,
        *,
        assoc_name: str,
        assoc_type: type,
        assoc_model: DB_Base,
        assoc_id: str,
        table,
    ):
        """Define a join association

        :param DB_Base source_model: a reference to the dbmodel class of the
          source object

        :param str source_id: label of the source object's ID column in the
          join table

        :param str assoc_name: attribute name of the association

        :param type assoc_type: usually :obj:`int` or :obj:`List[int]`; should
          be the type for the API to expect when setting up the route metadata

        :param DB_Base assoc_model: a reference to the dbmodel class of the
          associated object

        :param str assoc_id: label of associated object's ID column in the
          join table

        :param sqlalchemy.schema.Table table: a reference to the join table
          schema; it will be a constant in this module, generally

        """
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

    def select(self):
        """Convenience method

        :returns: a SELECT on the join table

        :rtype: sqlalchemy.sql.expression.Select

        """
        return self.table.select()

    def insert(self):
        """Convenience method

        :returns: an INSERT on the join table

        :rtype: sqlalchemy.sql.expression.Insert

        """
        return self.table.insert()

    def delete(self):
        """Convenience method

        :returns: a DELETE FROM on the join table

        :rtype: sqlalchemy.sql.expression.Delete

        """
        return self.table.delete()

    def update(self):
        """Convenience method

        :returns: an UPDATE on the join table

        :rtype: sqlalchemy.sql.expression.Update

        """
        return self.table.update()

    def values(
        self, item, assoc: Union[int, List[int]]
    ) -> List[Dict[str, int]]:
        """Get value-insertion or update mapping

        :param Union[DB_Base, int] item: the source item or its ID

        :param Union[int,List[int]] assoc: the association or associations to
          specify

        Using the `item` passed in, which may be an ORM object descended from
        :class:`~.DB_Base` or an :obj:`int`, construct a list of dictionaries
        mapping the join table's ID column names correctly onto the source item
        ID and the associated item ID(s).

        """

        item_id = item if type(item) == int else item.id
        try:
            i = iter(assoc)
            ins = [{self.source_id: item_id, self.assoc_id: val} for val in i]
        except TypeError:
            ins = [{self.source_id: item_id, self.assoc_id: assoc}]
        return ins

    def where_tuples(self, item_id: int, assoc: Union[int, List[int]]):
        """Get tuples suitable for use in an SQLAlchemy WHERE clause"""
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

    def insert_assoc(self, item_id: int, vals):
        return (
            self.insert()
            .prefix_with("IGNORE")
            .values(self.values(item_id, vals))
        )

    def delete_assoc(self, item_id: int, vals):
        return self.delete().where(
            tuple_(self.source_col, self.assoc_col).in_(
                self.where_tuples(item_id, vals)
            )
        )

    def update_assoc(self, item_id: int, assoc_id: int):
        return (
            self.update()
            .where(self.source_col == item_id)
            .values(**{self.assoc_id: assoc_id})
        )

    def select_ids_by_source_id(self, item_id: int):
        # not self.select() b/c we want the SQLA select()
        return select(self.assoc_col).where(self.source_col == item_id)
