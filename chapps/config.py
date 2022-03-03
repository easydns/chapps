"""chapps.config

An easy way to encapsulate library-wide defaults and settings for CHAPPS
"""
import collections.abc
import configparser
from pathlib import Path
from os import environ as env
from chapps.util import AttrDict
import logging, chapps.logging

logger = logging.getLogger(__name__)

class CHAPPSConfig():
    """Class wrapper around config logic makes testing easier"""
    # ultimately, we may need also to allow for a command-line option
    @staticmethod
    def what_config_file():
        """Determine what config file to read.  This is to allow for easier addition of a command-line option."""
        config_file = Path( env.get( 'CHAPPS_CONFIG', "/etc/chapps/chapps.ini" ) )
        return config_file

    @staticmethod
    def setup_config(cp):
        """Setup default config pattern on the parser passed in"""
        cp["CHAPPS"] = {
            'payload_encoding': 'utf-8',
            'listen_address': 'localhost', # should be real IP for API to work properly
            'listen_port': 11511,          # for API listener (TODO: implement API)
            'user_key': 'sasl_username',
        }
        cp["PolicyConfigAdapter"] = {
            'adapter': 'mariadb',
            'db_host': 'localhost',
            'db_port': '3306',
            'db_name': 'chapps',
            'db_user': 'chapps',
            'db_pass': 'chapps',
        }
        cp["OutboundQuotaPolicy"] = {
            'listen_address': 'localhost',
            'listen_port': 10225,
            'margin': 0.10,
            'counting_recipients': True,
            'rejection_message': 'REJECT Rejected - outbound quota fulfilled',
            'acceptance_message': 'DUNNO',
            'null_sender_ok': False,
        }
        cp['GreylistingPolicy'] = {
            'listen_address': 'localhost',
            'listen_port': 10226,
            'rejection_message': 'DEFER_IF_PERMIT Service temporarily unavailable - greylisted',
            'acceptance_message': 'DUNNO',
            'null_sender_ok': False,
        }
        cp['SPFEnforcementPolicy'] = {
            'listen_address': 'localhost',
            'listen_port': 10227,
            'whitelist': [],
            'null_sender_ok': False,
        }
        cp['PostfixSPFActions'] = {
            'passing': 'prepend',
            'fail': '550 5.7.1 SPF check failed: {reason}',
            'temperror': '451 4.4.3 SPF record(s) temporarily unavailable: {reason}',
            'permerror': '550 5.5.2 SPF record(s) are malformed: {reason}',
            'none_neutral': 'greylist',
            'softfail': 'greylist',
        }
        cp['SenderDomainAuthPolicy'] = {
            'listen_address': 'localhost',
            'listen_port': 10225,
            'rejection_message': 'REJECT Rejected - not allowed to send mail from this domain',
            'acceptance_message': 'DUNNO',
            'null_sender_ok': False,
        }
        cp["Redis"] = {
            'sentinel_servers': '',
            'sentinel_dataset': '',
            'server': 'localhost',
            'port': '6379',
        }
        return cp

    @staticmethod
    def write_config(cp, fn):
        """write config in cp to file named fn, if no such file exists; returns a Path object pointing at the config file"""
        config_file = Path(fn)
        if not config_file.parent.exists():
            try:
                config_file.parent.mkdir(0o777, True) # attempt to make any missing parent directories
            except OSError as e:
                logger.error(f"The specified config file's directory did not exist and could not be created.  File: {str(config_file)}")
                raise e
        with config_file.open('w') as fh:
            cp.write(fh)
        return config_file

    def __init__(self):
        ### Create and initialize the config
        config_file = CHAPPSConfig.what_config_file()
        self.configparser = configparser.ConfigParser( interpolation=None )
        CHAPPSConfig.setup_config( self.configparser )

        ### Initialize a config file if none
        if not config_file.exists():
            CHAPPSConfig.write_config( self.configparser, config_file )
        else:
            self.configparser.read( str(config_file) )
        self.configparser["CHAPPS"]["config_file"] = str( config_file )
        self.chapps = AttrDict( self.configparser["CHAPPS"] )
        self.adapter = AttrDict( self.configparser["PolicyConfigAdapter"] )
        self.actions_spf = AttrDict( self.configparser["PostfixSPFActions"] )
        self.redis = AttrDict( self.configparser["Redis"] )
        ### these are somewhat obsolete now
        self.policy_oqp = AttrDict( self.configparser["OutboundQuotaPolicy"] )
        self.policy_sda = AttrDict( self.configparser["SenderDomainAuthPolicy"] )
        self.policy_grl = AttrDict( self.configparser["GreylistingPolicy"] )
        self.policy_spf = AttrDict( self.configparser["SPFEnforcementPolicy"] )

    def get_block( self, blockname ):
        try:
            return AttrDict( self.configparser[ blockname ] )
        except Exception:
            pass
        return None


config = CHAPPSConfig()
