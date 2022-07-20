"""
Operational Configuration
-------------------------

CHAPPS configures itself at the library level.  When it is first launched,
the library will create a config file for itself if it does not find one
at its default config path, `/etc/chapps/chapps.ini`, or the value of
the environment variable `CHAPPS_CONFIG` if it is set.  When it does,
default settings for all available submodules will be produced.

Any instance of CHAPPS requires the general CHAPPS settings, adapter settings,
and the Redis settings.  These control basic features of CHAPPS and tell it
how to access its brains.

Each service script most likely runs a unique policy handler.  If only one
service is being used, only the settings for the policies of that handler will
be needed, plus the ones mentioned above.

Policy handlers (from :py:mod:`chapps.switchboard`) take their listener
configuration from that of their related policy.  Each may each be configured
to use separate listening addresses and ports, so that they may run
simultaneously on the same server.

.. note::

    For multi-policy handlers, the settings used are taken from the first
    handler found to have config elements named `listen_address` and
    `listen_port`.  It is recommended to configure those elements only on one
    active policy, or to keep them in sync on all policies which are handled
    together.

"""
import collections.abc
import configparser
from pathlib import Path
from os import environ as env
from chapps.util import AttrDict, VenvDetector
from chapps._version import __version__
import logging
from typing import Union

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

logger = logging.getLogger(__name__)


