"""Tests for response-action adapter objects"""
import pytest
from chapps.actions import PostfixActions, PostfixSPFActions

class Test_PostfixActions:
    """Tests for abstract Postfix action superclass"""
    def test_okay(self, postfix_actions):
        """Returns OK"""
        result = postfix_actions.okay()
        assert result == "OK"

    def test_okay_accepts_useless_message(self, postfix_actions):
        """Returns OK even if a message is supplied"""
        arbitrary_message = "This message will be ignored."
        result = postfix_actions.okay( arbitrary_message )
        assert result == "OK"

    def test_dunno(self, postfix_actions):
        """Returns DUNNO"""
        result = postfix_actions.dunno()
        assert result == "DUNNO"

    def test_dunno_accepts_useless_message(self, postfix_actions):
        """Returns DUNNO even if a message is supplied"""
        arbitrary_message = "This message will be ignored."
        result = postfix_actions.dunno( arbitrary_message )
        assert result == "DUNNO"

    def test_action_for_raises_not_implemented_error(self, postfix_actions):
        """The method action_for() is abstract and not implemented by PostfixActions"""
        with pytest.raises( NotImplementedError ):
            assert postfix_actions.action_for( 'foo' )

class Test_PostfixOQPActions:
    """Testing outbound quota actions for Postfix"""
    def test_pass_yields_okay(self, oqp_actions):
        """Pass returns OK"""
        ### When the calling routine gets True from the policy, it will call .pass()
        ### and when it gets false, it will call .fail()
        ### It may be that the acceptance message, even for outbound quota, should still be DUNNO
        result = oqp_actions.passing()
        assert result == 'OK' or result == 'DUNNO'

    def test_fail_yields_rejection(self, oqp_actions):
        """Fail returns a string starting with '554 Rejected' or 'REJECT'"""
        ### Postfix will insert enhanced status code 5.7.1 which is the code
        ###   we want anyhow.  There seems to be no code for gateways to use
        ###   to signal that the user's outbound quota has been reached.
        result = oqp_actions.fail()
        assert result[0:7] == 'REJECT ' or result[0:12] == '554 Rejected'

class Test_PostfixGRLActions:
    """Testing greylisting actions for Postfix"""
    def test_pass_yields_dunno(self, grl_actions):
        """Pass returns DUNNO"""
        result = grl_actions.passing()
        assert result == 'DUNNO'

    def test_fail_yields_rejection(self, grl_actions):
        """Fail returns a string starting with DEFER_IF_PERMIT"""
        result = grl_actions.fail()
        assert result[0:16] == 'DEFER_IF_PERMIT '

class Test_PostfixSPFActions:
    """Tests for Postfix action strings to be sent in response to particular SPF results:
       The possible results are:
           pass*
           fail*
           softfail
           temperror*
           permerror*
           none/neutral (two which must be treated the same)
       Starred items are ones for which RFC 7208 provides recommended SMTP result codes.
       For now, configuration will be able to override how the non-starred results are mapped onto
       actions taken for other classes of message.
       Eventually a response which implements greylisting (say, for softfails) will be provided,
       which could be applied also to none/neutral situations as well.
    """
    def test_pass_produces_prepend(self, spf_actions, spf_reason):
        result = spf_actions.action_for( 'pass' )
        assert result == PostfixActions.prepend

    def test_fail_produces_reject(self, spf_actions, spf_reason):
        result = spf_actions.action_for( 'fail' )
        message = result( spf_reason, None )
        assert message.split(' ')[0] == 'REJECT' or message[0] == '5'

    def test_temperror_produces_enhanced_code(self, spf_actions, spf_reason):
        result = spf_actions.action_for( 'temperror' )
        message = result( spf_reason, None )
        assert message[0:9] == '451 4.4.3'

    def test_permerror_produces_enhanced_code(self, spf_actions, spf_reason):
        result = spf_actions.action_for( 'permerror' )
        message = result( spf_reason, None )
        assert message[0:9] == '550 5.5.2'

    def test_none_produces_greylist(self, spf_actions):
        result = spf_actions.action_for( 'none' )
        assert result == PostfixSPFActions.greylist

    def test_neutral_produces_greylist(self, spf_actions):
        result = spf_actions.action_for( 'neutral' )
        assert result == PostfixSPFActions.greylist

    def test_softfail_produces_greylist(self, spf_actions):
        result = spf_actions.action_for( 'softfail' )
        assert result == PostfixSPFActions.greylist
