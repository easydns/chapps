"""Tests of CHAPPS adapters module"""
from unittest.mock import call
import pytest
import mariadb
from chapps.adapter import (
    PolicyConfigAdapter,
    MariaDBQuotaAdapter,
    MariaDBSenderDomainAuthAdapter,
)


class Test_PolicyConfigAdapter:
    def test_adapter_superclass(self, mock_mariadb):
        """
        Verify that the adapter stores instance data
        and attempts to open a database connection.
        """
        adapter = PolicyConfigAdapter(
            db_host="mockhost",
            db_name="mockdb",
            db_user="mockuser",
            db_pass="mockpass",
        )

        assert adapter.user == "mockuser"
        assert adapter.db == "mockdb"
        assert adapter.host == "mockhost"
        assert mariadb.connect.call_args.kwargs == {
            "user": "mockuser",
            "host": "mockhost",
            "port": 3306,
            "database": "mockdb",
            "password": "mockpass",
            "autocommit": True,
        }

    def test_create_user_table(self, database_fixture, finalizing_pcadapter):
        finalizing_pcadapter._initialize_tables()

        cur = database_fixture
        cur.execute("SHOW TABLES")
        tables = [t[0] for t in cur.fetchall()]
        assert "users" in tables


class Test_MariaDBQuotaAdapter:
    def test_initialize_tables_default(
        self, finalizing_mdbqadapter, database_fixture
    ):
        """
        Verify that MDBQA's table initialization works properly
        """
        finalizing_mdbqadapter._initialize_tables()

        cur = database_fixture  # adapter_fixture.conn.cursor()
        cur.execute("SHOW TABLES")
        tables = [t[0] for t in cur.fetchall()]
        assert "quotas" in tables
        assert "quota_user" in tables
        cur.execute("SELECT COUNT(name) FROM quotas")
        assert cur.fetchone()[0] == 0

    def test_initialize_tables_with_quotas(
        self, finalizing_mdbqadapter, database_fixture
    ):
        """
        Verify that MDBQA's table initialization works properly
        """
        finalizing_mdbqadapter._initialize_tables(defquotas=True)

        cur = database_fixture  # adapter_fixture.conn.cursor()
        cur.execute("SHOW TABLES")
        tables = [t[0] for t in cur.fetchall()]
        assert "quotas" in tables
        assert "quota_user" in tables
        cur.execute("SELECT COUNT(name) FROM quotas")
        assert cur.fetchone()[0] == 3

    def test_finalize(self, mdbqadapter_fixture):
        """
        Verify that MDBQA's finalize routine closes the database connection

        .. todo::

          refactor to superclass tests

        """
        mdbqadapter_fixture.finalize()
        with pytest.raises(mariadb.Error):
            assert mdbqadapter_fixture.conn.cursor()

    def test_quota_for_user(
        self, populated_database_fixture, finalizing_mdbqadapter
    ):
        """
        Verify that MDBQA.quota_for_user returns the expected quota for an email
        """
        quota = finalizing_mdbqadapter.quota_for_user("ccullen@easydns.com")
        assert quota == 240

    def test_quota_for_nonexistent_user(
        self, populated_database_fixture, finalizing_mdbqadapter
    ):
        """
        Verify that MDBQA.quota_for_user returns None when the email is not found in the database.
        """
        quota = finalizing_mdbqadapter.quota_for_user("nonexistent@chapps.io")
        assert quota == None

    def test_quota_dump(
        self, populated_database_fixture, finalizing_mdbqadapter
    ):
        """
        Verify that MDBQA._quota_search returns rows for all entries in the quota_user table if no list is specified
        """
        results = finalizing_mdbqadapter._quota_search()

        assert len(results) == 3  # curly-brace lists are sets
        assert {r[0] for r in results} == {
            "ccullen@easydns.com",
            "somebody@chapps.io",
            "bigsender@chapps.io",
        }
        assert {r[1] for r in results} == {240, 1200, 4800}

    def test_quota_search(
        self, populated_database_fixture, finalizing_mdbqadapter, test_emails
    ):
        """
        Verify that MDBQA._quota_search returns rows for all valid email addresses
        """
        results = finalizing_mdbqadapter._quota_search(test_emails)

        assert len(results) == 2  # curly-brace lists are sets
        assert {r[0] for r in results} == {
            "ccullen@easydns.com",
            "somebody@chapps.io",
        }
        assert {r[1] for r in results} == {240, 1200}

    def test_quota_search_accuracy(
        self, populated_database_fixture, finalizing_mdbqadapter, test_emails
    ):
        """
        Verify that MDBQA._quota_search produces accurate results
        """
        results = finalizing_mdbqadapter._quota_search(test_emails)

        for r in results:
            if r[0] == "ccullen@easydns.com":
                assert r[1] == 240
            if r[0] == "somebody@chapps.io":
                assert r[1] == 1200

    def test_MDBQA_quota_dict(
        self, populated_database_fixture, finalizing_mdbqadapter, test_emails
    ):
        """
        Verify that MDBQA.quota_dict returns a dict full of quotas
        """
        results = finalizing_mdbqadapter.quota_dict(test_emails)

        assert results == {
            "ccullen@easydns.com": 240,
            "somebody@chapps.io": 1200,
        }

    def test_quota_map(
        self,
        populated_database_fixture,
        finalizing_mdbqadapter,
        test_emails,
        mock_mapping,
    ):
        """
        Verify that MDBQA.quota_map() applies the function to all
        results from the query
        """
        results = finalizing_mdbqadapter.quota_map(
            mock_mapping,
            test_emails,  # the mock mapping function, which we can query
        )  # the emails to test with

        ### trivial assertion that the mock fired twice, giving its True
        assert results == [True, True]
        ### This asserts that the mock was actually called with the
        ###   expected arguments over the expected return dataset
        assert mock_mapping.mock_calls == [
            call("ccullen@easydns.com", 240),
            call("somebody@chapps.io", 1200),
        ]

    def test_quota_map_noncallable(
        self, populated_database_fixture, finalizing_mdbqadapter
    ):
        """
        Verify that when MDBQA.quota_map() is handed some non-callable
        as its first non-self argument, it will raise a ValueError
        """
        with pytest.raises(
            ValueError,
            match="must be a callable which accepts the user and quota as arguments",
        ):
            assert finalizing_mdbqadapter.quota_map(None)


