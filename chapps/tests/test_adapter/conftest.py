"""Fixtures for testing CHAPPS adapters module"""
from unittest.mock import Mock
import pytest
from pytest import fixture
import MySQLdb as dbmodule
from chapps.adapter import (
    PolicyConfigAdapter,
    MariaDBQuotaAdapter,
    MariaDBSenderDomainAuthAdapter,
    MariaDBInboundFlagsAdapter,
)
from chapps.tests.test_sqla_adapter.conftest import (
    no_options_domain,
    greylisting_domain,
    spf_domain,
    enforcing_both_domain,
    _populated_database_fixture,
    _populated_database_fixture_with_extras,
    _populated_database_fixture_with_breakage,
)


@fixture
def mock_dbmodule(monkeypatch):
    """Patch the mariadb module's connect function with a mock"""
    monkeypatch.setattr(
        dbmodule, "connect", Mock(return_value="mock connection")
    )


def _adapter_fixture(fixtype):
    adapter = fixtype(
        db_host="localhost",
        db_name="chapps_test",
        db_user="chapps_test",
        db_pass="screwy%pass${word}",
    )
    return adapter


def _database_fixture(finalizing_adapter):
    cur = finalizing_adapter.conn.cursor()
    cur.execute("DROP DATABASE IF EXISTS chapps_test")
    cur.execute("CREATE DATABASE IF NOT EXISTS chapps_test")
    cur.execute("USE chapps_test")
    yield cur
    cur.close()


@fixture
def base_adapter_fixture():
    return _adapter_fixture(PolicyConfigAdapter)


@fixture
def finalizing_pcadapter(base_adapter_fixture):
    yield base_adapter_fixture
    base_adapter_fixture.finalize()


@fixture
def database_fixture(finalizing_pcadapter):
    yield from _database_fixture(finalizing_pcadapter)


@fixture
def mdbqadapter_fixture():
    return _mdbqadapter_fixture()


def _mdbqadapter_fixture():
    return _adapter_fixture(MariaDBQuotaAdapter)


@fixture
def finalizing_mdbqadapter(mdbqadapter_fixture):
    yield mdbqadapter_fixture
    mdbqadapter_fixture.finalize()


@fixture
def mdbsdaadapter_fixture():
    return _adapter_fixture(MariaDBSenderDomainAuthAdapter)


@fixture
def mdbifadapter_fixture():
    return _adapter_fixture(MariaDBInboundFlagsAdapter)


@fixture
def finalizing_mdbsdaadapter(mdbsdaadapter_fixture):
    yield mdbsdaadapter_fixture
    mdbsdaadapter_fixture.finalize()


@fixture
def finalizing_mdbifadapter(mdbifadapter_fixture):
    yield mdbifadapter_fixture
    mdbifadapter_fixture.finalize()


@fixture
def test_emails():
    return [
        "ccullen@easydns.com",
        "somebody@chapps.io",
        "nonexistent@chapps.io",
    ]


