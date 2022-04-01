"""Tests of the REST API.  Not called test_rest obvs"""
import pytest
import pudb
import chapps.config
import time
from chapps.policy import TIME_FORMAT


class Test_API_Health:
    """Tests of the overall API"""

    def test_api_docs_render(self, testing_api_client):
        response = testing_api_client.get("/docs")
        assert response.status_code == 200


class Test_Users_API:
    """Tests of the User CRUD API"""

    @pytest.mark.timeout(2)
    def test_get_user(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.get("/users/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [{"id": 1, "name": "chapps.io"}],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
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
            "/users/",
            json={"name": "schmo1@chapps.io", "domains": [], "quota": 0},
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
            "/users/",
            json={"name": "schmo1@chapps.io", "domains": [1], "quota": 1},
        )
        assert response.status_code == 201
        assert response.json() == {
            "response": {"id": 4, "name": "schmo1@chapps.io"},
            "domains": [{"id": 1, "name": "chapps.io"}],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_delete_user(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.delete("/users/", json=[1])
        assert response.status_code == 200
        assert response.json() == {
            "response": "deleted",
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
        response = testing_api_client.get("/users/1")
        assert response.status_code == 404

    @pytest.mark.timeout(2)
    def test_update_user(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/users/",
            json=dict(user=dict(id=1, name="ccruller@easydonuts.com")),
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccruller@easydonuts.com"},
            "domains": None,
            "quota": None,
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_user_quota(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/users/",
            json=dict(user=dict(id=1, name="ccullen@easydns.com"), quota=2),
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": None,
            "quota": {"id": 2, "name": "50eph", "quota": 1200},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_user_domains(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/users/",
            json=dict(
                user=dict(id=1, name="ccullen@easydns.com"), domains=[1]
            ),
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [{"id": 1, "name": "chapps.io"}],
            "quota": None,
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_user_domains_empty(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/users/",
            json=dict(user=dict(id=1, name="ccullen@easydns.com"), domains=[]),
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": None,  # no value detected, no change, no value returned
            "quota": None,  # nothing provided, no change, no value returned
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_user_associations(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/users/",
            json=dict(
                user=dict(id=1, name="ccullen@easydns.com"),
                quota=2,
                domains=[1],
            ),
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [{"id": 1, "name": "chapps.io"}],
            "quota": {"id": 2, "name": "50eph", "quota": 1200},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_user_add_domains(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.put("/users/1/allow/", json=[2])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
        response = testing_api_client.get("/users/1")
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [
                {"id": 1, "name": "chapps.io"},
                {"id": 2, "name": "easydns.com"},
            ],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_user_remove_domains(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.put("/users/3/deny/", json=[1])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
        response = testing_api_client.get("/users/3")
        assert response.json() == {
            "response": {"id": 3, "name": "bigsender@chapps.io"},
            "domains": [{"id": 2, "name": "easydns.com"}],
            "quota": {"id": 3, "name": "200eph", "quota": 4800},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_user_set_quota(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.put("/users/1/quota/2")
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
        response = testing_api_client.get("/users/1")
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [{"id": 1, "name": "chapps.io"}],
            "quota": {"id": 2, "name": "50eph", "quota": 1200},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }


class Test_Domains_API:
    """Tests of the Domain CRUD API"""

    @pytest.mark.timeout(2)
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

    @pytest.mark.timeout(2)
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
        response = testing_api_client.delete("/domains/", json=[1])
        assert response.status_code == 200
        assert response.json() == {
            "response": "deleted",
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
        response = testing_api_client.get("/domains/1")
        assert response.status_code == 404
        response = testing_api_client.get("/users/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_domain(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/domains/", json=dict(domain=dict(id=1, name="crapps.io"))
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "crapps.io"},
            "timestamp": fixed_time,
            "users": None,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_domain_with_users(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/domains/",
            json=dict(domain=dict(id=1, name="chapps.io"), users=[2, 3]),
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "chapps.io"},
            "timestamp": fixed_time,
            "users": [
                {"id": 2, "name": "somebody@chapps.io"},
                {"id": 3, "name": "bigsender@chapps.io"},
            ],
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_domain_add_users(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.put("/domains/2/allow/", json=[2, 3])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
        response = testing_api_client.get("/users/2")
        assert response.json() == {
            "response": {"id": 2, "name": "somebody@chapps.io"},
            "domains": [
                {"id": 1, "name": "chapps.io"},
                {"id": 2, "name": "easydns.com"},
            ],
            "quota": {"id": 2, "name": "50eph", "quota": 1200},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
    def test_update_domain_remove_users(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.put("/domains/1/deny/", json=[3])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
        response = testing_api_client.get("/users/3")
        assert response.json() == {
            "response": {"id": 3, "name": "bigsender@chapps.io"},
            "domains": [{"id": 2, "name": "easydns.com"}],
            "quota": {"id": 3, "name": "200eph", "quota": 4800},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }


class Test_Quotas_API:
    """Tests of the Quota CRUD API"""

    @pytest.mark.timeout(2)
    def test_get_quota(self, fixed_time, testing_api_client):
        response = testing_api_client.get("/quotas/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    @pytest.mark.timeout(2)
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

    @pytest.mark.timeout(2)
    def test_delete_quota(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.delete("/quotas/", json=[3])
        assert response.status_code == 200
        assert response.json() == {
            "response": "deleted",
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
        response = testing_api_client.get("/quotas/3")
        assert response.status_code == 404

    @pytest.mark.timeout(2)
    def test_update_quota(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/quotas/", json=dict(id=1, name="newname", quota=220)
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "newname", "quota": 220},
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }


class Test_Live_API:
    """Tests of API routes which interact with Redis"""

    def test_get_current_quota(
        self,
        fixed_time,
        testing_api_client,
        sda_allowable_ppr,
        populated_database_fixture,
        populate_redis,
        well_spaced_attempts,
    ):
        attempts = well_spaced_attempts(100)
        ppr = sda_allowable_ppr
        populate_redis(ppr.user, 240, attempts)
        last_try = time.strftime(TIME_FORMAT, time.gmtime(attempts[-1]))
        response = testing_api_client.get("/live/quota/remaining/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": 140,
            "remarks": [f"Last send attempt was at {last_try}"],
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    def test_get_current_after_multisend(self):
        """
        Create test like above but ensure that Redis reflects
        multisender attempts payload
        """
        raise NotImplementedError

    def test_reset_quota(
        self,
        fixed_time,
        testing_api_client,
        sda_allowable_ppr,
        populated_database_fixture,
        populate_redis,
        well_spaced_attempts,
    ):
        attempts = well_spaced_attempts(100)
        ppr = sda_allowable_ppr
        populate_redis(ppr.user, 240, attempts)
        last_try = time.strftime(TIME_FORMAT, time.gmtime(attempts[-1]))
        response = testing_api_client.get("/live/quota/remaining/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": 140,
            "remarks": [f"Last send attempt was at {last_try}"],
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
        response = testing_api_client.post("/live/quota/reset/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": 100,
            "remarks": [
                "Quota reset for ccullen@easydns.com: 100 xmits dropped"
            ],
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }

    def test_refresh_quota(
        self,
        fixed_time,
        testing_api_client,
        sda_allowable_ppr,
        populated_database_fixture,
        populate_redis,
        well_spaced_attempts,
    ):
        """
        Test refreshment of quota policy parameters without dropping xmits
        """
        attempts = well_spaced_attempts(100)
        ppr = sda_allowable_ppr
        populate_redis(ppr.user, 240, attempts)
        last_try = time.strftime(TIME_FORMAT, time.gmtime(attempts[-1]))
        response = testing_api_client.get("/live/quota/remaining/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": 140,
            "remarks": [f"Last send attempt was at {last_try}"],
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
        response = testing_api_client.post("/live/quota/refresh/1")
        assert response.status_code == 200
        assert response.json == {
            "response": "Quota policy refreshed for ccullen@easydns.com",
            "timestamp": fixed_time,
            "version": "CHAPPS v0.4",
        }