class Test_MariaDBSenderDomainAuthAdapter:
    def test_initialize_tables(
        self, finalizing_mdbsdaadapter, database_fixture
    ):
        """
        Verify that MDBSDAA's table initialization works properly
        """
        finalizing_mdbsdaadapter._initialize_tables()

        cur = database_fixture  # adapter_fixture.conn.cursor()
        cur.execute("SHOW TABLES")
        tables = [t[0] for t in cur.fetchall()]
        assert "domains" in tables
        assert "domain_user" in tables

    def test_check_domain_for_user(
        self, finalizing_mdbsdaadapter, populated_database_fixture
    ):
        """GIVEN a user has an entry in the database
           WHEN  that user tries to send an email for a domain they are linked to
           THEN  return a True result
        """
        assert finalizing_mdbsdaadapter.check_domain_for_user(
            "ccullen@easydns.com", "chapps.io"
        )

    def test_check_email_for_user(
        self, finalizing_mdbsdaadapter, populated_database_fixture
    ):
        assert finalizing_mdbsdaadapter.check_email_for_user(
            "ccullen@easydns.com", "caleb@chapps.com"
        )

    def test_check_domain_for_unauth_user(
        self, finalizing_mdbsdaadapter, populated_database_fixture
    ):
        """GIVEN a user has an entry in the database
           WHEN  that user tries to send an email for a domain they are not linked to
           THEN  return a False result
        """
        assert not finalizing_mdbsdaadapter.check_domain_for_user(
            "ccullen@easydns.com", "example.com"
        )

    def test_check_domain_for_nonexistent_user(
        self, finalizing_mdbsdaadapter, populated_database_fixture
    ):
        """GIVEN a user has no entry in the database
           WHEN  that user tries to send an email for any domain
           THEN  return a False result
        """
        assert not finalizing_mdbsdaadapter.check_domain_for_user(
            "nonexistent@example.com", "chapps.io"
        )
