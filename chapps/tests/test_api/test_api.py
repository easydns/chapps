"""Tests of the REST API.  Not called test_rest obvs"""
import pytest
import pudb
import chapps.config


class Test_Users_API:
    """Tests of the User CRUD API"""

    def test_get_user(self, fixed_time, testing_api_client, populated_database_fixture):
        response = testing_api_client.get("/users/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [{"id": 1, "name": "chapps.io"}],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    def test_list_users(self, fixed_time, testing_api_client):
        response = testing_api_client.get("/users/")
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {"id": 1, "name": "ccullen@easydns.com"},
                {"id": 2, "name": "somebody@chapps.io"},
                {"id": 3, "name": "bigsender@chapps.io"},
            ],
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_create_user(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        # pudb.set_trace()
        response = testing_api_client.post(
            "/users/", json={"name": "schmo1@chapps.io", "domains": [], "quota": 0}
        )
        assert response.status_code == 201
        assert response.json() == {
            "response": {"id": 4, "name": "schmo1@chapps.io"},
            "domains": None,
            "quota": None,
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_create_user_with_associations(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        # pudb.set_trace()
        response = testing_api_client.post(
            "/users/", json={"name": "schmo1@chapps.io", "domains": [1], "quota": 1}
        )
        assert response.status_code == 201
        assert response.json() == {
            "response": {"id": 4, "name": "schmo1@chapps.io"},
            "domains": [{"id": 1, "name": "chapps.io"}],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }


class Test_Domains_API:
    """Tests of the Domain CRUD API"""

    def test_get_domain(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.get("/domains/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "chapps.io"},
            "timestamp": fixed_time,
            "users": [
                {"id": 1, "name": "ccullen@easydns.com"},
                {"id": 2, "name": "somebody@chapps.io"},
                {"id": 3, "name": "bigsender@chapps.io"},
            ],
            "version": "CHAPPS v0.4",
        }

    def test_list_domains(self, fixed_time, testing_api_client):
        response = testing_api_client.get("/domains/")
        assert response.status_code == 200
        assert response.json() == {
            "response": [{"id": 1, "name": "chapps.io"}],
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_create_domain(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        # pudb.set_trace()
        response = testing_api_client.post(
            "/domains/", json={"name": "easydns.com", "users": []}
        )
        assert response.status_code == 201
        assert response.json() == {
            "response": {"id": 2, "name": "easydns.com"},
            "users": None,
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(3)
    def test_create_domain_with_users(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.post(
            "/domains/", json={"name": "easydns.com", "users": [1]}
        )
        assert response.status_code == 201
        assert response.json() == {
            "response": {"id": 2, "name": "easydns.com"},
            "timestamp": fixed_time,
            "users": [{"id": 1, "name": "ccullen@easydns.com"}],
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_delete_domain(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.delete("/domains/", json={1})
        assert response.status_code == 200
        assert response.json() == {
            "status": True,
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }


class Test_Quotas_API:
    """Tests of the Quota CRUD API"""

    def test_get_quota(self, fixed_time, testing_api_client):
        response = testing_api_client.get("/quotas/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    def test_list_quotas(self, fixed_time, testing_api_client):
        response = testing_api_client.get("/quotas/")
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {"id": 1, "name": "10eph", "quota": 240},
                {"id": 2, "name": "50eph", "quota": 1200},
                {"id": 3, "name": "200eph", "quota": 4800},
            ],
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_create_quota(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.post(
            "/quotas/", json={"name": "400eph", "quota": 9600}
        )
        assert response.status_code == 201
        assert response.json() == {
            "response": {"id": 4, "name": "400eph", "quota": 9600},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
