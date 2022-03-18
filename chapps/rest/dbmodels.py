"""SQLAlchemy ORM Models to correspond to Pydantic models for API"""
from sqlalchemy import Column, Integer, String, ForeignKey, Table, select
from sqlalchemy.orm import declarative_base, relationship, backref, DeclarativeMeta

# declare subclass of the SQLAlchemy DeclarativeMeta class
# in order to attach custom routines to the ORM objects
class DB_Customizations(DeclarativeMeta):
    """Metaclass for adding custom code to ORM models"""
    def select_by_id(cls, id: int):
        return select(cls).where(cls.id==id)

# declare DB model base class
DB_Base = declarative_base(metaclass=DB_Customizations)
"""DB_Base serves as the base of all ORM classes"""

quota_user = Table(
    'quota_user',
    DB_Base.metadata,
    Column(
        'user_id',
        ForeignKey(
            'users.id',
            ondelete='CASCADE',
            onupdate='RESTRICT',
        ),
        primary_key=True,
    ),
    Column(
        'quota_id',
        ForeignKey(
            'quotas.id',
            ondelete='CASCADE',
            onupdate='CASCADE',
        ),
        nullable=False,
    )
)
domain_user = Table(
    'domain_user',
    DB_Base.metadata,
    Column(
        'user_id',
        ForeignKey(
            'users.id',
            ondelete='CASCADE',
            onupdate='RESTRICT',
        ),
        primary_key=True,
    ),
    Column(
        'domain_id',
        ForeignKey(
            'domains.id',
            ondelete='CASCADE',
            onupdate='CASCADE',
        ),
        primary_key=True,
    )
)

class Quota(DB_Base):
    """ORM Model for quota definitions"""
    __tablename__ = 'quotas'

    id = Column(Integer, primary_key=True)
    name = Column(String(32), unique=True)
    quota = Column(Integer, unique=True)

    def __repr__(self):
        return f"Quota[ORM](id={self.id!r}, name={self.name!r}, quota={self.quota!r})"

class Domain(DB_Base):
    """ORM Model for domain definitions"""
    __tablename__ = 'domains'

    id = Column(Integer,primary_key=True)
    name = Column(String(64))

    def __repr__(self):
        return f"Domain[ORM](id={self.id!r}, name={self.name!r})"

class User(DB_Base):
    """ORM model for user entities within CHAPPS"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    name = Column(String(128), unique=True)
    quota = relationship(
        Quota,
        secondary=quota_user,   # using m2m mainly for optimization
        backref="users",        # wants to be efficient and non-eager
        passive_deletes=True,   # prevent loading during deletion
        single_parent=True,     # only one association to quota
        uselist=False,          # one quota per user
        primaryjoin=id == quota_user.c.user_id,
        secondaryjoin=Quota.id == quota_user.c.quota_id,
    )
    domains = relationship(
        Domain,
        secondary=domain_user,  # really m2m
        backref="users",        # reverse associate
        order_by=Domain.id,     # order by id
        passive_deletes=True,   # protect domains
    )

    def __repr__(self):
        return f"User[ORM](id={self.id!r}, name={self.name!r})"

### for testing purposes:
import urllib.parse
from sqlalchemy import select, text, create_engine, insert
from sqlalchemy.orm import Session
password = urllib.parse.quote_plus('screwy%pass${word}')
engine = create_engine(f"mariadb+pymysql://chapps_test:{password}@localhost/chapps_test")
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
