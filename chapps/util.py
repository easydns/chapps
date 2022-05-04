"""chapps.util

These are the utility classes for CHAPPS
"""
from collections.abc import Mapping
import re
import logging
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class VenvDetector:
    def __init__(self, *, datapath=None):
        """Detect virtual environments and help with paths

        The detector encapsulates the job of determining whether a virtual
        environment is activaed, and assists in composing some important
        paths in order to locate certain files the application needs.

        One of those files is Markdown source which is imported into the
        live API documentation.  Another is the config file.

        """
        if datapath:
            self.datapath = Path(datapath)
        elif self.ve:
            self.datapath = Path(sys.prefix)
        else:
            self.datapath = Path("/usr/local")

    # find the base prefix; hopefully pyenv-compatible
    def get_base_prefix_compat(self):
        return (
            getattr(sys, "base_prefix", None)
            or getattr(sys, "real_prefix", None)
            or sys.prefix
        )

    # return whether we are in a venv
    def in_virtualenv(self):
        return self.get_base_prefix_compat() != sys.prefix

    @property
    def ve(self):
        if "_ve" not in vars(self):
            self._ve = self.in_virtualenv()
        return self._ve

    @property
    def docpath(self):
        """Returns a :class:`Path` pointing at the data directory"""
        if "_docpath" not in vars(self):
            self._docpath = self.datapath / "chapps"
        return self._docpath

    @property
    def confpath(self):
        """Returns a :class:`Path` pointing at the config file"""
        if "_confpath" not in vars(self):
            try:
                self._confpath = self.venvpath / "etc" / "chapps.ini"
            except TypeError:
                self._confpath = Path("/") / "etc" / "chapps" / "chapps.ini"
        return self._confpath

    @property
    def venvpath(self) -> Optional[Path]:
        """Returns None or the value of :const:`sys.prefix` as a :class:`Path`

        If no virtual environment is active, then ``None`` is returned,
        otherwise as :class:`Path` instance is returned, containing the path to
        the virtual environment.  This hasn't been tested with all types of
        virtual environment.

        """
        if self.ve:
            return Path(sys.prefix)


class AttrDict:
    """Attribute Dictionary

    This simple class allows accessing the keys of a hash as attributes on an
    object.  As a useful side effect it also casts floats, integers and
    booleans in advance.

    This object is used in :class:`CHAPPSConfig` for holding the configuration data.

    """

    boolean_pattern = re.compile("^[Tt]rue|[Ff]alse$")

    def __init__(self, data=None, **kwargs):
        if not data:
            data = kwargs
        for k, v in data.items():
            if k[0:2] != "__":
                val = v
                try:
                    val = int(v)
                except ValueError:
                    try:
                        val = float(v)
                    except ValueError:
                        m = self.boolean_pattern.match(v)
                        if m:
                            val = (
                                m.span(0)[1] == 4
                            )  # if the match is 4 chars long, it is True
                except TypeError:
                    pass
                setattr(self, k, val)


