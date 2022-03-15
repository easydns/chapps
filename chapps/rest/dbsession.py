"""SQLAlchemy DB session global setup"""
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from chapps.config import config

DIALECT_MAP = dict(
    mariadb="mysql",
    mysql="mysql",
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
    dialect = DIALECT_MAP[adapter.adapter]
    creds = dict(
        password=adapter.db_pass,           # auto encoded
        username=adapter.db_user,
        host=adapter.db_host or '127.0.0.1',
        port=adapter.db_port or '3306',
        database=adapter.db_name,
    )
    return URL.create(dialect, **creds)


sql_engine = create_engine(create_db_url())
