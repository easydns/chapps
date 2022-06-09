"""
OutboundPPR
-----------

And possibly other classes related to outbound traffic, but right now there is
only one, which is an outbound-only subclass of
:py:class:`chapps.util.PostfixPolicyRequest`.

"""
from typing import List
from chapps.util import PostfixPolicyRequest
from chapps.config import config, CHAPPSConfig
from chapps.signals import ConfigurationError, AuthenticationFailureException
import logging

logger = logging.getLogger(__name__)


class OutboundPPR(PostfixPolicyRequest):
    """Encapsulates logic to identify the authenticated user sending the email.

    Ignoring non-authenticated email attempts, which I think everyone does
    today, outbound requests should all be associated to a known user who has
    authenticated to Postfix.  Postfix provides information in the payload
    which can be used to identify the user.  That piece of data may then be
    used to apply policies to the outbound email of a particular user.

    In order to allow for the possibility that other sites might prefer to use
    arbitrary bits of the Postfix policy request payload to identify users,
    CHAPPS allows for the key used to extract that data to be specified in the
    config file.  At present, there is no support for combining more than one
    key.

    .. admonition:: Notes about subclassing

       Don't forget that the normal attribute space is reserved for the payload
       data.  All internal attributes should start with `_` (underscore).

    .. todo::

      Arbitrary user-key composition functionality could be achieved by a
      classmethod setting the user-getter routine, accepting as its argument a
      closure which accepts a :class:`~chapps.util.PostfixPolicyRequest` and
      returns a string which is the user-identifier.

    """

    _memoized_routines = dict()

    def __init__(self, payload: List[str], *, cfg: CHAPPSConfig = None):
        """Create a new outbound policy request"""
        super().__init__(payload)
        self._config = cfg or config
        self._params = self._config.chapps
        if cfg:
            logger.debug(
                "Got override config from file: " + cfg.chapps.config_file
            )
        else:
            logger.debug(
                "Using global config based on: " + self._params.config_file
            )

    @classmethod
    def clear_memoized_routines(cls) -> None:
        """Clear all memoized routines

        This mainly exists to facilitate testing.

        """
        cls._memoized_routines.clear()

    def __str__(self):
        """In certain contexts, `str(<o_ppr>)` is used for brevity

        The routine tries to use the `user` which is the point of the class,
        but if it cannot determine a non-nil user name, it falls back to
        printing a bit of extra detail.

        """
        try:
            return (
                f"i={self.instance} "
                f"user={self.user} "
                f"sender={self.sender or 'None'} "
                f"client_address={self.client_address} "
                f"recipient={self.recipient}"
            )
        except Exception:
            return (
                f"i={self.instance} "
                f"sasl_username={self.sasl_username or 'None'} "
                f"ccert_subject={self.ccert_subject or 'None'} "
                f"sender={self.sender or 'None'} "
                f"client_address={self.client_address} "
                f"recipient={self.recipient}"
            )

    @property
    def user(self) -> str:
        """Return and memoize the user-identifier.

        :returns: the user-identifier

        :rtype: str

        :raise AuthenticationFailureException: when no user-identifier can be
          found, and the `require_user_key` setting of the `[CHAPPS]` section
          of the config is set to :obj:`True`

        :raise ValueError: when no user-identifier is found, but user keys
          are not required

        The underlying routine raises :exc:`ValueError` when no user-identifier
        can be found.  If the config stipulates that a user-identifier must be
        found, this routine raises :exc:`AuthenticationFailureException` to
        signal that the email originated from a source which did not
        authenticate.

        """
        if not "_user" in self.__dict__:
            try:
                self._user = self._get_user()
            except ValueError as e:
                if self._params.require_user_key:
                    raise AuthenticationFailureException()
                else:
                    raise e
        return self._user

    # this routine creates and memoizes a routine if need be
    # it also uses that routine to return the value to be used to track a user
    def _get_user(self) -> str:
        """Obtain the user value, and memoize the procedure

        In an attempt to support as many different configuration scenarios as
        possible, the codebase can attempt to find a user-identifier in a few
        different places, in a search path.  Since it is possible to configure
        this search path via the config file, the actual search function is
        produced as a closure and memoized at the class level, so that all
        future instances will be able to use the same function without creating
        a new (identical) closure first.

        The closure produced by this factory raises :exc:`ValueError` if it
        cannot find a non-nil user-identifier.

        .. note::

           Any alternate closure provided for this purpose should also raise
           :exc:`ValueError` if no user-identifier can be found, as it is
           handled explicitly in :meth:`.user`

        :meta public:

        """
        # see if we already have a procedure from some previous iteration
        get_user = self.__class__._memoized_routines.get("get_user", None)
        cfg = self._params
        # if there is no procedure, we build one
        # logger.debug("Using config file: " + cfg.config_file)
        if not get_user:
            if cfg.require_user_key:
                if not cfg.user_key:
                    raise ConfigurationError(
                        (
                            "If require_user_key is True, "
                            "then user_key must be set."
                        )
                    )
                qk_list = [cfg.user_key]
                # logger.debug(
                #     f"User key required; {cfg.user_key} must appear in PPRs."
                # )
            else:
                qk_list = [
                    "sasl_username",
                    "ccert_subject",
                    "sender",
                    "client_address",
                ]
                qk = cfg.user_key
                if qk and qk != qk_list[0]:
                    qk_list = [qk, *qk_list]
                # logger.debug(
                #     "User key not required.  Using search path: "
                #     + (":".join(qk_list))
                # )

            def get_user(ppr):
                for k in qk_list:
                    user = getattr(ppr, k, None)
                    if user and user != "None":
                        # logger.debug(
                        #     f"Selecting user-identifier {user} from key {k}"
                        # )
                        return user
                raise ValueError(
                    (
                        "None of the following keys had values in "
                        f"the provided PPR: {qk_list}"
                    )
                )

            # this memoizes the procedure for finding the user
            self.__class__._memoized_routines["get_user"] = get_user
        # execute the procedure and return the result
        return get_user(self)
