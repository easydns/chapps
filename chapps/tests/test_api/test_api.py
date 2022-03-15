"""Tests of the REST API.  Not called test_rest obvs"""
from fastapi.testclient import TestClient
from chapps.rest.api import api

client = TestClient(api)


class Test_Users_API():
    """Tests of the User CRUD API"""
    def test_get_user(self):
        response = client.get("/users/1")
        assert response.status_code == 200
        assert response.json() == {}
