"""Tests for CHAPPS configuration code"""
from unittest.mock import patch
from pathlib import Path
import configparser
import pytest
import filecmp
from chapps.config import CHAPPSConfig

pytestmark = pytest.mark.order(2)

DEFAULT_CHAPPS_TEST_CONFIG_WRITE_PATH = "etc/chapps/chapps_test_write.ini"


class Test_Config:
    def test_what_config_file_returns_path(self, chapps_test_env):
        result = CHAPPSConfig.what_config_file()
        assert isinstance(result, Path)

    def test_what_config_file(self, chapps_test_cfg_path, chapps_test_env):
        result = CHAPPSConfig.what_config_file()
        assert str(result) == chapps_test_cfg_path

    def test_mock_config_file(self, chapps_mock_cfg_path, chapps_mock_env):
        result = CHAPPSConfig.what_config_file()
        assert str(result) == chapps_mock_cfg_path

    def test_setup_config(self):
        cp = configparser.ConfigParser()
        CHAPPSConfig.setup_config(cp)
        assert cp["CHAPPS"]["payload_encoding"] == "utf-8"
        assert (
            cp["CHAPPS"]["user_key"] == "sasl_username"
        )  # we assume this elsewhere
        assert cp["CHAPPS"]["listener_backlog"] == "100"
        assert cp["PolicyConfigAdapter"]["adapter"] == "mariadb"
        assert cp["GreylistingPolicy"]["acceptance_message"] == "DUNNO"
        assert cp["Redis"]["server"] == "localhost"

    def test_write_config(
        self, chapps_mock_config, chapps_mock_config_file, chapps_mock_cfg_path
    ):
        """Test that when we write a config file, one is written that contains the config"""
        cfg_path = CHAPPSConfig.write_config(
            chapps_mock_config, DEFAULT_CHAPPS_TEST_CONFIG_WRITE_PATH
        )
        assert filecmp.cmp(str(cfg_path), chapps_mock_cfg_path, shallow=False)
        cfg_path.unlink()

    def test_write_config_bad_path(self, chapps_mock_config):
        """
        Verify that an OSError is raised if the write path is unworkable.
        """
        with pytest.raises(OSError):
            assert CHAPPSConfig.write_config(
                chapps_mock_config, "/dev/null/somedir/noway.ini"
            )

    def test_self_write(self, chapps_test_env, chapps_test_cfg_path):
        cfg = CHAPPSConfig()
        cfg_path = cfg.write(DEFAULT_CHAPPS_TEST_CONFIG_WRITE_PATH)
        assert filecmp.cmp(
            str(cfg_path), cfg.chapps.config_file, shallow=False
        )
        cfg_path.unlink()
        assert cfg.chapps.config_file == chapps_test_cfg_path

    def test_chapps_config_defaults(self, chapps_test_env):
        """Ensure that all CHAPPS settings defaults are present"""
        config = CHAPPSConfig()
        chapps_config = config.chapps
        assert chapps_config.payload_encoding == "utf-8"
        assert chapps_config.listener_backlog == 100

    def test_policy_config_adapter_defaults(self, chapps_test_env):
        config = CHAPPSConfig()
        adapter_config = config.adapter
        assert adapter_config.adapter == "mariadb"
        assert adapter_config.db_host == "localhost"
        assert adapter_config.db_port == 3306
        assert adapter_config.db_name == "chapps"
        assert adapter_config.db_user == "chapps"
        assert adapter_config.db_pass == "chapps"

    def test_oqp_config_defaults(self, chapps_test_env):
        """Ensure that all default policy origin settings are present"""
        config = CHAPPSConfig()
        policy_config = config.policy_oqp
        assert policy_config.listen_address == "localhost"
        assert policy_config.listen_port == 10225
        assert policy_config.acceptance_message == "DUNNO"
        assert (
            policy_config.rejection_message
            == "REJECT Rejected - outbound quota fulfilled"
        )
        assert config.policy_grl.acceptance_message == "DUNNO"
        assert (
            config.policy_grl.rejection_message
            == "DEFER_IF_PERMIT Service temporarily unavailable - greylisted"
        )

    def test_inbound_policy_defaults(self, chapps_test_env):
        """Ensure certain inbound defaults are present"""
        config = CHAPPSConfig()
        spf_config = config.policy_spf
        grl_config = config.policy_grl
        assert grl_config.acceptance_message == "DUNNO"
        assert grl_config.null_sender_ok is False
        assert spf_config.spf_query_timeout == 20
        assert spf_config.null_sender_ok is False

    def test_redis_config_defaults(self, chapps_test_env):
        """Ensure that all Redis setting defaults are present"""
        config = CHAPPSConfig()
        redis_config = config.redis
        assert redis_config.server == "localhost"
        assert redis_config.port == 6379

    def test_config_overrides(
        self,
        chapps_mock_env,
        chapps_mock_config_file,
        chapps_mock_config,
        chapps_mock_cfg_path,
    ):
        """Test a bunch of keys to show that an non-default config prevails"""
        config = CHAPPSConfig()
        chapps_config = config.chapps
        adapter_config = config.adapter
        policy_config = config.policy_oqp
        redis_config = config.redis
        assert chapps_config.config_file == str(Path(chapps_mock_cfg_path))
        assert (
            chapps_config.payload_encoding
            == chapps_mock_config["CHAPPS"]["payload_encoding"]
        )
        assert (
            policy_config.rejection_message
            == "554 Rejected because I said so."
        )
        assert policy_config.acceptance_message == "DUNNO"
        assert adapter_config.adapter == "mysql"
        assert adapter_config.db_port == 3306
        assert adapter_config.db_user == "chapps_test"
        assert adapter_config.db_name == "chapps_test"
        assert adapter_config.db_pass == "screwy%pass${word}"
        assert policy_config.margin == 50.0
        assert policy_config.counting_recipients == False
        assert (
            config.policy_grl.rejection_message
            == "DEFER_IF_PERMIT Service temporarily stupid"
        )
        assert redis_config.server == "127.0.0.1"
        assert redis_config.port == 6379
        assert chapps_config.listener_backlog == 100

    def test_get_block(
        self,
        chapps_mock_env,
        chapps_mock_config_file,
        chapps_mock_config,
        chapps_mock_cfg_path,
    ):
        config = CHAPPSConfig()
        policy_grl = config.get_block("GreylistingPolicy")
        assert (
            policy_grl.rejection_message == config.policy_grl.rejection_message
        )

    def test_helo_whitelist(
        self,
        chapps_helo_env,
        chapps_helo_config_file,
        chapps_helo_config,
        chapps_helo_cfg_path,
    ):
        config = CHAPPSConfig()
        # these settings are weird, but they are for integration testing
        # all that matters here is that they come through properly
        assert config.helo_whitelist == {"[127.0.1.1]": "127.0.0.1"}
