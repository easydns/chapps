import os
import pytest
from pytest import fixture
from services.tests.conftest import test_message_factory

@fixture(scope='session')
def monkeypatch_session():
    from pytest import MonkeyPatch
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()

@fixture(scope='session')
def run_services():
    """Force services to run because that is the point"""
    return True

@fixture(scope='session')
def null_filter_service( request, run_services,
        chapps_mock_session,
        chapps_mock_config_file,
        populated_database_fixture,
        watcher_getter):
    """
    The fixtures requested above establish the mock-config, which points at the
        test database, and also populates that database.
    pytest-services watcher_getter is used to launch CHAPPS with the environment
        monkey-patched so that the mock-config will be loaded.
    """
    if run_services:
        null_filter_watcher = watcher_getter( "./null_filter.py",
                           checker=lambda: os.path.exists('/tmp/null_filter.pid'),
                           request=request,
        )
        return null_filter_watcher

@fixture(scope='session')
def nlf_test_recipients():
    return [
        'ccullen@easydns.com'
    ]

@fixture(scope='session')
def known_sender():
    return 'ccullen@easydns.com'

@fixture(scope='session')
def nlf_test_message_factory():
    return test_message_factory( "CHAPPS-NLF", "CHAPPS automated null-content-filter service testing" )

# @fixture(scope='session')
# def mail_sink(request, run_services, watcher_getter,):
#     if run_services:
#         mail_sink_watcher = watcher_getter( "./mail-sink.py",
#                                             checker=lambda: os.path.exists('/tmp/mail-sink.pid'),
#                                             request=request,)
#         return mail_sink_watcher

# @fixture(scope='session')
# def sunk_postfix(run_services, watcher_getter,): # add mail_sink to sink test emails
#     pidfile = '/var/spool/postfix/pid/master.pid'
#     def sink_postfix(request, postfix_argv):
#         if run_services:
#             postfix_watcher = watcher_getter( postfix_argv,
#                                               checker=lambda: os.path.exists(pidfile) and os.path.size(pidfile) > 0,
#                                               request=request)
#             return postfix_watcher
#     return sink_postfix

# @fixture(scope='session')
# def postfix_for_nlf(request, sunk_postfix):
#     postfix_argv = "/usr/sbin/postfix -c postfix/null-filter"
#     return sunk_postfix( request, postfix_argv )