# def _populated_database_fixture(database_fixture):
#     basic_quotas = (
#         "INSERT INTO quotas ( name, quota ) VALUES "
#         "('10eph', 240),"
#         "('50eph', 1200),"
#         "('200eph', 4800)"
#     )
#     test_users = [
#         "BEGIN;",
#         "INSERT INTO users ( name ) VALUES ( 'ccullen@easydns.com' );",
#         "SELECT LAST_INSERT_ID() INTO @userid;",
#         "INSERT INTO domains ( name, greylist, check_spf )"
#         " VALUES ( 'chapps.io', 1, 1 );",
#         "SELECT LAST_INSERT_ID() INTO @chappsid;",
#         "INSERT INTO emails (name) VALUES ( 'caleb@chapps.com' );",
#         "SELECT LAST_INSERT_ID() INTO @emailid;",
#         (
#             "INSERT INTO quota_user ( quota_id, user_id ) VALUES"
#             " ( (SELECT id FROM quotas WHERE name = '10eph'), @userid );"
#         ),
#         (
#             "INSERT INTO domain_user ( domain_id, user_id ) VALUES"
#             " ( @chappsid, @userid );"
#         ),
#         (
#             "INSERT INTO email_user ( email_id, user_id ) VALUES"
#             " ( @emailid, @userid );"
#         ),
#         "INSERT INTO users (name) VALUES ('somebody@chapps.io');",
#         "SELECT LAST_INSERT_ID() INTO @userid;",
#         (
#             "INSERT INTO quota_user ( quota_id, user_id ) VALUES"
#             " ( (SELECT id FROM quotas WHERE name = '50eph'), @userid );"
#         ),
#         (
#             "INSERT INTO domain_user ( domain_id, user_id ) VALUES"
#             " ( @chappsid, @userid );"
#         ),
#         "INSERT INTO users (name) VALUES ('bigsender@chapps.io');",
#         "SELECT LAST_INSERT_ID() INTO @userid;",
#         (
#             "INSERT INTO quota_user ( quota_id, user_id ) VALUES"
#             " ( (SELECT id FROM quotas WHERE name = '200eph'), @userid );"
#         ),
#         (
#             "INSERT INTO domain_user ( domain_id, user_id ) VALUES"
#             " ( @chappsid, @userid );"
#         ),
#         "COMMIT;",
#     ]
#     count_users = "SELECT COUNT(name) FROM users;"
#     cur = database_fixture
#     for policy in [MariaDBQuotaAdapter, MariaDBSenderDomainAuthAdapter]:
#         _adapter_fixture(policy)._initialize_tables()
#     cur.execute(count_users)
#     usercount = cur.fetchone()[0]
#     if usercount == 0:
#         cur.execute(basic_quotas)
#         for stmt in test_users:
#             cur.execute(stmt)
#     return cur
#     # yield cur
#     # could drop and re-create the DB here, but we do that elsewhere


# def _populated_database_fixture_with_extras(database_fixture):
#     cur = _populated_database_fixture(database_fixture)
#     extra_domains = (
#         "INSERT INTO domains (name, greylist, check_spf) VALUES"
#         " ('easydns.com', 0, 1),"
#         " ('easydns.net', 1, 0),"
#         " ('easydns.org', 0, 0);"
#     )
#     extra_users = (
#         "INSERT INTO users (name) VALUES "
#         "('schmo1@chapps.io'), ('schmo2@chapps.io');"
#     )
#     extra_emails = (
#         "INSERT INTO emails (name) VALUES ('roleaccount@chapps.com'),"
#         " ('admin@chapps.com'), ('abuse@chapps.com'), ('info@chapps.com');"
#     )

#     extra_assoc = [
#         (
#             "INSERT INTO domain_user (domain_id, user_id) VALUES"
#             " (2, 3), (1, 5), (2, 5), (3, 5), (4, 5);"
#         ),
#         ("INSERT INTO quota_user (quota_id, user_id) VALUES (1, 5);"),
#         (
#             "INSERT INTO email_user (email_id, user_id) VALUES"
#             " (2, 2), (2, 3), (2, 4), (2, 5),"
#             " (3, 3), (4, 3), (5, 3);"
#         ),
#     ]
#     cur.execute(extra_domains)
#     cur.execute(extra_users)
#     cur.execute(extra_emails)
#     for q in extra_assoc:
#         cur.execute(q)
#     return cur


# def _populated_database_fixture_with_breakage(database_fixture):
#     cur = _populated_database_fixture_with_extras(database_fixture)
#     breakage = (
#         "DELETE FROM quota_user WHERE user_id = 1;"
#         "DELETE FROM users WHERE id = 2;"
#     )
#     cur.execute(breakage)
#     return cur


@fixture
def populated_database_fixture(database_fixture):
    return _populated_database_fixture(database_fixture)


@fixture
def populated_database_fixture_with_extras(database_fixture):
    return _populated_database_fixture_with_extras(database_fixture)


@fixture
def populated_database_fixture_with_breakage(database_fixture):
    return _populated_database_fixture_with_breakage(database_fixture)


@fixture
def mock_mapping():
    m = Mock(name="mapping", ident="mock_mapping_func", return_value=True)
    return m
