"""
Actions
-------

These classes intepret policy manager output to produce instructions for Postfix."""
import functools
from typing import Optional
from chapps.config import config
from chapps.policy import GreylistingPolicy
from chapps.models import PolicyResponse

policy_response = PolicyResponse.policy_response


class PostfixActions:
    """Superclass for Postfix action adapters"""

    @staticmethod
    def dunno(*args, **kwargs):
        """Return the Postfix directive `DUNNO`"""
        return "DUNNO"

    @staticmethod
    def okay(*args, **kwargs):
        """Return the Postfix directive `OK`"""
        return "OK"

    ok = okay
    """`ok()` is an alias for `okay()`"""

    @staticmethod
    def defer_if_permit(msg, *args, **kwargs):
        """
        Return the Postfix `DEFER_IF_PERMIT` directive with the provided
        message
        """
        return f"DEFER_IF_PERMIT {msg}"

    @staticmethod
    def reject(msg, *args, **kwargs):
        """
        Return the Postfix `REJECT` directive along with the provided message
        """
        return f"REJECT {msg}"

    @staticmethod
    def prepend(*args, **kwargs):
        """
        Return the Postfix `PREPEND` directive.
        Include the header to prepend as keyword-argument `prepend`
        """
        new_header = kwargs.get("prepend", None)
        if new_header is None or len(new_header) < 5:
            raise ValueError(
                f"Prepended header expected to be at least 5 chars in length."
            )
        return f"PREPEND {new_header}"

    def __init__(self, cfg=None):
        """
        Optionally supply a :py:class:`chapps.config.CHAPPSConfig` instance as
        the first argument.
        """
        self.cfg = cfg or config
        self.config = self.cfg  # later this is overridden, in subclasses

    def _get_closure_for(
        self, decision: str, wrapper: Optional[callable] = None
    ):
        """Setup the prescribed closure for generating SMTP action directives"""
        action_config = getattr(self.config, decision, None)
        if not action_config:
            raise ValueError(
                f"Action config for {self.__class__.__name__} does not contain a key named {decision}"
            )
        action_tokens = action_config.split(" ")
        action = action_tokens[0]
        try:
            i = int(action)  #  if the first token is a number, its a directive
        except ValueError:  #  first token was a string, and therefore refers to a method
            # look for predefined or memoized version
            af = getattr(self, action, None)
            if af:
                return af
            # no local version found, find function reference
            action_func = getattr(PostfixActions, action, None)
            if not action_func:
                action_func = getattr(self.__class__, action, None)
            if not action_func:
                raise NotImplementedError(
                    f"Action {action} is not implemented by PostfixActions"
                    f" or by {self.__class__.__name__}"
                )
        else:
            # construct closure from configured message string
            action_func = lambda reason, ppr, *args, **kwargs: action_config.format(
                reason=reason
            )
        action_func = policy_response(action_func != self.reject, action)(
            action_func
        )
        # memoize the action function for quicker reference next time
        setattr(self, action, action_func)
        return action_func

    def _get_message_for(self, decision, config_name=None):
        """Grab a status message for a decision from the config, optionally with another name"""
        msg_key = config_name or decision
        msg = getattr(self, msg_key, None)
        if not msg:
            raise ValueError(
                f"There is no key {msg_key} in the config for {self.__class__.__name__} or its policy"
            )
        return msg

    def _mangle_action(self, action):
        """
        Policy decisions which are also reserved words need to be altered.
        Currently, this routine handles only the action 'pass'
        """
        if action == "pass":
            return "passing"
        return action

    def action_for(self, *args, **kwargs):
        """Abstract method which must be implemented in subclasses.

        This method is intended to map responses from a policy
        manager onto Postfix directives.

        Not all policy managers return only yes/no answers.  Some, like
        :py:class:`chapps.spf_policy.SPFEnforcementPolicy`, return a handful of
        different possible values, and so there must be a mechanism for
        allowing sites to determine what happens when each of those different
        outcomes occurs.

        """
        raise NotImplementedError(
            f"Subclasses of {self.__class__.__name__} must define the method"
            " action_for() for themselves, to map policy module responses"
            " (decisions) onto Postfix action directives."
        )


