"""Classes related to outbound traffic"""
from chapps.util import PostfixPolicyRequest
from chapps.config import config
from chapps.signals import ConfigurationError, AuthenticationFailureException
import logging, chapps.logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class OutboundPPR(PostfixPolicyRequest):  # empty line eliminated for paste-ability
    memoized_routines = dict()
    # Initialize with optional config, in order to allow site-specific user-search path
    def __init__(self, payload, *, cfg=None):
        super().__init__(payload)
        self._config = cfg or config
        self._config = self._config.chapps

    @classmethod
    def clear_memoized_routines(cls):
        cls.memoized_routines.clear()

    def __str__(self):
        try:
            return f"OutboundPPR({self.user}:{self.instance} as {self.sender}, #recip={len(self.recipients)})"
        except Exception:
            return f"OutboundPPR(:{self.instance}) is missing sender and/or user_key"

    ### create a property handler for "user"
    @property
    def user(self):
        if not "_user" in self.__dict__:
            try:
                self._user = self._get_user()
            except ValueError as e:
                if self._config.require_user_key:
                    raise AuthenticationFailureException()
                else:
                    raise e
        return self._user

    # this routine creates and memoizes a routine if need be
    # it also uses that routine to return the value to be used to track a user
    def _get_user(self):
        """Obtain the user value, and memoize the procedure"""
        # see if we already have a procedure from some previous iteration
        get_user = self.__class__.memoized_routines.get("get_user", None)
        cfg = self._config
        # if there is no procedure, we build one
        if not get_user:
            if cfg.require_user_key:
                logger.debug(f"configfile={cfg.config_file}, cfg.require_user_key={cfg.require_user_key}")
                if not cfg.user_key:
                    raise ConfigurationError(
                        ("If require_user_key is True, "
                         "then user_key must be set.")
                    )
                qk_list = [cfg.user_key]
            else:
                qk_list = [
                    "sasl_username",
                    "ccert_subject",
                    "sender",
                    "client_address"
                ]
                qk = cfg.user_key
                if qk and qk != qk_list[0]:
                    qk_list = [qk, *qk_list]

            def get_user(ppr):
                for k in qk_list:
                    user = getattr(ppr, k, None)
                    if user and user != "None":
                        logger.debug(
                            f"Selecting quota-identifier {user} from key {k}"
                        )
                        return user
                raise ValueError(
                    ("None of the following keys had values in "
                     f"the provided PPR: {qk_list}")
                )

            # this memoizes the procedure for finding the user
            self.__class__.memoized_routines["get_user"] = get_user
        # execute the procedure and return the result
        return get_user(self)
