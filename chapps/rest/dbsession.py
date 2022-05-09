"""SQLAlchemy DB session global setup"""
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from chapps.config import config

DIALECT_MAP = dict(mariadb="mysql", mysql="mysql")
"""Map dialects to drivers, for DBI URL construction"""


def create_db_url(cfg=None) -> URL:
    """Create a DBI URL for initializing :mod:`SQLAlchemy`

    :param ~chapps.config.CHAPPSConfig cfg: optional config override

    :returns: `URL <https://docs.sqlalchemy.org/en/14/core/engines.html#sqlalchemy.engine.URL>`_ instance for use in accessing the database

    :rtype: sqlalchemy.engine.URL

    """
    cfg = cfg or config
    adapter = cfg.adapter
    if adapter.adapter not in DIALECT_MAP:
        raise ValueError(
            (
                "Configured database adapter must be one of:"
                f"{', '.join([repr(v) for v in DIALECT_MAP.keys()])}"
            )
        )
    dialect = DIALECT_MAP[adapter.adapter]
    creds = dict(
        password=adapter.db_pass,  # auto encoded
        username=adapter.db_user,
        host=adapter.db_host or "127.0.0.1",
        port=adapter.db_port or "3306",
        database=adapter.db_name,
    )
    return URL.create(dialect, **creds)


sql_engine = create_engine(create_db_url())
"""a package-global SQL engine"""
