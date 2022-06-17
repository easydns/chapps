#!/usr/bin/env python3
"""CHAPPS database setup script"""
### This script reads the CHAPPS config and uses the database information contained therein
###   to initialize the database.  It should be idempotent, and safe to run against an existing
###   config database.

from chapps.dbsession import sql_engine
from chapps.dbmodels import DB_Base


def setup_chapps_database():
    DB_Base.metadata.create_all(sql_engine)


if __name__ == "__main__":
    setup_chapps_database()
