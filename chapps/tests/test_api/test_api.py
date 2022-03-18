"""Tests of the REST API.  Not called test_rest obvs"""
import pytest
import chapps.config


class Test_Users_API:
    """Tests of the User CRUD API"""

    def test_get_user(self, fixed_time, testing_api_client):
        response = testing_api_client.get("/users/1")
        assert response.status_code == 200
        assert response.json() == {
            "domains": [
                {"id": 1, "name": "chapps.io"},
                {"id": 2, "name": "easydns.com"},
            ],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }


class Test_Domains_API:
    """Tests of the Domain CRUD API"""

    def test_get_domain(self, fixed_time, testing_api_client):
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