class PostfixPassfailActions(PostfixActions):
    """Postfix Actions adapter for PASS/FAIL policy responses.

    Many policies return `True` if the email should be accepted/forwarded and
    return `False` if the email should be rejected/dropped.  This class
    encapsulates the common case, and includes some logic to extract precise
    instructions from the config.

    """

    def __init__(self, cfg=None):
        super().__init__(cfg)

    def _get_closure_for(self, decision, msg_key=None):
        """Create a closure for formatting these messages and store it on
        self.<decision>, and also return it
        """
        msg_key = msg_key or decision
        msg = getattr(self.config, msg_key, None)
        if not msg:
            raise ValueError(
                f"The key {msg_key} is not defined in the config for"
                f" {self.__class__.__name__} or its policy"
            )
        msg_tokens = msg.split(" ")
        msg_text = ""
        if msg_tokens[0] == "OK":
            func = PostfixActions.okay
        elif msg_tokens[0] == "DUNNO":
            func = PostfixActions.dunno
        elif msg_tokens[0] == "DEFER_IF_PERMIT":
            func = PostfixActions.defer_if_permit
            msg_text = " ".join(msg_tokens[1:])
        elif msg_tokens[0] == "REJECT" or msg_tokens[0] == "554":
            func = PostfixActions.reject
            msg_text = " ".join(msg_tokens[1:])
        else:
            raise NotImplementedError(
                "Pass-fail closure creation for Postfix directive"
                f" {msg_tokens[0]} is not yet available."
            )
        action = policy_response(func != PostfixActions.reject, decision)(
            self.__prepend_action_with_message(func, msg_text)
        )
        setattr(self, decision, action)
        return action

    def __prepend_action_with_message(self, func, prepend_msg_text):
        """Wrap an action func in order to prepend an additional message"""
        # avoiding use of nonlocal required if definition is embedded inline
        # in calling procedure
        def action(message="", *args, **kwargs):
            msg_text = prepend_msg_text
            if len(message) > 0:
                msg_text = " ".join([msg_text, message])
            return func(msg_text, *args, **kwargs)

        return action

    def action_for(self, pf_result):
        """Return an action closure for a pass/fail policy

        Evaluates its argument `pf_result` as a boolean and returns the
        action closure for 'passing' if True, otherwise the action closure for
        'fail'.  To provide backwards-compatibility with older versions, and to
        allow for more descriptive configuration elements, the actions may be
        attached to keys named `acceptance_message` or `rejection_message`
        instead of `passing` and `fail` respectively.  This is only true
        of policies with action factories inheriting from
        :py:class:`chapps.actions.PostfixPassfailActions`

        """
        if pf_result:  # True / pass
            action_name = "passing"
        else:  # False / fail
            action_name = "fail"
        return getattr(self, action_name, None)

    def __getattr__(self, attrname, *args, **kwargs):
        """Allow use of old config elements with long descriptive names."""
        attrname = self._mangle_action(attrname)
        if attrname == "passing":
            msg_key = "acceptance_message"
        elif attrname == "fail":
            msg_key = "rejection_message"
        else:
            raise NotImplementedError(
                f"Pass-fail actions do not include {attrname}"
            )
        return self._get_closure_for(attrname, msg_key)


class PostfixOQPActions(PostfixPassfailActions):
    """Postfix Action translator for :py:class:`chapps.policy.OutboundQuotaPolicy`"""

    def __init__(self, cfg=None):
        """
        Optionally provide an instance of :py::class`chapps.config.CHAPPSConfig`.

        All this class does is wire up `self.config` to
        point at the :py:class:`chapps.policy.OutboundQuotaPolicy` config block.
        """
        super().__init__(cfg)
        self.config = self.config.policy_oqp


class PostfixGRLActions(PostfixPassfailActions):
    """Postfix Action translator for :py:class:`chapps.policy.GreylistingPolicy`"""

    def __init__(self, cfg=None):
        """
        Optionally provide an instance of :py:class:`chapps.config.CHAPPSConfig`.

        All this class does is wire up `self.config` to
        point at the :py:class:`chapps.policy.GreylistingPolicy` config block.
        """
        super().__init__(cfg)
        self.config = self.config.policy_grl


class PostfixSPFActions(PostfixActions):
    """
    Postfix Action translator for :py:class:`chapps.policy.SPFEnforcementPolicy`

    .. caution::

        The SPF functionality of CHAPPS is not considered complete.  YMMV

    """

    greylisting_policy = GreylistingPolicy()
    """
    Reference to a class-global :py:class:`chapps.policy.GreylistingPolicy`
    instance.

    This implementation is poor and will change in future revisions.

    .. todo::

      Implement `greylisting_policy` as a class-level pseudo-property,
      using a class-attribute dict for memoization storage.

    """

    @staticmethod
    def greylist(msg, *args, **kwargs):
        """This method is meant to share the same signature as the other
        action methods, mainly defined on :py:class:`chapps.actions.PostfixActions`

        The `greylist` action causes the email in question to be
        greylisted, according to the policy.  The `msg` is used as
        the message for the Postfix directive, or if the message has
        no contents and the email is being deferred, the string
        "due to SPF enforcement policy" is used.  Because the greylisting
        policy's message is prepended later, the actual message delivered
        by Postfix will look something like "greylisted due to SPF
        enforcement policy".

        Right now :py:class:`chapps.actions.PostfixSPFActions` uses a
        declared class-global :py:class:`chapps.policy.GreylistingPolicy`
        instance, which will change in a future revision so that an overriding
        config may be provided for initialization of that instance.

        """
        ppr = kwargs.get("ppr", None)
        if ppr is None:
            raise ValueError(
                "PostfixSPFActions.greylist() expects a ppr= kwarg "
                "providing the PPR for greylisting."
            )
        if PostfixSPFActions.greylisting_policy.approve_policy_request(
            ppr, force=True
        ):
            passing = PostfixSPFActions().action_for("pass")
            return passing(msg, ppr, *args, **kwargs)
        if len(msg) == 0:
            msg = "due to SPF enforcement policy"
        return PostfixGRLActions().fail(msg, ppr, *args, **kwargs)

    def __init__(self, cfg=None):
        """Optionally pass CHAPPSConfig override.

        All this init routine needs to do is adjust `self.config` to refer to
        the `[PostfixSPFActions]` config block.

        """
        super().__init__(cfg)
        self.config = self.config.actions_spf

    def _mangle_action(self, action):
        """
        Perform additional mangling to turn either of 'none' or 'neutral' into
        the same symbol, 'none_neutral'

        """
        if action == "none" or action == "neutral":
            action = "none_neutral"
        else:
            action = super()._mangle_action(action)
        return action

    def action_for(self, spf_result):
        """

        Override
        :py:meth:`chapps.actions.PostfixActions.action_for()` to provide
        action closures for the different SPF results.  The closures are
        memoized, so that they only need be constructed once per runtime.

        """
        spf_result = self._mangle_action(spf_result)
        action = getattr(self, spf_result, None)
        if action:
            return action
        return self._get_closure_for(spf_result)  #  this memoizes its result