class PostfixPolicyRequest(Mapping):
    """Lazy-loading Policy Request Mapping Interface

    An implementation of Mapping which by default only processes and caches
    values from the data payload when they are accessed, to avoid a bunch of
    useless parsing.  Instances may be dereferenced like hashes, but the keys
    are also attributes on the instance, similar to :class:`AttrDict`.

    Once parsed, results are memoized.

    For example, a payload might look a bit like this, when it is first received from Postfix and turned into an array of one string per line:

    .. code::python

        [
            "request=smtpd_access_policy",
            "protocol_state=RCPT",
            "protocol_name=SMTP",
            "helo_name=helo.chapps.io",
            "queue_id=8045F2AB23",
            "sender=unauth@easydns.com",
            "recipient=bar@foo.tld",
            "recipient_count=0",
            "client_address=10.10.10.10",
            "client_name=mail.chapps.io",
            "reverse_client_name=mail.chapps.io",
            "instance=a483.61706bf9.17663.0",
            "sasl_method=plain",
            "sasl_username=somebody@chapps.io",
            "sasl_sender=",
            "size=12345",
            "ccert_subject=",
            "ccert_issuer=Caleb+20Cullen",
            "ccert_fingerprint=DE:AD:BE:EF:FE:ED:AD:DE:D0:A7:52:F3:C1:DA:6E:04",
            "encryption_protocol=TLSv1/SSLv3",
            "encryption_cipher=DHE-RSA-AES256-SHA",
            "encryption_keysize=256",
            "etrn_domain=",
            "stress=",
            "ccert_pubkey_fingerprint=68:B3:29:DA:98:93:E3:40:99:C7:D8:AD:5C:B9:C9:40",
            "client_port=1234",
            "policy_context=submission",
            "server_address=10.3.2.1",
            "server_port=54321",
            "",
        ]

    Refer to the `Postfix policy delegation
    documentation <http://www.postfix.org/SMTPD_POLICY_README.html>`
    for more information.

    """

    def __init__(self, payload: List[str]):
        """Store the payload.

        :param List[str] payload: strings which are formatted as 'key=val',
          including an empty entry at the end.

        This routine discards the last element of the list and stores the rest
        as ``self._payload``.

        .. admonition:: The getattr dunder method is overloaded

          Because the purpose of the class is to present the contents of the
          initial payload as attributes, all internal attributes are
          prefaced with an underscore.

        """
        self._payload = payload[0:-2]

    # the main reason for this class:
    # find and memoize as attributes the values in the request payload
    # means we cannot test existence of attrs by getattr or self.<attr>
    def __getattr__(self, attr: str):
        """Overloaded in order to search for missing attributes in the payload

        :param str attr: the attribute which triggered this call

        First, if the value of ``attr`` starts with an underscore, ``None`` is
        returned.  No lines of the payload start with an underscore.  This
        ensures that references to internal attributes of the class are not
        snarled up with the payload searches.

        Next, the payload is searched for the requested key-value pair,
        attempting to match ``attr`` against everything before the ``=`` sign.
        When a line is found, the contents after the ``=`` are stored as an
        attribute named ``attr`` (and so memoized), and the value is returned.
        Future attempts to obtain the value will encounter the attribute and
        not invoke :func:``__getattr__`` again.

        A ``DEBUG`` level message is currently produced if no lines in the
        payload matched the requested payload data.  No errors are produced
        if a nonexistent ``attr`` starting with ``_`` is encountered.

        """
        if attr[0] == "_":  # leading underscores do not occur in the payload
            return None
        line = next(
            (l for l in self._payload if attr == l.split("=")[0]), None
        )
        if line:
            key, value = line.split("=")
            setattr(self, key, value)
            return value
        else:
            logger.debug(f"No lines in {self} matched {attr}.")
        return None

    # Since the datastructure can function as a hash, provide optimization
    def __getitem__(self, key):
        """
        Getting an item should optimize the result
        via the attribute mechanism
        """
        return getattr(self, key)

    # The datastructure is iterable, in case we need to enumerate the request
    def __iter__(self):
        """Return an iterable representing the mapping

        There should be few reasons to ever do this, though it comes in quite
        handy for testing.  This routine memoizes the dict it creates and also
        stores all the keys as attributes for future accesses.

        """
        if not getattr(self, "_mapping", None):
            self._mapping = {
                k: v for k, v in [l.split("=") for l in self._payload]
            }
            # Since we end up parsing the entire payload
            # optimize it for future random access
            for k, v in self._mapping.items():
                setattr(self, k, v)
        yield from self._mapping

    # The length of the PPR is considered to be the number of items stored
    def __len__(self):
        """Act like a dict and return the number of k,v pairs"""
        return len(self._payload)

    # Representations of PPR use their own class name, and otherwise dump
    # the payload, but not a list of attributes
    def __repr__(self):
        """Dump the data in _payload"""
        return "%s( %r )" % (self.__class__.__name__, self._payload)

    # In order to use memoization with PPRs, a hash function is required
    def __hash__(self):
        """Create a reliable hash for this PPR"""
        if "_hash" not in vars(self):
            self._hash = hash(f"{self.instance}:{self.queue_id}")
        return self._hash

    # This convenience property provides a list of recipient email addresses
    # since the line may contain more than one
    @property
    def recipients(self) -> List[str]:
        """
        A convenience method to split the 'recipient' datum
        into comma-separated tokens, for easier counting.
        """
        if "_recipients" not in vars(self):
            self._recipients = (
                self.recipient.split(",")
                if self.recipient and len(self.recipient) > 0
                else []
            )
        return self._recipients
