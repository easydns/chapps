"""Tests of the REST API.  Not called test_rest obvs"""
from fastapi.testclient import TestClient
from chapps.tests.test_config.conftest import (
    chapps_mock_cfg_path,
    chapps_mock_config,
    chapps_mock_config_file,
    chapps_mock_env,
)
import chapps.config



class Test_Users_API:
    """Tests of the User CRUD API"""

    def test_get_user(self, monkeypatch, chapps_mock_env, chapps_mock_config_file):
        cfg = chapps.config.CHAPPSConfig()
        assert cfg.chapps.config_file == str(chapps_mock_config_file)
        with monkeypatch.context() as m:
            m.setattr(chapps.config, 'config', cfg)
            from chapps.rest.api import api
            client = TestClient(api)
            response = client.get("/users/1")
            assert response.status_code == 200
            assert response.json() == {}
