"""Tests of CHAPPS SQLAlchemy adapters module"""
from unittest.mock import call
import pytest
import MySQLdb as dbmodule  # for some error symbols, etc
from chapps.sqla_adapter import SQLAPolicyConfigAdapter


class Test_SQLAPolicyConfigAdapter:
    def test_install_schema(self, database_fixture, sqla_pc_adapter_fixture):
        sqla_pc_adapter_fixture._initialize_tables()

        cur = database_fixture
        cur.execute("SHOW TABLES")
        tables = [t[0] for t in cur.fetchall()]
        assert "users" in tables


class Test_SQLAQuotaAdapter:
    def test_initialize_tables_default(
        self, sqla_oqp_adapter_fixture, database_fixture
    ):
        """
        Verify that MDBQA's table initialization works properly
        """
        sqla_oqp_adapter_fixture._initialize_tables()

        cur = database_fixture
        cur.execute("SHOW TABLES")
        tables = [t[0] for t in cur.fetchall()]
        assert "quotas" in tables
        assert "quota_user" in tables
        cur.execute("SELECT COUNT(name) FROM quotas")
        assert cur.fetchone()[0] == 0

    def test_quota_for_user(
        self, populated_database_fixture, sqla_oqp_adapter_fixture
    ):
        """
        Verify that MDBQA.quota_for_user returns the expected quota for an email
        """
        quota = sqla_oqp_adapter_fixture.quota_for_user("ccullen@easydns.com")
        assert quota == 240

    def test_quota_for_nonexistent_user(
        self, populated_database_fixture, sqla_oqp_adapter_fixture
    ):
        """
        Verify that MDBQA.quota_for_user returns None when the email is not found in the database.
        """
        quota = sqla_oqp_adapter_fixture.quota_for_user(
            "nonexistent@chapps.io"
        )
        assert quota == None


class Test_SQLASenderDomainAuthAdapter:
    def test_initialize_tables(
        self, sqla_sda_adapter_fixture, database_fixture
    ):
        """
        Verify that MDBSDAA's table initialization works properly
        """
        sqla_sda_adapter_fixture._initialize_tables()

        cur = database_fixture  # adapter_fixture.conn.cursor()
        cur.execute("SHOW TABLES")
        tables = [t[0] for t in cur.fetchall()]
        assert "domains" in tables
        assert "domain_user" in tables

    def test_check_domain_for_user(
        self, sqla_sda_adapter_fixture, populated_database_fixture
    ):
        """GIVEN a user has an entry in the database
           WHEN  that user tries to send an email for a domain they are linked to
           THEN  return a True result
        """
        assert sqla_sda_adapter_fixture.check_domain_for_user(
            "ccullen@easydns.com", "chapps.io"
        )

    def test_check_email_for_user(
        self, sqla_sda_adapter_fixture, populated_database_fixture
    ):
        assert sqla_sda_adapter_fixture.check_email_for_user(
            "ccullen@easydns.com", "caleb@chapps.com"
        )

    def test_check_domain_for_unauth_user(
        self, sqla_sda_adapter_fixture, populated_database_fixture
    ):
        """GIVEN a user has an entry in the database
           WHEN  that user tries to send an email for a domain they are not linked to
           THEN  return a False result
        """
        assert not sqla_sda_adapter_fixture.check_domain_for_user(
            "ccullen@easydns.com", "example.com"
        )

    def test_check_domain_for_nonexistent_user(
        self, sqla_sda_adapter_fixture, populated_database_fixture
    ):
        """GIVEN a user has no entry in the database
           WHEN  that user tries to send an email for any domain
           THEN  return a False result
        """
        assert not sqla_sda_adapter_fixture.check_domain_for_user(
            "nonexistent@example.com", "chapps.io"
        )
