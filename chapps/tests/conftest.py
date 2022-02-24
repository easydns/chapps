"""Root conftest for CHAPPS"""
import pytest
import redis
import time
from pytest import fixture
from chapps.policy import GreylistingPolicy

seconds_per_day = 3600 * 24

class ErrorAfter(object):
    """Return a callable object which will raise CallableExhausted after a set number of calls"""
    def __init__(self, limit):
        self.limit = limit
        self.calls = 0

    def __call__(self, *args, **kwargs):
        if self.calls > self.limit:
            raise CallableExhausted
        self.calls += 1

class CallableExhausted(Exception):
    """Custom exception mainly for escaping infinite loops"""
    pass

def _unique_instance(deadbeef='deadbeef'):
    counter = 0
    def _fmt_inst( ctr, deadbeef=deadbeef ):
        return f"a469.{deadbeef}.{ctr:05d}.0"

    def _uniq_inst(count=1):
        nonlocal counter
        if count == 1:
            result = _fmt_inst( counter )
            counter += 1
        else:
            result = [ _fmt_inst( counter + i ) for i in range(0,count) ]
            counter += count
        return result
    return _uniq_inst

def _mock_client_tally(unique_instance):
    def _mct( ct ):
        t = int( time.time() ) - seconds_per_day
        tally = dict( zip(
            unique_instance( ct ),
            [ float( t + 60 + i*300 ) for i in range(0, ct ) ] ))
        return tally
    return _mct

def _clear_redis(prefix):
    def __cr():
        rh = redis.Redis()
        keys = rh.keys( f"{prefix}:*" )
        if len( keys ) > 0:
            rh.delete( *keys )
    __cr()
    return __cr

def _redis_args_grl(src_ip, sender, recipient, tally_count=0):
    tally = {}
    if tally_count > 0:
        mock_client_tally = _mock_client_tally(_unique_instance()) # this is weird, I know; fixtures get weird
        tally = { GreylistingPolicy._fmtkey( src_ip ): mock_client_tally( tally_count ) }
    return ( GreylistingPolicy._fmtkey( src_ip, sender, recipient ), tally )

def _populate_redis_grl( tuple_key, entries={} ):
    if len(tuple_key) < 7:
        raise ValueError("Tuple key is too short to be legal.")
    rh = redis.Redis()
    with rh.pipeline() as pipe:
        pipe.set( tuple_key, time.time() - 305 ) # seen 5 min ago
        if len( entries ) > 0:
            for k, v in entries.items():
                pipe.zadd( k, v )
        pipe.execute()
