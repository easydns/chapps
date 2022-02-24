"""Global services test fixtures"""
import os
import pytest
from pytest import fixture
from chapps.tests.test_config.conftest import chapps_mock_config, chapps_mock_cfg_path, _chapps_mock_config_file
from chapps.tests.test_adapter.conftest import _adapter_fixture, _database_fixture, _populated_database_fixture, _mdbqadapter_fixture

def test_message_factory(sn, ln=None, *, subject='{sn} Testing'):
    """If module is a string, we use it as both short and long name, otherwise, it is a duple of (short, long)"""
    if ln is None:
        ln = sn
    message_lines = [ "From: {sender}",
                     "Subject: {subject}",
                     "To: {recipient}",
                     "",
                     f"This test message was created by automated testing of {ln}",
                     "Please disregard." ]
    message_text = "\n".join( message_lines )
    default_subject = subject.format(**locals())
    def __message_factory( sender, recipients, subject=default_subject ):
        recipient = recipients if type(recipients) == str else ",".join( recipients )
        return message_text.format(**locals())
    return __message_factory

def test_recipients():
    return [
        'ccullen@easydns.com',
    ]

def standard_sender():
    return "ccullen@easydns.com"

@fixture(scope='module')
def monkeypatch_module():
    from pytest import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()

@fixture(scope='session')
def monkeypatch_session():
    from pytest import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()

@fixture(scope='session')
def adapter_fixture():
    return _mdbqadapter_fixture()

@fixture(scope='session')
def finalizing_adapter(adapter_fixture):
    yield adapter_fixture
    adapter_fixture.finalize()

@fixture(scope='session')
def database_fixture(finalizing_adapter):
    yield from _database_fixture(finalizing_adapter)

@fixture(scope='session')
def populated_database_fixture(database_fixture):
    return _populated_database_fixture(database_fixture)

@fixture(scope='session')
def chapps_mock_config_file(chapps_mock_config, chapps_mock_cfg_path):
    yield from _chapps_mock_config_file( chapps_mock_config, chapps_mock_cfg_path )

@fixture(scope='session')
def chapps_mock_session(monkeypatch_session, chapps_mock_cfg_path):
    monkeypatch_session.setenv( 'CHAPPS_CONFIG', chapps_mock_cfg_path )
    return chapps_mock_cfg_path

@fixture(scope='session')
def run_services():
    """Force services to run because that is the point"""
    return True

@fixture(scope='session')
def known_sender():
    return standard_sender()

@fixture(scope='session')
def mail_sink(request, run_services, watcher_getter):
    """Set up a mail sink, so that once Postfix forwards email, it will be destroyed"""
    if run_services:
        mail_sink_watcher = watcher_getter( './services/mail-sink.py',
                                            checker=lambda: os.path.exists('/tmp/mail-sink.pid'),
                                            request=request,)
        return mail_sink_watcher
