#!/usr/bin/env python3
"""CHAPPS database setup script"""
### This script reads the CHAPPS config and uses the database information contained therein
###   to initialize the database.  It should be idempotent, and safe to run against an existing
###   config database.

from chapps.adapter import MariaDBQuotaAdapter, MariaDBSenderDomainAuthAdapter

def setup_chapps_database():
    for adapter in [ MariaDBQuotaAdapter(), MariaDBSenderDomainAuthAdapter() ]:
        adapter._initialize_tables()

if __name__ == '__main__':
    setup_chapps_database()
