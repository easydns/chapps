"""SQLAlchemy DB session global setup"""
from sqlalchemy import create_engine
from chapps.config import config
from urllib.parse import quote_plus

DIALECT_MAP = dict(
    mariadb="mariadb+pymysql",
    mysql="mysql+pymysql",
)

def create_db_url(cfg=None):
    cfg = cfg or config
    adapter = cfg.adapter
    if adapter.adapter not in DIALECT_MAP:
        raise ValueError(
            (
                "Configured database adapter must be one of:"
                f"{', '.join([repr(v) for v in DIALECT_MAP.keys()])}"
            )
        )
    password = quote_plus(adapter.db_pass)
    dialect = DIALECT_MAP[adapter.adapter]
    username = adapter.db_user
    host = adapter.db_host or '127.0.0.1'
    port = adapter.db_port or '3306'
    database = adapter.db_name
    return f"{dialect}://{username}:{password}@{host}:{port}/{database}"


sql_engine = create_engine(create_db_url())
