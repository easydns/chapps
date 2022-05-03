"""
Adapters
--------

Policy-configuration source data adapters.

All of these currently interface to MariaDB as a fairly low level.
A change is planned to convert all of this to use SQLAlchemy.

"""
import mariadb

# import re ### needed if implementing domain_re_for_user()
import logging
from chapps.config import config
from contextlib import contextmanager
from typing import List

logger = logging.getLogger(__name__)  # pragma: no cover


class PolicyConfigAdapter:
    """Base class for DB adapters for policy config parameter access"""

    user_table = (
        "CREATE TABLE IF NOT EXISTS users ("  # pragma: no cover
        "id BIGINT AUTO_INCREMENT PRIMARY KEY,"
        "name VARCHAR(128) UNIQUE NOT NULL"
        ")"
    )
    """SQL query used to create the **user** table."""
    userid_query = "SELECT id FROM users WHERE name = %(user)s"
    """
    SQL query for obtaining the ID of a **user**.  These queries
    will go away when the older codebase is adapted to use SQLAlchemy
    """

    def __init__(
        self,
        *,
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
        self.host = db_host or config.adapter.db_host or "127.0.0.1"
        self.port = db_port or config.adapter.db_port or 3306
        self.user = db_user or config.adapter.db_user
        self.pswd = db_pass or config.adapter.db_pass
        self.db = db_name or config.adapter.db_name
        self.autocommit = autocommit
        kwargs = dict(
            user=self.user,
            password=self.pswd,
            host=self.host,
            port=int(self.port),
            database=self.db,
            autocommit=self.autocommit,
        )
        self.conn = mariadb.connect(**kwargs)

    def finalize(self):
        """Close the database connection."""
        self.conn.close()

    def _initialize_tables(self):
        """Set up required tables.

        Everything requires User records, so those tables are created here.

        """
        cur = self.conn.cursor()
        cur.execute(self.user_table)
        cur.close()

    @contextmanager
    def adapter_context(self):
        """Database connection context manager.

        This method is meant to be used as a context manager, like so:

        .. code:: python

          with someadapter.adapter_context() as cur:
              cur.execute(some_sql)

        The context manager closes the cursor once the context ends.
        """
        cur = self.conn.cursor()
        try:
            yield cur
        finally:
            cur.close()


class MariaDBQuotaAdapter(PolicyConfigAdapter):
    """An adapter for obtaining quota policy data from MariaDB

    .. admonition:: SQL constants are deprecated.

       All of the SQL statement constant strings defined in this class are
       deprecated.  In a future version, all of this logic will be accomplished
       using SQLAlchemy.

    """

    quota_table = (
        "CREATE TABLE IF NOT EXISTS quotas ("  # pragma: no cover
        "id BIGINT AUTO_INCREMENT PRIMARY KEY,"
        "name VARCHAR(32) UNIQUE NOT NULL,"
        "quota BIGINT UNIQUE NOT NULL"
        ")"
    )
    """SQL statement for creating the **Quota** table."""
    join_table = (
        "CREATE TABLE IF NOT EXISTS quota_user ("  # pragma: no cover
        "quota_id BIGINT NOT NULL,"
        "user_id BIGINT NOT NULL PRIMARY KEY,"
        "CONSTRAINT fk_user_quota"
        " FOREIGN KEY (user_id) REFERENCES users (id)"
        " ON DELETE CASCADE"
        " ON UPDATE RESTRICT,"
        "CONSTRAINT fk_quota"
        " FOREIGN KEY (quota_id) REFERENCES quotas (id)"
        " ON DELETE CASCADE"
        " ON UPDATE CASCADE"  # allow replacement of quota defs
        ")"
    )
    """SQL statement for creating the join table between **Quota** and **User** tables."""
    basic_quotas = (
        "INSERT INTO quotas ( name, quota ) VALUES "  # pragma: no cover
        "('10eph', 240),"
        "('50eph', 1200),"
        "('200eph', 4800)"
    )
    """Doubly deprecated insert statement for creating basic quotas."""
    quota_query = (
        "SELECT quota FROM quotas WHERE id = ("  # pragma: no cover
        "SELECT quota_id FROM quota_user AS j"
        " LEFT JOIN users AS u ON j.user_id = u.id"
        " WHERE u.name = %(user)s"
        ")"
    )
    """SQL query for selecting a **Quota**'s ``quota`` value for a named **User**."""
    quota_map_query = (
        "SELECT u.name AS user, p.quota FROM quotas AS p"  # pragma: no cover
        " LEFT JOIN quota_user AS j ON p.id = j.quota_id"
        " LEFT JOIN users AS u ON j.user_id = u.id"
    )
    """SQL query for selecting a list of users and their quotas."""
    quota_map_where = "WHERE u.name IN ({srch})"  # pragma: no cover

    def _initialize_tables(self, *, defquotas=False):
        super()._initialize_tables()
        cur = self.conn.cursor()
        cur.execute(self.quota_table)
        cur.execute(self.join_table)
        if defquotas:
            cur.execute("SELECT COUNT(name) FROM quotas")
            if cur.fetchone()[0] == 0:
                cur.execute(self.basic_quotas)
        cur.close()

    def quota_for_user(self, user):
        """Return the quota for an user account"""
        cur = self.conn.cursor()
        cur.execute(self.quota_query, dict(user=user))
        try:
            res = cur.fetchone()[0]
        except TypeError:  # generally meaning no result; we could log this
            res = None
        except mariadb.Error as e:  # pragma: no cover
            logger.error(e)
            res = None
        finally:
            cur.close()
        return res

    def _quota_search(self, users=[]):
        cur = self.conn.cursor()
        if len(users) == 0:
            query = self.quota_map_query
            cur.execute(query)
        else:
            query = self.quota_map_query + " " + self.quota_map_where
            srch = str(users)[
                1:-1
            ]  # produces a string suitable for SQL "IN ()"
            cur.execute(query.format(srch=srch))
        return cur.fetchall()

    def quota_dict(self, users=[]):
        """Return a dict which maps users onto their quotas"""
        rows = self._quota_search(users)
        res = {r[0]: r[1] for r in rows}
        return res

    def quota_map(self, func: callable, users: List[str] = []):
        """Map a callable over a set of users and their quotas

        :param callable func: A callable which will be passed (username, quota
          amount) for each user in the result

        :param List[str] users: Optional limiting list of usernames

        Provide a function to execute over each user and its quota.  Use this
        to directly wire the database-loading logic to the Redis-population
        logic.

        """
        if not callable(func):
            raise ValueError(
                "The first non-self argument must be a callable which accepts the user and quota as arguments, in that order."
            )
        rows = self._quota_search(users)
        res = []
        for row in rows:
            res.append(func(row[0], row[1]))
        return res


class MariaDBSenderDomainAuthAdapter(PolicyConfigAdapter):
    """A class for adapting to MariaDB for sender domain authorization data"""

    domain_table = (
        "CREATE TABLE IF NOT EXISTS domains ("  # pragma: no cover
        "id BIGINT AUTO_INCREMENT PRIMARY KEY,"
        "name VARCHAR(64) UNIQUE NOT NULL"
        ")"
    )
    domain_join_table = (
        "CREATE TABLE IF NOT EXISTS domain_user ("  # pragma: no cover
        "domain_id BIGINT NOT NULL,"
        "user_id BIGINT NOT NULL,"
        "PRIMARY KEY (domain_id, user_id),"  # comp. primary key allows more than one user per domain
        "CONSTRAINT fk_user_domain"
        " FOREIGN KEY (user_id) REFERENCES users (id)"
        " ON DELETE CASCADE"
        " ON UPDATE RESTRICT,"
        "CONSTRAINT fk_domain"
        " FOREIGN KEY (domain_id) REFERENCES domains (id)"
        " ON DELETE CASCADE"
        " ON UPDATE CASCADE"  # allow replacement of domain defs
        ")"
    )
    email_table = (
        "CREATE TABLE IF NOT EXISTS emails ("
        "id BIGINT AUTO_INCREMENT PRIMARY KEY,"
        "name VARCHAR(128) UNIQUE NOT NULL"
        ")"
    )
    email_join_table = (
        "CREATE TABLE IF NOT EXISTS email_user ("
        "email_id BIGINT NOT NULL,"
        "user_id BIGINT NOT NULL,"
        "PRIMARY KEY (email_id, user_id),"
        "CONSTRAINT fk_user_email"
        " FOREIGN KEY (user_id) REFERENCES users (id)"
        " ON DELETE CASCADE"
        " ON UPDATE RESTRICT,"
        "CONSTRAINT fk_email"
        " FOREIGN KEY (email_id) REFERENCES emails (id)"
        " ON DELETE CASCADE"
        " ON UPDATE CASCADE"
        ")"
    )
    domain_query = (
        "SELECT d.name FROM domains AS d"  # pragma: no cover
        " WHERE id = ("
        "SELECT domain_id FROM domain_user AS j"
        " LEFT JOIN users AS u ON j.user_id = u.id"
        " WHERE u.name = %(user)s"
        ")"
    )
    domain_map_query = (
        "SELECT u.name AS user, d.name AS domain FROM domains AS d"  # pragma: no cover
        " LEFT JOIN domain_user AS j ON p.id = j.domain_id"
        " LEFT JOIN users AS u ON j.user_id = u.id"
    )
    domain_map_where = "WHERE user IN ({srch})"  # pragma: no cover
    check_domain_query = (
        "SELECT COUNT(d.name) FROM domains AS d"
        " LEFT JOIN domain_user AS j ON d.id = j.domain_id"
        " LEFT JOIN users AS u ON u.id = j.user_id"
        " WHERE d.name = '{domain}' AND u.name = '{user}'"
    )
    check_email_query = (
        "SELECT COUNT(e.name) FROM emails AS e"
        " LEFT JOIN email_user AS j on e.id = j.email_id"
        " LEFT JOIN users AS u ON u.id = j.user_id"
        " WHERE e.name = '{email}' AND u.name = '{user}'"
    )

    def _initialize_tables(self, *args, **kwargs):
        super()._initialize_tables()
        cur = self.conn.cursor()
        cur.execute(self.domain_table)
        cur.execute(self.email_table)
        cur.execute(self.domain_join_table)
        cur.execute(self.email_join_table)
        cur.close()

    def check_domain_for_user(self, user, domain):
        """Returns true if the user is authorized to send for this domain"""
        cur = self.conn.cursor()
        cur.execute(self.check_domain_query.format(user=user, domain=domain))
        result = cur.fetchone()[0]  ### returns 1 if a domain matched, 0 if not
        cur.close()
        return result

    def check_email_for_user(self, user, email):
        """Returns true if the user is authorized to send as this email"""
        cur = self.conn.cursor()
        cur.execute(self.check_email_query.format(user=user, email=email))
        result = cur.fetchone()[0]
        cur.close()
        return result

    ### These methods would provide a similar functionality profile to the above
    ###     but as yet, none of that code is being used either, so these are left
    ###     as a suggestion for future expansion, as needed
    def _domain_search(self, users=[]):
        """Return a set of rows, either for specified users or all users"""
        raise NotImplementedError

    def domains_for_user(self, user):
        """Return a list of domains the user is authorized to send from"""
        raise NotImplementedError

    def domain_re_for_user(self, user):
        """Returns a regular expression useful for detecting a user's domains"""
        raise NotImplementedError

    def domain_map(self, func, users=[]):
        """Pass in a closure which accepts (user, domain); useful for prepopulating Redis"""
        raise NotImplementedError
