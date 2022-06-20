"""Tests of the REST API.  Not called test_rest obvs

.. todo::

  Write tests for data models -- specifically cover validation

"""
import pytest
import pudb
import chapps.config
import time
from urllib.parse import quote as urlencode
from chapps._version import __version__
from chapps.policy import TIME_FORMAT
from chapps.models import SDAStatus
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
verstr = "CHAPPS v" + __version__

pytestmark = pytest.mark.order(-1)


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
            "domains": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "emails": [{"id": 1, "name": "caleb@chapps.com"}],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": verstr,
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
            "version": verstr,
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
            "emails": None,
            "domains": None,
            "quota": None,
            "timestamp": fixed_time,
            "version": verstr,
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
            "domains": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "emails": None,
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": verstr,
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
            "version": verstr,
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
            "emails": None,
            "timestamp": fixed_time,
            "version": verstr,
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
            "emails": None,
            "quota": {"id": 2, "name": "50eph", "quota": 1200},
            "timestamp": fixed_time,
            "version": verstr,
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
            "domains": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "emails": None,
            "quota": None,
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_user_emails(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/users/",
            json=dict(user=dict(id=1, name="ccullen@easydns.com"), emails=[1]),
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": None,
            "emails": [{"id": 1, "name": "caleb@chapps.com"}],
            "quota": None,
            "timestamp": fixed_time,
            "version": verstr,
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
            "emails": None,
            "timestamp": fixed_time,
            "version": verstr,
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
            "domains": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "emails": None,
            "quota": {"id": 2, "name": "50eph", "quota": 1200},
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_user_add_domains(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.put("/users/1/domains/", json=[2])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get("/users/1")
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                },
                {
                    "id": 2,
                    "name": "easydns.com",
                    "greylist": False,
                    "check_spf": False,
                },
            ],
            "emails": [{"id": 1, "name": "caleb@chapps.com"}],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_user_remove_domains(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.delete("/users/3/domains/", json=[1])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get("/users/3")
        assert response.json() == {
            "response": {"id": 3, "name": "bigsender@chapps.io"},
            "domains": [
                {
                    "id": 2,
                    "name": "easydns.com",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "quota": {"id": 3, "name": "200eph", "quota": 4800},
            "emails": [
                {"id": 2, "name": "roleaccount@chapps.com"},
                {"id": 3, "name": "admin@chapps.com"},
                {"id": 4, "name": "abuse@chapps.com"},
                {"id": 5, "name": "info@chapps.com"},
            ],
            "timestamp": fixed_time,
            "version": verstr,
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
            "version": verstr,
        }
        response = testing_api_client.get("/users/1")
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "emails": [{"id": 1, "name": "caleb@chapps.com"}],
            "quota": {"id": 2, "name": "50eph", "quota": 1200},
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_user_paginate_domains(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.get("/users/5/domains/?skip=2&limit=2")
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {
                    "id": 3,
                    "name": "easydns.net",
                    "greylist": False,
                    "check_spf": False,
                },
                {
                    "id": 4,
                    "name": "easydns.org",
                    "greylist": False,
                    "check_spf": False,
                },
            ],
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_user_paginate_emails(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.get("/users/3/emails/?skip=2&limit=2")
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {"id": 4, "name": "abuse@chapps.com"},
                {"id": 5, "name": "info@chapps.com"},
            ],
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_user_add_emails(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.put("/users/1/emails/", json=[2])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get("/users/1")
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "emails": [
                {"id": 1, "name": "caleb@chapps.com"},
                {"id": 2, "name": "roleaccount@chapps.com"},
            ],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_user_remove_emails(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.delete("/users/3/emails/", json=[2])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get("/users/3")
        assert response.json() == {
            "response": {"id": 3, "name": "bigsender@chapps.io"},
            "domains": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                },
                {
                    "id": 2,
                    "name": "easydns.com",
                    "greylist": False,
                    "check_spf": False,
                },
            ],
            "quota": {"id": 3, "name": "200eph", "quota": 4800},
            "emails": [
                {"id": 3, "name": "admin@chapps.com"},
                {"id": 4, "name": "abuse@chapps.com"},
                {"id": 5, "name": "info@chapps.com"},
            ],
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_user_quota_mapping(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.get("/users/quotas/", json=[1, 2, 3])
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {"user_name": "ccullen@easydns.com", "quota_id": "1"},
                {"user_name": "somebody@chapps.io", "quota_id": "2"},
                {"user_name": "bigsender@chapps.io", "quota_id": "3"},
            ],
            "remarks": [],
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_user_domains_mapping(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.get("/users/domains/", json=[1, 2, 3])
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {"user_name": "ccullen@easydns.com", "domain_ids": [1]},
                {"user_name": "somebody@chapps.io", "domain_ids": [1]},
                {"user_name": "bigsender@chapps.io", "domain_ids": [1, 2]},
            ],
            "remarks": [],
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_user_emails_mapping(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.get("/users/emails/", json=[1, 2, 3])
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {"user_name": "ccullen@easydns.com", "email_ids": [1]},
                {"user_name": "somebody@chapps.io", "email_ids": [2]},
                {
                    "user_name": "bigsender@chapps.io",
                    "email_ids": [2, 3, 4, 5],
                },
            ],
            "remarks": [],
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_user_quota_mapping_with_breakage(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_breakage,
    ):
        response = testing_api_client.get("/users/quotas/", json=[1, 2, 3])
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {"user_name": "ccullen@easydns.com", "quota_id": None},
                {"user_name": "bigsender@chapps.io", "quota_id": "3"},
            ],
            "remarks": [],
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_user_create_duplicate(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.post(
            "/users/", json=dict(name="ccullen@easydns.com")
        )
        assert response.status_code == 409
        assert response.json() == {
            "detail": "Unique key conflict creating user."
        }

    @pytest.mark.timeout(2)
    def test_user_quota_mapping_with_empty_return(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_breakage,
    ):
        response = testing_api_client.get("/users/quotas/", json=[2])
        assert response.status_code == 404
        assert response.json() == {"detail": "Unable to find a matching user"}


class Test_Domains_API:
    """Tests of the Domain CRUD API"""

    @pytest.mark.timeout(2)
    def test_get_domain(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.get("/domains/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": {
                "id": 1,
                "name": "chapps.io",
                "greylist": False,
                "check_spf": False,
            },
            "timestamp": fixed_time,
            "users": [
                {"id": 1, "name": "ccullen@easydns.com"},
                {"id": 2, "name": "somebody@chapps.io"},
                {"id": 3, "name": "bigsender@chapps.io"},
            ],
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_list_domains(self, fixed_time, testing_api_client):
        response = testing_api_client.get("/domains/")
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_create_domain(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        # pudb.set_trace()
        response = testing_api_client.post(
            "/domains/",
            json={
                "name": "easydns.com",
                "users": [],
                "greylist": True,
                "check_spf": True,
            },
        )
        assert response.status_code == 201
        assert response.json() == {
            "response": {
                "id": 2,
                "name": "easydns.com",
                "greylist": True,
                "check_spf": True,
            },
            "users": None,
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(3)
    def test_create_domain_with_users(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.post(
            "/domains/",
            json={
                "name": "easydns.com",
                "greylist": True,
                "check_spf": True,
                "users": [1],
            },
        )
        assert response.status_code == 201
        assert response.json() == {
            "response": {
                "id": 2,
                "name": "easydns.com",
                "greylist": True,
                "check_spf": True,
            },
            "timestamp": fixed_time,
            "users": [{"id": 1, "name": "ccullen@easydns.com"}],
            "version": verstr,
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
            "version": verstr,
        }
        response = testing_api_client.get("/domains/1")
        assert response.status_code == 404
        response = testing_api_client.get("/users/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "domains": [],
            "emails": [{"id": 1, "name": "caleb@chapps.com"}],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_domain(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/domains/",
            json=dict(
                domain=dict(
                    id=1, name="crapps.io", greylist=False, check_spf=True
                )
            ),
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {
                "id": 1,
                "name": "crapps.io",
                "greylist": False,
                "check_spf": True,
            },
            "timestamp": fixed_time,
            "users": None,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_domain_with_users(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/domains/",
            json=dict(
                domain=dict(
                    id=1, name="chapps.io", greylist=True, check_spf=False
                ),
                users=[2, 3],
            ),
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {
                "id": 1,
                "name": "chapps.io",
                "greylist": True,
                "check_spf": False,
            },
            "timestamp": fixed_time,
            "users": [
                {"id": 2, "name": "somebody@chapps.io"},
                {"id": 3, "name": "bigsender@chapps.io"},
            ],
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_domain_add_users(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.put("/domains/2/users/", json=[4, 3])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get("/users/4")
        assert response.json() == {
            "response": {"id": 4, "name": "schmo1@chapps.io"},
            "domains": [
                {
                    "id": 2,
                    "name": "easydns.com",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "emails": [{"id": 2, "name": "roleaccount@chapps.com"}],
            "quota": None,
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_domain_remove_users(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.delete("/domains/1/users/", json=[3])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get("/users/3")
        assert response.json() == {
            "response": {"id": 3, "name": "bigsender@chapps.io"},
            "domains": [
                {
                    "id": 2,
                    "name": "easydns.com",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "emails": [
                {"id": 2, "name": "roleaccount@chapps.com"},
                {"id": 3, "name": "admin@chapps.com"},
                {"id": 4, "name": "abuse@chapps.com"},
                {"id": 5, "name": "info@chapps.com"},
            ],
            "quota": {"id": 3, "name": "200eph", "quota": 4800},
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_domain_list_users(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.get("/domains/1/users/?skip=2&limit=2")
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {"id": 3, "name": "bigsender@chapps.io"},
                {"id": 5, "name": "schmo2@chapps.io"},
            ],
            "timestamp": fixed_time,
            "version": verstr,
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
            "version": verstr,
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
            "version": verstr,
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
            "version": verstr,
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
            "version": verstr,
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
            "version": verstr,
        }


class Test_Emails_API:
    """Tests of whole-email sender authorization API routes"""

    @pytest.mark.timeout(2)
    def test_get_email(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.get("/emails/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "caleb@chapps.com"},
            "users": [{"id": 1, "name": "ccullen@easydns.com"}],
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_list_emails(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.get("/emails/")
        assert response.status_code == 200
        assert response.json() == {
            "response": [{"id": 1, "name": "caleb@chapps.com"}],
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_create_email(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        # pudb.set_trace()
        response = testing_api_client.post(
            "/emails/", json={"name": "someone@chapps.com", "users": []}
        )
        assert response.status_code == 201
        assert response.json() == {
            "response": {"id": 2, "name": "someone@chapps.com"},
            "users": None,
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(3)
    def test_create_email_with_users(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.post(
            "/emails/", json={"name": "someone@chapps.com", "users": [1]}
        )
        assert response.status_code == 201
        assert response.json() == {
            "response": {"id": 2, "name": "someone@chapps.com"},
            "timestamp": fixed_time,
            "users": [{"id": 1, "name": "ccullen@easydns.com"}],
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_delete_email(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.delete("/emails/", json=[1])
        assert response.status_code == 200
        assert response.json() == {
            "response": "deleted",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get("/emails/1")
        assert response.status_code == 404
        response = testing_api_client.get("/users/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "emails": [],
            "domains": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_email(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/emails/", json=dict(email=dict(id=1, name="caleb@crapps.io"))
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "caleb@crapps.io"},
            "timestamp": fixed_time,
            "users": None,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_email_with_users(
        self, fixed_time, testing_api_client, populated_database_fixture
    ):
        response = testing_api_client.put(
            "/emails/",
            json=dict(email=dict(id=1, name="caleb@chapps.com"), users=[2, 3]),
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {"id": 1, "name": "caleb@chapps.com"},
            "timestamp": fixed_time,
            "users": [
                {"id": 2, "name": "somebody@chapps.io"},
                {"id": 3, "name": "bigsender@chapps.io"},
            ],
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_email_add_users(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.put("/emails/1/users/", json=[4, 3])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get("/users/4")
        assert response.json() == {
            "response": {"id": 4, "name": "schmo1@chapps.io"},
            "emails": [
                {"id": 1, "name": "caleb@chapps.com"},
                {"id": 2, "name": "roleaccount@chapps.com"},
            ],
            "domains": [],
            "quota": None,
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_update_email_remove_users(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.delete("/emails/1/users/", json=[1])
        assert response.status_code == 200
        assert response.json() == {
            "response": "Updated.",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get("/users/1")
        assert response.json() == {
            "response": {"id": 1, "name": "ccullen@easydns.com"},
            "emails": [],
            "domains": [
                {
                    "id": 1,
                    "name": "chapps.io",
                    "greylist": False,
                    "check_spf": False,
                }
            ],
            "quota": {"id": 1, "name": "10eph", "quota": 240},
            "timestamp": fixed_time,
            "version": verstr,
        }

    @pytest.mark.timeout(2)
    def test_email_list_users(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_extras,
    ):
        response = testing_api_client.get("/emails/2/users/?skip=2&limit=2")
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                {"id": 4, "name": "schmo1@chapps.io"},
                {"id": 5, "name": "schmo2@chapps.io"},
            ],
            "timestamp": fixed_time,
            "version": verstr,
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
        response = testing_api_client.get("/live/quota/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": 140,
            "remarks": [f"Last send attempt was at {last_try}"],
            "timestamp": fixed_time,
            "version": verstr,
        }

    def test_get_current_after_multisend(
        self,
        fixed_time,
        testing_api_client,
        sda_allowable_ppr,
        populated_database_fixture,
        populate_redis_multi,
        well_spaced_attempts,
    ):
        """
        Create test like above but ensure that Redis reflects
        multisender attempts payload
        """
        attempts = well_spaced_attempts(100)
        ppr = sda_allowable_ppr
        populate_redis_multi(ppr.user, 240, attempts)
        last_try = time.strftime(TIME_FORMAT, time.gmtime(attempts[-1]))
        response = testing_api_client.get("/live/quota/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": 140,
            "remarks": [f"Last send attempt was at {last_try}"],
            "timestamp": fixed_time,
            "version": verstr,
        }

    def test_bulk_avail_quota(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture,
        populate_redis,
        well_spaced_attempts,
    ):
        attempts = well_spaced_attempts(100)
        users = [
            ["ccullen@easydns.com", 240],
            ["somebody@chapps.io", 1200],
            ["bigsender@chapps.io", 4800],
        ]
        for u in users:
            populate_redis(u[0], u[1], attempts)
        last_try = time.strftime(TIME_FORMAT, time.gmtime(attempts[-1]))
        response = testing_api_client.get("/live/quota/", json=[1, 2, 3])
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                dict(user_name=u[0], quota_avail=str(u[1] - 100))
                for u in users
            ],
            "remarks": [f"Last send attempt was at {last_try}"] * 3,
            "timestamp": fixed_time,
            "version": verstr,
        }

    def test_bulk_avail_quota_with_breakage(
        self,
        fixed_time,
        testing_api_client,
        populated_database_fixture_with_breakage,
        populate_redis,
        well_spaced_attempts,
    ):
        attempts = well_spaced_attempts(100)
        users = [
            ["ccullen@easydns.com", 240],
            ["somebody@chapps.io", 1200],
            ["bigsender@chapps.io", 4800],
        ]
        for u in users:
            populate_redis(u[0], u[1], attempts)
        last_try = time.strftime(TIME_FORMAT, time.gmtime(attempts[-1]))
        response = testing_api_client.get("/live/quota/", json=[1, 2, 3])
        assert response.status_code == 200
        assert response.json() == {
            "response": [
                dict(user_name=u[0], quota_avail=str(u[1] - 100))
                for u in [users[0], users[2]]
            ],
            "remarks": [
                f"Last send attempt was at {last_try}",
                f"There is no quota configured for user {users[0][0]}.",
                f"Last send attempt was at {last_try}",
            ],
            "timestamp": fixed_time,
            "version": verstr,
        }

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
        response = testing_api_client.get("/live/quota/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": 140,
            "remarks": [f"Last send attempt was at {last_try}"],
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.delete("/live/quota/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": 100,
            "remarks": [
                "Attempts (quota) reset for ccullen@easydns.com: 100 xmits dropped"
            ],
            "timestamp": fixed_time,
            "version": verstr,
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
        populate_redis(ppr.user, 1200, attempts)
        last_try = time.strftime(TIME_FORMAT, time.gmtime(attempts[-1]))
        response = testing_api_client.get("/live/quota/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": 1100,
            "remarks": [f"Last send attempt was at {last_try}"],
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.post("/live/quota/1")
        assert response.status_code == 200
        assert response.json() == {
            "response": 140,
            "timestamp": fixed_time,
            "version": verstr,
            "remarks": [
                f"Quota policy config cache reset for ccullen@easydns.com",
                f"Last send attempt was at {last_try}",
            ],
        }

    # CONFIG oriented
    def test_write_config(
        self, fixed_time, testing_api_client, chapps_mock_cfg_path
    ):
        response = testing_api_client.post(
            "/live/config/write/", json="screwy%pass${word}"
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": chapps_mock_cfg_path,
            "timestamp": fixed_time,
            "version": verstr,
        }

    # SDA oriented
    def test_sda_cache_peek_single(
        self,
        fixed_time,
        testing_api_client,
        testing_policy_sda,
        sda_allowable_ppr,
        populated_database_fixture,
        populate_redis,
        well_spaced_attempts,
    ):
        result = testing_policy_sda.approve_policy_request(sda_allowable_ppr)
        response = testing_api_client.get(
            "/live/sda/"
            + urlencode("chapps.io")
            + "/for/"
            + urlencode(sda_allowable_ppr.user)
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": SDAStatus.AUTH.value,
            "timestamp": fixed_time,
            "version": verstr,
        }

    def test_sda_cache_peek_email(
        self,
        fixed_time,
        testing_api_client,
        testing_policy_sda,
        sda_auth_email_ppr,
        populated_database_fixture,
    ):
        result = testing_policy_sda.approve_policy_request(sda_auth_email_ppr)
        response = testing_api_client.get(
            "/live/sda/"
            + urlencode(sda_auth_email_ppr.sender)
            + "/for/"
            + urlencode(sda_auth_email_ppr.user)
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": SDAStatus.AUTH.value,
            "timestamp": fixed_time,
            "version": verstr,
        }

    def test_sda_cache_peek_domains_bulk(
        self,
        fixed_time,
        testing_api_client,
        testing_policy_sda,
        sda_allowable_ppr,
        sda_unauth_ppr,
        populated_database_fixture_with_extras,
        clear_redis_sda,
    ):
        result = testing_policy_sda.approve_policy_request(sda_allowable_ppr)
        assert result == True
        result = testing_policy_sda.approve_policy_request(sda_unauth_ppr)
        assert result == False
        response = testing_api_client.get(
            "/live/sda/", json={"user_ids": [1, 2], "domain_ids": [1, 2]}
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {
                "chapps.io": {
                    "ccullen@easydns.com": SDAStatus.AUTH.value,
                    "somebody@chapps.io": SDAStatus.NONE.value,
                },
                "easydns.com": {
                    "ccullen@easydns.com": SDAStatus.NONE.value,
                    "somebody@chapps.io": SDAStatus.PROH.value,
                },
            },
            "timestamp": fixed_time,
            "version": verstr,
        }

    def test_sda_cache_peek_emails_bulk(
        self,
        fixed_time,
        testing_api_client,
        testing_policy_sda,
        # sda_allowable_ppr,
        # sda_unauth_ppr,
        sda_auth_email_ppr,
        sda_unauth_email_ppr,
        populated_database_fixture_with_extras,
        clear_redis_sda,
    ):
        # result = testing_policy_sda.approve_policy_request(sda_allowable_ppr)
        # assert result == True
        # result = testing_policy_sda.approve_policy_request(sda_unauth_ppr)
        # assert result == False
        result = testing_policy_sda.approve_policy_request(sda_auth_email_ppr)
        assert result == True
        result = testing_policy_sda.approve_policy_request(
            sda_unauth_email_ppr
        )
        assert sda_unauth_email_ppr.sender == "ccullen@chapps.com"
        assert sda_unauth_email_ppr.user == "ccullen@easydns.com"
        assert result == False
        response = testing_api_client.get(
            "/live/sda/", json={"user_ids": [1, 2], "email_ids": [1, 2]}
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {
                "caleb@chapps.com": {
                    "ccullen@easydns.com": SDAStatus.AUTH.value,
                    "somebody@chapps.io": SDAStatus.NONE.value,
                },
                "roleaccount@chapps.com": {
                    "ccullen@easydns.com": SDAStatus.NONE.value,
                    "somebody@chapps.io": SDAStatus.NONE.value,
                },
            },
            "timestamp": fixed_time,
            "version": verstr,
        }

    def test_sda_cache_clear_single(
        self,
        fixed_time,
        testing_api_client,
        testing_policy_sda,
        sda_allowable_ppr,
        populated_database_fixture,
        populate_redis,
        well_spaced_attempts,
    ):
        result = testing_policy_sda.approve_policy_request(sda_allowable_ppr)
        response = testing_api_client.delete(
            "/live/sda/"
            + urlencode("chapps.io")
            + "/for/"
            + urlencode(sda_allowable_ppr.user)
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": SDAStatus.AUTH.value,
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get(
            "/live/sda/"
            + urlencode("chapps.io")
            + "/for/"
            + urlencode(sda_allowable_ppr.user)
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": SDAStatus.NONE.value,
            "timestamp": fixed_time,
            "version": verstr,
        }

    def test_sda_cache_clear_email(
        self,
        fixed_time,
        testing_api_client,
        testing_policy_sda,
        sda_auth_email_ppr,
        populated_database_fixture,
        clear_redis_sda,
    ):
        result = testing_policy_sda.approve_policy_request(sda_auth_email_ppr)
        response = testing_api_client.delete(
            "/live/sda/"
            + urlencode(sda_auth_email_ppr.sender)
            + "/for/"
            + urlencode(sda_auth_email_ppr.user)
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": SDAStatus.AUTH.value,
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get(
            "/live/sda/"
            + urlencode(sda_auth_email_ppr.sender)
            + "/for/"
            + urlencode(sda_auth_email_ppr.user)
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": SDAStatus.NONE.value,
            "timestamp": fixed_time,
            "version": verstr,
        }

    def test_sda_cache_clear_domains_bulk(
        self,
        fixed_time,
        testing_api_client,
        testing_policy_sda,
        sda_allowable_ppr,
        sda_unauth_ppr,
        populated_database_fixture_with_extras,
        clear_redis_sda,
    ):
        result = testing_policy_sda.approve_policy_request(sda_allowable_ppr)
        assert result == True
        result = testing_policy_sda.approve_policy_request(sda_unauth_ppr)
        assert result == False
        assert sda_unauth_ppr.user == "somebody@chapps.io"
        response = testing_api_client.get(
            "/live/sda/", json={"user_ids": [1, 2], "domain_ids": [1, 2]}
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {
                "chapps.io": {
                    "ccullen@easydns.com": SDAStatus.AUTH.value,
                    "somebody@chapps.io": SDAStatus.NONE.value,
                },
                "easydns.com": {
                    "ccullen@easydns.com": SDAStatus.NONE.value,
                    "somebody@chapps.io": SDAStatus.PROH.value,
                },
            },
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.delete(
            "/live/sda/", json={"domain_ids": [1, 2], "user_ids": [1, 2]}
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": "SDA cache cleared for specified domains and/or emails x users.",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get(
            "/live/sda/", json={"user_ids": [1, 2], "domain_ids": [1, 2]}
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {
                "chapps.io": {
                    "ccullen@easydns.com": SDAStatus.NONE.value,
                    "somebody@chapps.io": SDAStatus.NONE.value,
                },
                "easydns.com": {
                    "ccullen@easydns.com": SDAStatus.NONE.value,
                    "somebody@chapps.io": SDAStatus.NONE.value,
                },
            },
            "timestamp": fixed_time,
            "version": verstr,
        }

    def test_sda_cache_clear_emails_bulk(
        self,
        fixed_time,
        testing_api_client,
        testing_policy_sda,
        # sda_allowable_ppr,
        # sda_unauth_ppr,
        sda_auth_email_ppr,
        sda_unauth_email_ppr,
        populated_database_fixture_with_extras,
        clear_redis_sda,
    ):
        # result = testing_policy_sda.approve_policy_request(sda_allowable_ppr)
        # assert result == True
        # result = testing_policy_sda.approve_policy_request(sda_unauth_ppr)
        # assert result == False
        result = testing_policy_sda.approve_policy_request(sda_auth_email_ppr)
        assert result == True
        result = testing_policy_sda.approve_policy_request(
            sda_unauth_email_ppr
        )
        assert result == False
        response = testing_api_client.get(
            "/live/sda/", json={"user_ids": [1, 2], "email_ids": [1, 2]}
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {
                "caleb@chapps.com": {
                    "ccullen@easydns.com": SDAStatus.AUTH.value,
                    "somebody@chapps.io": SDAStatus.NONE.value,
                },
                "roleaccount@chapps.com": {
                    "ccullen@easydns.com": SDAStatus.NONE.value,
                    "somebody@chapps.io": SDAStatus.NONE.value,
                },
            },
            "timestamp": fixed_time,
            "version": verstr,
        }

        response = testing_api_client.delete(
            "/live/sda/", json={"user_ids": [1, 2], "email_ids": [1, 2]}
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": "SDA cache cleared for specified domains and/or emails x users.",
            "timestamp": fixed_time,
            "version": verstr,
        }
        response = testing_api_client.get(
            "/live/sda/", json={"user_ids": [1, 2], "email_ids": [1, 2]}
        )
        assert response.status_code == 200
        assert response.json() == {
            "response": {
                "caleb@chapps.com": {
                    "ccullen@easydns.com": SDAStatus.NONE.value,
                    "somebody@chapps.io": SDAStatus.NONE.value,
                },
                "roleaccount@chapps.com": {
                    "ccullen@easydns.com": SDAStatus.NONE.value,
                    "somebody@chapps.io": SDAStatus.NONE.value,
                },
            },
            "timestamp": fixed_time,
            "version": verstr,
        }
