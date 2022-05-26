"""Policy Configuration Adapters based on SQLAlchemy
-----------------------------

Policy-configuration source data adapters.

These adapter classes have been adjusted from their original form to use
SQLAlchemy.

"""
import logging
from chapps.config import config, CHAPPSConfig
from chapps.dbsession import (
    create_db_url,
    create_engine,
    sql_engine,
    sessionmaker,
    func,
    select,
)
from chapps.models import User, Domain, Email, Quota
from chapps import dbmodels
from contextlib import contextmanager
from typing import List, Dict, Union, Any

logger = logging.getLogger(__name__)  # pragma: no cover


class SQLAPolicyConfigAdapter:
    """Base class for policy config access

    Right now, all of the adapters use MariaDB, but this will change
    (as noted below).
    Non-database adapters could also be created, which might use a
    flat file, or a blockchain, or some sort of other API interaction,
    to be the source of policy data.

    Ideally there should be a second-level base class called something like
    `MariaDBPolicyConfigAdapter` which would hold all the SQL-specific stuff,
    but that would make a lot more sense if

      a) there were going to be a lot of weird, different adapters.  We may yet get there!
      b) there were anything else to put in the base class

    For now, however, this
    class serves to store instructions about how to create the **User** table,
    since they are used for everything, just about.

    """

    def __init__(
        self,
        *,
        cfg: CHAPPSConfig = None,
        db_host: str = None,
        db_port: int = None,
        db_name: str = None,
        db_user: str = None,
        db_pass: str = None,
        autocommit: bool = True,
    ):
        """
        :param str db_host: the hostname or IP address of the database server
        :param int db_port: the port number of the database server
        :param str db_name: the name of the database
        :param str db_user: the username for login
        :param str db_pass: the password for the user
        :param bool autocommit: defaults to True


        """
        self.config = cfg or config
        self.params = self.config.adapter
        self.host = db_host or self.params.db_host or "127.0.0.1"
        self.port = db_port or self.params.db_port or 3306
        self.user = db_user or self.params.db_user
        self.pswd = db_pass or self.params.db_pass
        self.db = db_name or self.params.db_name
        self.autocommit = autocommit
        kwargs = dict(
            user=self.user,
            password=self.pswd,
            host=self.host,
            port=int(self.port),
            database=self.db,
            autocommit=self.autocommit,
        )
        # specifically: use the global engine unless we were passed a config
        self.sql_engine = (
            create_engine(create_db_url(cfg)) if cfg else sql_engine
        )

    def finalize(self):
        """Session-based access closes at the end of the context, so no-op"""
        pass

    def _initialize_tables(self):
        """Set up required tables.

        The schemata for the tables are defined in :mod:`~.dbmodels`.  We can
        create everything in a stroke by simply invoking :func:`create_all` on
        the SQLAlchemy_ metadata_.

        .. _metadata: https://docs.sqlalchemy.org/en/14/tutorial/metadata.html#id1

        """
        DB_Base.metadata.create_all()


class SQLAQuotaAdapter(PolicyConfigAdapter):
    """An adapter for obtaining quota policy data from MariaDB
       using SQLAlchemy_

    """

    def quota_for_user(self, user: str) -> Union[int, None]:
        """Return the quota amount for an user account

        :param str user: the user's name

        """
        Session = sessionmaker(self.sql_engine)
        with Session() as sess:
            u = sess.execute(User.select_by_name(user)).scalar()
            return u.quota.quota


class MariaDBSenderDomainAuthAdapter(PolicyConfigAdapter):
    """An adapter to obtain sender domain authorization data from MariaDB"""

    def check_domain_for_user(self, user: str, domain: str) -> bool:
        """Returns True if the user is authorized to send for this domain

        :param str user: name of user
        :param str domain: name of domain

        """
        Session = sessionmaker(self.sql_engine)
        with Session() as sess:
            user_subselect = (
                select(User.id).where(User.name == user).scalar_subquery()
            )
            domain_subselect = (
                select(Domain.id)
                .where(Domain.name == domain)
                .scalar_subquery()
            )
            stmt = (
                select(dbmodels.domain_user)
                .where(dbmodels.domain_user.c.user_id == user_subselect)
                .where(dbmodels.domain_user.c.domain_id == domain_subselect)
            )
            res = sess.execute(stmt)
            return len(list(res.scalars()))

    def check_email_for_user(self, user: str, email: str) -> bool:
        """Returns True if the user is authorized to send as this email

        :param str user: name of user
        :param str email: email address

        """
        Session = sessionmaker(self.sql_engine)
        with Session() as sess:
            user_subselect = (
                select(User.id).where(User.name == user).scalar_subquery()
            )
            email_subselect = (
                select(Email.id).where(Email.name == email).scalar_subquery()
            )
            stmt = (
                select(dbmodels.email_user)
                .where(dbmodels.email_user.c.user_id == user_subselect)
                .where(dbmodels.email_user.c.email_id == email_subselect)
            )
            res = sess.execute(stmt)
            return len(list(res.scalars()))
