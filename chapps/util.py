"""
Utility classes
---------------

Since CHAPPS mainly deals with policy requests coming from Postfix,
there is a utility object for representing them in a way which makes
the code easier to read while also providing access optimizations.

There is another utility class for providing the configuration
data via an object which presents dictionary keys as attributes.

In order to create different defaults and access documentation files,
an object is provided which detects whether the library is running
within a virtual environment, and serves as a source of local paths
to package resources.

.. todo::

  add Postfix command class, to store action output along with
  status information.

"""
from collections.abc import Mapping
import re
import logging
import sys
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from chapps.signals import TooManyAtsException, NotAnEmailAddressException

logger = logging.getLogger(__name__)


def hash_password(password: str, encoding: str = "utf-8") -> str:
    return hashlib.sha256(password.encode(encoding)).hexdigest()


class VenvDetector:
    """Detect use of a virtual environment and calculate local paths

    The detector encapsulates the job of determining whether a virtual
    environment is activated, and assists in composing some important paths in
    order to locate certain files the application needs.

    One of those files is Markdown source which is imported into the live API
    documentation.  Another is the config file.

    Instance attributes:

      :datapath: :class:`~pathlib.Path` pointing at location where data files
        are installed

      :ve: :obj:`bool` indicating whether a virtual environment is active

      :docpath: :class:`~pathlib.Path` pointing at the location of the Markdown

      :confpath: :class:`~pathlib.Path` pointing at the config file

      :venvpath: :class:`~pathlib.Path` to the root of the active virtual
        environment, or None if none is active

    """

    def __init__(self, *, datapath: Optional[Union[str, Path]] = None):
        """Detect virtual environments and provide local package paths

        :param datapath: optional override to point
          at the data installation path of the package (or a surrogate).  The
          API uses this value to load the API readme into the live docs.

        """
        if datapath:
            self.datapath = Path(datapath)
        elif self.ve:
            self.datapath = Path(sys.prefix)
        else:
            self.datapath = Path("/usr/local")

    # find the base prefix; hopefully pyenv-compatible
    def get_base_prefix_compat(self) -> str:
        """Return the non-virtual base prefix

        Sometimes called `sys.real_prefix`, so we check for both.

        :returns: the base path prefix
        :rtype: str

        """
        return (
            getattr(sys, "base_prefix", None)
            or getattr(sys, "real_prefix", None)
            or sys.prefix
        )

    # return whether we are in a venv
    def in_virtualenv(self) -> bool:
        """Compare prefixes to determine if a virtual environment is active.

        :returns: true if a virtual environment is active, otherwise False

        :rtype: bool

        """
        return self.get_base_prefix_compat() != sys.prefix

    # return whether a Sphinx build launched the library
    def sphinx_build(self) -> bool:
        """Determine whether invoked by Sphinx

        :returns: `True` if Sphinx invoked the library

        """
        try:
            if __sphinx_build__:
                return True
        except NameError:
            return False

    @property
    def ve(self) -> bool:
        """Property which memoizes :meth:`~.in_virtualenv`"""
        if "_ve" not in vars(self):
            self._ve = self.in_virtualenv()
        return self._ve

    @property
    def sb(self) -> bool:
        """Property which memoizes :meth:`~.sphinx_build`"""
        if "_sb" not in vars(self):
            self._sb = self.sphinx_build()
        return self._sb

    @property
    def docpath(self) -> Path:
        """Memoizes the documentation location

        :returns: a :class:`~pathlib.Path` pointing at the Markdown files'
          location

        :rtype: pathlib.Path

        """
        if "_docpath" not in vars(self):
            self._docpath = self.datapath / "chapps"
        return self._docpath

    @property
    def confpath(self) -> Path:
        """Memoizes the config file's full path

        :returns: a :class:`~pathlib.Path` pointing at the config file

        :rtype: pathlib.Path


        """
        if "_confpath" not in vars(self):
            try:
                self._confpath = self.venvpath / "etc" / "chapps.ini"
            except TypeError:
                self._confpath = Path("/") / "etc" / "chapps" / "chapps.ini"
        return self._confpath

    @property
    def venvpath(self) -> Optional[Path]:
        """The virtual environment root, if any

        :returns: None or the value of :const:`sys.prefix` as a :class:`Path`

        :rtype: Optional[pathlib.Path]

        If no virtual environment is active, then `None` is returned,
        otherwise a :class:`Path` instance is returned, containing the path to
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

    This object is used in :class:`~chapps.config.CHAPPSConfig` for holding the configuration data.

    .. note::

      The purpose of this class is to map all the keys of a fairly small
      :obj:`dict` as attributes of the instance onto their values in the source
      dict.  This class does not perform the same sort of lazy-loading as the
      :class:`~.PostfixPolicyRequest` class below; it pre-maps all the elements
      in the source :obj:`dict`.  So be careful about passing large
      dictionaries to it.

    .. admonition:: Subclassing

      Given the stated purpose of the class, all *internal instance attributes*,
      i.e. ones not associated to a key-value pair in the source object, should
      begin with  `_` (an underscore).

    """

    boolean_pattern = re.compile("^[Tt]rue|[Ff]alse$")
    """A regex to detect text-string boolean values"""

    def __init__(
        self, data: Dict[str, Any] = None, **kwargs: Optional[Dict[str, Any]]
    ):
        r"""Populate an instance with attributes

        :param data: a :obj:`dict` mapping strings (attribute names) onto arbitrary values

        :param kwargs: arbitrary keyword arguments

        If, and only if, `data` is not provided, then the keyword arguments will be used in place of data provided as a :obj:`dict`.

        .. todo::

          add any `kwargs` to an existing `data` :obj:`dict`

        Henceforth whatever is rounded up to use shall be referred to as the `data`.

        The initialization routine creates an attribute on the instance for
        each key in the `data`, and then attempts to cast the value:

            1. to an :obj:`int`.

            2. If a :exc:`TypeError` is encountered, the unadulterated value is used.

            3. If only :exc:`ValueError` is raised, then it is casted to
               :obj:`float`

            4. if that causes another :exc:`ValueError` then it is matched
               against the :const:`.boolean_pattern` to see whether it matches,
               which is to say, whether it is a string containing "true" or
               "false".

            5. If so, a simple check is conducted to determine whether the
               match was four characters long: `True`.

            6. If it does not test positive for truth, it is considered to be
               `False`.

            7. But if it wasn't a match for the :const:`.boolean_pattern` at
               all, then its original value is preserved.

        Generally, instances of this class are used to present a particular
        module, such as a policy manager, with its configuration in a form
        which can be dereferenced with dot notation.  As such, values which
        cannot be casted to some other type are almost always left in their
        original form as `str`\ ings, because the `AttrDict` is being
        initialized with a sub-block of a :class:`~configparser.ConfigParser`
        as the source object, and its values will all be strings.

        """
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

    An implementation of :class:`~collections.abc.Mapping` which by default
    only processes and caches values from the data payload when they are
    accessed, to avoid a bunch of useless parsing.  Instances may be
    dereferenced like hashes, but the keys are also attributes on the instance,
    so they can be accessed without brackets and quotation marks.

    Once parsed, results are memoized.

    For example, a payload might look a bit like this, when it is first
    received from Postfix and turned into an array of one string per line:

    .. code:: python

      payload = [
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

    As an example of the class's utility, and using the above definition of
    `payload`, consider:

    .. code:: python

      from chapps.util import PostfixPolicyRequest

      ppr = PostfixPolicyRequest(payload)

      # all the following are true:
      ppr.sender == 'unauth@easydns.com'
      ppr.sasl_username == 'somebody@chapps.io'
      ppr.client_address == '10.10.10.10'

      # demonstrating the pseudo-attribute:
      ppr.recipients == ['bar@foo.tld']

    Instance attributes (apart from Postfix payload parameters):

      :_payload: the Postfix policy delegation request payload in string-per-line format

      :recipients: a pseudo-attribute of the policy request derived from the
         value of `recipient`, provided by Postfix, which may contain more
         than one comma-separated email address.  For reasons unknown, Postfix
         always provides a `recipient_count` of 0 before the DATA phase, so
         we rely upon counting the email addresses directly.

      :_recipients: memoization attribute for :meth:`.recipients`

    .. admonition:: Subclassing

      Because the purpose of the class is to present the contents of the
      initial payload as attributes, all internal attributes are
      prefaced with an underscore.

    .. document private functions
    .. automethod:: __getattr__

    """

    def __init__(self, payload: List[str], *args, **kwargs):
        """Store the payload.

        :param List[str] payload: strings which are formatted as 'key=val',
          including an empty entry at the end.

        This routine discards the last element of the list and stores the rest
        as `self._payload`.

        """
        self._payload = payload[0:-2]

    # the main reason for this class:
    # find and memoize as attributes the values in the request payload
    # means we cannot test existence of attrs by getattr or self.<attr>
    def __getattr__(self, attr: str) -> Optional[str]:
        """Overloaded in order to search for missing attributes in the payload

        :param str attr: the attribute which triggered this call

        :returns: the value found in the payload, or :obj:`None`

        :rtype: Optional[str]

        First, if the value of `attr` starts with an underscore, `None` is
        returned.  No lines of the payload start with an underscore.  This
        ensures that references to internal attributes of the class are not
        snarled up with the payload searches.

        Next, the payload is searched for the requested key-value pair,
        attempting to match `attr` against everything before the `=` sign.
        When a line is found, the contents after the `=` are stored as an
        attribute named `attr` (and so memoized), and the value is returned.
        Future attempts to obtain the value will encounter the attribute and
        not invoke :meth:`.__getattr__` again.

        A `DEBUG` level message is currently produced if no lines in the
        payload matched the requested payload data.  No errors are produced
        if a nonexistent `attr` starting with `_` is encountered.

        """
        if attr[0] == "_":  # leading underscores do not occur in the payload
            return None
        line = next(
            (l for l in self._payload if attr == l.split("=")[0]), None
        )
        if line:
            key, *values = line.split("=")
            value = "=".join(values)
            setattr(self, key, value)
            return value
        else:
            logger.debug(f"No lines in {self} matched {attr}.")
        return None

    # Since the datastructure can function as a hash, provide optimization
    def __getitem__(self, key) -> Optional[str]:
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
                k: "=".join(vs)
                for k, *vs in [l.split("=") for l in self._payload]
            }
            # Since we end up parsing the entire payload
            # optimize it for future random access
            for k, v in self._mapping.items():
                setattr(self, k, v)
        yield from self._mapping

    # The length of the PPR is considered to be the number of items stored
    def __len__(self) -> int:
        """Act like a dict and return the number of k,v pairs

        :returns: number of lines in the payload

        :rtype: int

        """
        return len(self._payload)

    # Representations of PPR use their own class name, and otherwise dump
    # the payload, but not a list of attributes
    def __repr__(self) -> str:
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
        """Memoize recipients as a list

        :returns: a list of strings which are the email addresses of recipients

        :rtype: List[str]

        A convenience method to split the 'recipient' datum into
        comma-separated tokens for easier counting.

        """
        if "_recipients" not in vars(self):
            self._recipients = (
                self.recipient.split(",")
                if self.recipient and len(self.recipient) > 0
                else []
            )
        return self._recipients

    def domain_from(self, email_address: str) -> str:
        """Given an email address, return the domain part

        Raises meaningful errors if nonconforming conditions are encountered.
        """
        parts = email_address.split("@")
        if len(parts) > 2:
            logger.info(
                "Found sender email with more than one at-sign: "
                f"sender={email_address} instance={self.instance} "
                f"parts={parts!r}"
            )
            raise TooManyAtsException(f"{email_address}=>{parts!r}")
        elif len(parts) == 1:
            logger.info(
                "Found sender string without at-sign: "
                f"sender={email_address} instance={self.instance} "
                f"parts={parts!r}"
            )
            raise NotAnEmailAddressException
        return parts[-1]
