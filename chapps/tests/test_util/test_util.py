"""CHAPPS Utilities Tests

.. todo::

  Write tests for :class:`~chapps.util.VenvDetector`

"""
import pytest
from pprint import pprint as ppr
from chapps.util import AttrDict, PostfixPolicyRequest

pytestmark = pytest.mark.order(1)


class Test_AttrDict:
    def test_attr_dict_return_int(self, mock_config_dict):
        ad = AttrDict(mock_config_dict)
        assert ad.intval == int(mock_config_dict["intval"])

    def test_attr_dict_return_float(self, mock_config_dict):
        ad = AttrDict(mock_config_dict)
        assert ad.floatval == float(mock_config_dict["floatval"])

    def test_attr_dict_return_string(self, mock_config_dict):
        ad = AttrDict(mock_config_dict)
        assert ad.stringval == mock_config_dict["stringval"]

    def test_return_boolean(self, mock_config_dict):
        ad = AttrDict(mock_config_dict)
        assert ad.boolean == bool(mock_config_dict["boolean"])


class Test_PostfixPolicyRequest:
    def test_instantiate_ppr(self, postfix_policy_request_message):
        """
        :GIVEN: a policy data payload from Postfix
        :WHEN:  a new ppr object is instantiated from it
        :THEN:  a new ppr object should be returned containing a copy of that data
        """
        pprp = postfix_policy_request_message()
        new_ppr = PostfixPolicyRequest(pprp)
        for i, l in enumerate(new_ppr._payload):
            assert l == pprp[i]

    def test_attribute(self, postfix_policy_request_message):
        """
        :GIVEN: a ppr object with contents
        :WHEN:  an attribute is requested
        :THEN:  its value (from the payload) should be returned
        """
        pprp = postfix_policy_request_message(sender="srs=ccullen@easydns.com")
        new_ppr = PostfixPolicyRequest(pprp)

        for k, *vs in [l.split("=") for l in pprp[0:-2]]:
            v = "=".join(vs)
            assert getattr(new_ppr, k, None) == v

    def test_dereference(self, postfix_policy_request_message):
        """
        :GIVEN: a ppr object with contents
        :WHEN:  an attribute is dereferenced
        :THEN:  its value (from the payload) should be returned
        """
        pprp = postfix_policy_request_message()
        new_ppr = PostfixPolicyRequest(pprp)

        for k, *vs in [l.split("=") for l in pprp[0:-2]]:
            v = "=".join(vs)
            assert new_ppr[k] == v

    def test_iterable(self, postfix_policy_request_message):
        """
        :GIVEN: a ppr object with contents
        :WHEN:  an iterable is requested (as with items())
        :THEN:  a dict-iterator should be returned, containing the payload data
        """
        pprp = postfix_policy_request_message()
        new_ppr = PostfixPolicyRequest(pprp)

        for k, v in new_ppr.items():
            assert f"{k}={v}" in pprp

    def test_len(self, postfix_policy_request_message):
        """:GIVEN: a ppr object with contents
        :WHEN:  asked for length
        :THEN:  the number of parameters from the payload should be returned

          :NB: (the payload ends with an extra blank line)

        """
        pprp = postfix_policy_request_message()
        new_ppr = PostfixPolicyRequest(pprp)

        assert len(new_ppr) == len([l for l in pprp if len(l) > 0])

    def test_recipients(self, postfix_policy_request_message):
        """:GIVEN: a PPR w/ more than one recipient listed
        :WHEN: the pseudo-attribute `recipients` is accessed
        :THEN: a list should be returned with one element per recipient

        """
        new_ppr = PostfixPolicyRequest(
            postfix_policy_request_message(
                "underquota@chapps.io",
                [
                    "one@recipient.com",
                    "two@recipient.com",
                    "three@recipient.com",
                ],
            )
        )

        r = new_ppr.recipients
        assert type(r) == list
        assert len(r) == 3
        assert r[0] == "one@recipient.com"
