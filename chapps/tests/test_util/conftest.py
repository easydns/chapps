"""pytest config for chapps.util"""

import pytest

@pytest.fixture
def mock_config_dict():
    return dict(
        intval='99',
        floatval='9.9',
        stringval='ninety-nine',
        boolean='True'
    )

@pytest.fixture
def postfix_sasl_username():
    users = [
        "ccullen@easydns.com",
        "ted@easydns.com",
        "some_dummy.quota_user@theirowndomain.com"
    ]
    return users[0]

@pytest.fixture
def postfix_policy_request_payload():
    def _pprp( email='ccullen@easydns.com', recipients=None, instance=None, **kwargs ):
        namespace = dict(
            sender=email,
            sasl_username=email,
            ccert_subject=email,
            helo_name='mail.chapps.io',
            queue_id='8045F2AB23',
            recipient_count='0',
            client_address='10.10.10.10',
            client_name='mail.chapps.io',
            reverse_client_name='mail.chapps.io',
            size='12345',
        )
        namespace.update( kwargs )
        if 'recipient' not in namespace:
            recipients = recipients or namespace.get( 'recipients', None ) or ['bar@foo.tld']
            namespace[ 'recipient' ] = ','.join( recipients )
        if 'instance' not in namespace:
            namespace[ 'instance' ] = instance or 'a483.61706bf9.17663.0'
        payload = \
"""request=smtpd_access_policy
protocol_state=RCPT
protocol_name=SMTP
helo_name=helo.chapps.io
queue_id=8045F2AB23
sender={sender}
recipient={recipient}
recipient_count=0
client_address=10.10.10.10
client_name=mail.chapps.io
reverse_client_name=mail.chapps.io
instance={instance}
sasl_method=plain
sasl_username={sasl_username}
sasl_sender=
size=12345
ccert_subject={ccert_subject}
ccert_issuer=Caleb+20Cullen
ccert_fingerprint=DE:AD:BE:EF:FE:ED:AD:DE:D0:A7:52:F3:C1:DA:6E:04
encryption_protocol=TLSv1/SSLv3
encryption_cipher=DHE-RSA-AES256-SHA
encryption_keysize=256
etrn_domain=
stress=
ccert_pubkey_fingerprint=68:B3:29:DA:98:93:E3:40:99:C7:D8:AD:5C:B9:C9:40
client_port=1234
policy_context=submission
server_address=10.3.2.1
server_port=54321

""".format( **namespace )
        return payload.encode('utf-8')
    return _pprp

@pytest.fixture
def postfix_policy_request_message(postfix_policy_request_payload):
    def _ppr( email=None, recipients=None, **kwargs ):
        return postfix_policy_request_payload( email, recipients, **kwargs ).decode('utf-8').split("\n")
    return _ppr