class CHAPPSConfig:
    """The configuation object

    Mostly a wrapper around :py:mod:`configparser`, with the most
    commonly used portions wrapped in :py:mod:`chapps.util.AttrDict`

    """

    # ultimately, we may need also to allow for a command-line option
    @staticmethod
    def what_config_file(
        default_pathname: str = "/etc/chapps/chapps.ini"
    ) -> Path:
        """Determine what config file to read.

        This is to allow for easier addition of a command-line option.
        Also encapsulates search for possible file pointed to by the
        environment setting `CHAPPS_CONFIG`

        """
        config_file = Path(env.get("CHAPPS_CONFIG", default_pathname))
        logger.debug("Configurator choosing file " + str(config_file))
        return config_file

    @staticmethod
    def setup_config(
        cp: configparser.ConfigParser
    ) -> configparser.ConfigParser:
        """Setup default config pattern on the parser passed in

        :param configparser.ConfigParser cp: a
           :py:class:`configparser.ConfigParser` instance to hold the
           default config

        This routine establishes the default configuration.  It returns
        the same object which was passed to it.
        """
        cp["CHAPPS"] = {
            "payload_encoding": "utf-8",
            "user_key": "sasl_username",
            "require_user_key": True,
            "no_user_key_response": "REJECT Rejected - Authentication failed",
            "password": (
                "effda33d276c1d5649f3933a6d6b286e"
                "d7eaaede0b944221e7699553ce0558e2"
            ),
        }
        cp["PolicyConfigAdapter"] = {
            "adapter": "mariadb",
            "db_host": "localhost",
            "db_port": "3306",
            "db_name": "chapps",
            "db_user": "chapps",
            "db_pass": "chapps",
        }
        cp["Redis"] = {
            "sentinel_servers": "",
            "sentinel_dataset": "",
            "server": "localhost",
            "port": "6379",
        }
        cp["OutboundQuotaPolicy"] = {
            "listen_address": "localhost",
            "listen_port": 10225,
            "margin": 0.10,
            "min_delta": 0,
            "counting_recipients": True,
            "rejection_message": "REJECT Rejected - outbound quota fulfilled",
            "acceptance_message": "DUNNO",
            "null_sender_ok": False,
        }
        cp["GreylistingPolicy"] = {
            "listen_address": "localhost",
            "listen_port": 10226,
            "rejection_message": (
                "DEFER_IF_PERMIT Service temporarily"
                " unavailable - greylisted"
            ),
            "acceptance_message": "DUNNO",
            "null_sender_ok": False,
            "whitelist_threshold": 10,
        }
        cp["SPFEnforcementPolicy"] = {
            "listen_address": "localhost",
            "listen_port": 10227,
            "whitelist": [],
            "null_sender_ok": False,
        }
        cp["PostfixSPFActions"] = {
            "passing": "prepend",
            "fail": "550 5.7.1 SPF check failed: {reason}",
            "temperror": "451 4.4.3 SPF record(s) temporarily unavailable: {reason}",
            "permerror": "550 5.5.2 SPF record(s) are malformed: {reason}",
            "none_neutral": "greylist",
            "softfail": "greylist",
        }
        cp["SenderDomainAuthPolicy"] = {
            "listen_address": "localhost",
            "listen_port": 10225,
            "rejection_message": "REJECT Rejected - not allowed to send mail from this domain",
            "acceptance_message": "DUNNO",
            "null_sender_ok": False,
        }
        return cp

    @staticmethod
    def write_config(cp, fn) -> Path:
        """Write the ConfigParser contents to disk.

        :param configparser.ConfigParser cp: a ConfigParser object
        :param Union[str, pathlib.Path] fn: path of the config file to write

        If the location's parent directory does not exist, CHAPPS
        will attempt to create it.  If CHAPPS can open the file, it
        writes the contents of `cp` into the file referred to by `fn`.

        Returns a :class:`pathlib.Path` which points at the newly-written file.

        """
        config_file = Path(fn)
        if not config_file.parent.exists():
            try:  # attempt to make any missing parent directories
                config_file.parent.mkdir(0o777, True)
            except OSError as e:
                logger.error(
                    "The specified config file's directory did not exist and"
                    f" could not be created.  File: {str(config_file)}"
                )
                raise e  # possibly this should not be re-raised
        with config_file.open("w") as fh:
            cp.write(fh)
        return config_file

    def __init__(self):
        """Setup a new CHAPPSConfig instance

        This routine does a bunch of different setup to provide more than just
        the on-disk configuration to the running instance. It provides the path
        to the config file that was used to configure the session.  It also
        provides a symbol to refer to the version number.

        It creates a :mod:`chapps.util.VenvDetector` in order to set up the
        path to the README-API.md file.  This could also be used to change the
        default config location when running in a `venv`.  That would
        eliminate the need for prefacing commands with a phrase setting the
        config-file location.

        It causes a config file full of defaults to be written to disk if it
        does not find a file to read.  If it does find a file, it uses the
        settings from that file to overlay the defaults already set up on the
        config object.  It is for this reason that an API method is provided to
        refresh the file on disk with any new settings which might have been
        introduced since the software was last configured.

        """
        ### Create and initialize the config
        self.venvdetector = VenvDetector()
        config_file = CHAPPSConfig.what_config_file(self.venvdetector.confpath)
        self.configparser = configparser.ConfigParser(interpolation=None)
        CHAPPSConfig.setup_config(self.configparser)

        ### Initialize a config file if none
        if not config_file.exists() and not self.venvdetector.sb:
            logger.debug("Writing new config file " + str(config_file))
            CHAPPSConfig.write_config(self.configparser, config_file)
        else:
            logger.debug("Reading from config file " + str(config_file))
            self.configparser.read(str(config_file))
        self.configparser["CHAPPS"]["config_file"] = str(config_file)
        self.configparser["CHAPPS"]["version"] = f"CHAPPS v{__version__}"
        self.configparser["CHAPPS"]["docpath"] = str(self.venvdetector.docpath)
        self.chapps = AttrDict(self.configparser["CHAPPS"])
        self.adapter = AttrDict(self.configparser["PolicyConfigAdapter"])
        self.actions_spf = AttrDict(self.configparser["PostfixSPFActions"])
        self.redis = AttrDict(self.configparser["Redis"])
        ### these are somewhat obsolete now
        self.policy_oqp = AttrDict(self.configparser["OutboundQuotaPolicy"])
        self.policy_sda = AttrDict(self.configparser["SenderDomainAuthPolicy"])
        self.policy_grl = AttrDict(self.configparser["GreylistingPolicy"])
        self.policy_spf = AttrDict(self.configparser["SPFEnforcementPolicy"])
        logger.debug("Returning config built from " + str(config_file))

    def get_block(self, blockname) -> AttrDict:
        """Attempt to get a top-level block of the config as an AttrDict.

        :param str blockname: the name of the block

        Return `None` if it cannot be found.

        """
        try:
            return AttrDict(self.configparser[blockname])
        except Exception:
            pass
        return None

    def write(self, location: Union[str, Path] = None):
        """Write the current config to disk.

        :param Union[str,pathlib.Path] location: where to write the file

        Currently manages exceptions for elements of the `[CHAPPS]` section of
        the config, for parameters which are not specified in the file.  It
        removes them from the config, writes the file, then restores their
        values.  These are:

          * the config file itself (as a :class:`Path`)
          * the CHAPPS version
          * the READMEs' directory (as a :class:`Path`)

        """

        location = Path(location or self.chapps.config_file)
        config_file = self.chapps.config_file
        version = self.chapps.version
        docpath = self.chapps.docpath
        self.configparser.remove_option("CHAPPS", "config_file")
        self.configparser.remove_option("CHAPPS", "version")
        self.configparser.remove_option("CHAPPS", "docpath")
        result = CHAPPSConfig.write_config(self.configparser, location)
        if config_file:
            self.configparser["CHAPPS"]["config_file"] = config_file
        self.configparser["CHAPPS"]["version"] = version
        self.configparser["CHAPPS"]["docpath"] = docpath
        return result


config = CHAPPSConfig()
