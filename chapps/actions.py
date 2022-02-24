"""Actions: instructions for the MTA, based on policy module output"""
import functools
from chapps.config import config
from chapps.policy import GreylistingPolicy

class PostfixActions:
    """Superclass for Postfix action adapters"""
    @staticmethod
    def dunno(*args, **kwargs):
        return "DUNNO"

    @staticmethod
    def okay(*args, **kwargs):
        return "OK"
    ok = okay

    @staticmethod
    def defer_if_permit(msg, *args, **kwargs):
        return f"DEFER_IF_PERMIT {msg}"

    @staticmethod
    def reject(msg, *args, **kwargs):
        return f"REJECT {msg}"

    @staticmethod
    def prepend(msg, *args, **kwargs):
        new_header = kwargs.get( 'prepend', None )
        if new_header is None or len( new_header ) < 5:
            raise ValueError( f"Prepended header expected to be at least 5 chars in length.")
        return f"PREPEND {new_header}"

    def __init__(self, cfg=None, extended_status=True):
        self.config = cfg or config
        self.extended_status = extended_status # intended to allow choice whether to use extended status; TODO: not currently implemented

    def _get_closure_for(self, decision):
        """Setup the prescribed closure for generating SMTP action directives"""
        action_config = getattr( self.config, decision, None )
        if not action_config:
            raise ValueError( f"Action config for {self.__class__.__name__} does not contain a key named {decision}" )
        action_tokens = action_config.split(' ')
        action = action_tokens[0]
        try:
            i = int( action )  #  if the first token is a number, its a directive
        except ValueError:  #  first token was a string, and therefore refers to a method
            af = getattr( self, action, None )
            if af:
                return af
            action_func = getattr( PostfixActions, action, None )
            if not action_func:
                action_func = getattr( self.__class__, action, None )
            if not action_func:
                raise NotImplementedError( f"Action {action} is not implemented by PostfixActions or by {self.__class__.__name__}" )
        else:
            action_func = lambda reason, ppr, *args, **kwargs: action_config.format(reason=reason)
        setattr( self, action, action_func )
        return action_func

    def _get_message_for(self, decision, config_name=None):
        """Grab a status message for a decision from the config, optionally with another name"""
        msg_key = config_name or decision
        msg = getattr( self, msg_key, None )
        if not msg:
            raise ValueError( f"There is no key {msg_key} in the config for {self.__class__.__name__} or its policy" )
        return msg

    def _mangle_action(self, action):
        """Policy decisions which are also reserved words will need to be altered"""
        if action == 'pass':
            return 'passing'
        return action

    def action_for(self, *args, **kwargs):
        raise NotImplementedError(f"Subclasses of {self.__class__.__name__} must define the method action_for() for themselves, to map policy module response (decision) strings onto Postfix action directives.")

class PostfixPassfailActions( PostfixActions ):
    def __init__(self, cfg=None):
        super().__init__( cfg )

    def _get_closure_for(self, decision, msg_key=None):
        """Create a closure for formatting these messages and store it on self.<decision>, and also return it"""
        msg_key = msg_key or decision
        msg = getattr( self.config, msg_key, None )
        if not msg:
            raise ValueError( f"The key {msg_key} is not defined in the config for {self.__class__.__name__} or its policy" )
        msg_tokens = msg.split(' ')
        msg_text = ''
        if msg_tokens[0] == 'OK':
            func = PostfixActions.okay
        elif msg_tokens[0] == 'DUNNO':
            func = PostfixActions.dunno
        elif msg_tokens[0] == 'DEFER_IF_PERMIT':
            func = PostfixActions.defer_if_permit
            msg_text = ' '.join( msg_tokens[1:] )
        elif msg_tokens[0] == 'REJECT' or msg_tokens[0] == '554':
            func = PostfixActions.reject
            msg_text = ' '.join( msg_tokens[1:] )
        else:
            raise NotImplementedError( f"Pass-fail closure creation for Postfix directive {msg_tokens[0]} is not yet available." )
        action = self.__prepend_action_with_message( func, msg_text )
        setattr( self, decision, action )
        return action

    def __prepend_action_with_message(self, func, prepend_msg_text):
        ### avoiding use of nonlocal required if definition is embedded inline in calling procedure
        def action(message="", *args, **kwargs):
            msg_text = prepend_msg_text
            if len( message ) > 0:
                msg_text = ' '.join([ msg_text, message ])
            return func( msg_text, *args, **kwargs )
        return action

    def action_for(self, pf_result):
        if pf_result:   # True / pass
            action_name = 'passing'
        else:           # False / fail
            action_name = 'fail'
        return getattr( self, action_name, None )

    def __getattr__(self, attrname, *args, **kwargs):
        attrname = self._mangle_action( attrname )
        if attrname == 'passing':
            msg_key = 'acceptance_message'
        elif attrname == 'fail':
            msg_key = 'rejection_message'
        else:
            raise NotImplementedError( f"Pass-fail actions do not include {attrname}" )
        return self._get_closure_for( attrname, msg_key )

class PostfixOQPActions( PostfixPassfailActions ):
    def __init__(self, cfg=None):
        super().__init__( cfg )
        self.config = self.config.policy_oqp

class PostfixGRLActions( PostfixPassfailActions ):
    def __init__(self, cfg=None):
        super().__init__( cfg )
        self.config = self.config.policy_grl

class PostfixSPFActions( PostfixActions ):
    greylisting_policy = GreylistingPolicy()
    @staticmethod
    def greylist(msg, *args, **kwargs):
        ppr = kwargs.get( 'ppr', None )
        if ppr is None:
            raise ValueError( f"PostfixSPFActions.greylist() expects a ppr= kwarg providing the PPR for greylisting.")
        if PostfixSPFActions.greylisting_policy.approve_policy_request( ppr ):
            passing = PostfixSPFActions().action_for('pass')
            return passing( msg, ppr, *args, **kwargs )
        if len(msg) == 0:
            msg = 'due to SPF enforcement policy'
        return PostfixGRLActions().fail( msg, ppr, *args, **kwargs )

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.config = self.config.actions_spf

    def _mangle_action(self, action):
        if action == 'none' or action == 'neutral':
            action = 'none_neutral'
        else:
            action = super()._mangle_action( action )
        return action

    def action_for(self, spf_result):
        spf_result = self._mangle_action( spf_result )
        action = getattr( self, spf_result, None )
        if action:
            return action
        return self._get_closure_for( spf_result )  #  this memoizes its result
