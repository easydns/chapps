"""Classes related to outbound traffic"""
from chapps.util import PostfixPolicyRequest
from chapps.config import config
import logging, chapps.logging

logger = logging.getLogger( __name__ )
logger.setLevel( logging.DEBUG )

class OutboundPPR(PostfixPolicyRequest): # empty line eliminated for paste-ability
    memoized_routines = dict()
    ### Initialize with optional config, in order to allow site-specific user-search path
    def __init__(self, payload, *, cfg=None):
        super().__init__(payload)
        self.config = cfg or config
        self.config = self.config.chapps
    ### create a property handler for "user"
    @property
    def user(self):
        if not '_user' in self.__dict__:
            self._user = self._get_user()
        return self._user
    ### not intended for public use, this routine creates and memoizes a routine if need be
    ### it also uses that routine to return the value to be used to track a user
    def _get_user(self):
        """Obtain the user value, and memoize the procedure"""
        ### see if we already have a procedure from some previous iteration
        get_user = self.__class__.memoized_routines.get('get_user', None)
        config = self.config
        ### if there is no procedure, we build one
        if not get_user:
            qk_list = [ 'sasl_username', 'ccert_subject', 'sender', 'client_address' ]
            qk = config.user_key
            if qk and qk != qk_list[0]:
                qk_list = [ qk, *qk_list ]
            def get_user(ppr):
                for k in qk_list:  # avoiding a list-comp here because I'd rather not evaluate getattr any more times than I have to
                    user = getattr( ppr, k, None )
                    if user and user != 'None':
                        logger.debug(f"Selecting quota-identifier {user} from key {k}")
                        return user
                raise ValueError(f"None of the following keys had values in the provided PPR: {qk_list}")
            ### this memoizes the procedure for finding the user
            self.__class__.memoized_routines['get_user'] = get_user
        ### execute the procedure and return the result
        return get_user(self)
