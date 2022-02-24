#!/usr/bin/env python
import redis
import time
import random
from pprint import pprint as ppr


default_user = "someguy@somewhere.com"
rolling_interval = 3600 * 24 # seconds
min_delta = 1

def ts_start():
    t = int(time.time()) - (3600 * 24)
    return [ t + r*random.randint(1,2000) for r in range(0, 99) ]

def policy_key(val="attempts", user=""):
    user = default_user if len(user) == 0 else user
    if val in [ 'attempts', 'limit' ]:
        return f"oqp:{user}:{val}"

def policy_fixture(redis_handle, user="", times=[]):
    with redis_handle.pipeline() as pipe:
        pipe.set(policy_key('limit', user), 100)
        pipe.zadd(policy_key('attempts', user), { k: k for k in times })
        pipe.execute()

def would_allow(redis_handle, user=""):
    pipe = redis_handle.pipeline()
    time_now = int(time.time())
    pipe.zremrangebyscore(policy_key('attempts', user), 0, time_now - rolling_interval)
    pipe.zadd(policy_key('attempts', user), {time_now: time_now})
    pipe.get(policy_key('limit'))
    pipe.zrange(policy_key('attempts', user), 0, -1)
    # pipe.expire(policy_key('attempts', user), rolling_interval)
    results = pipe.execute()
    removed, _, limit, attempts = results
    pipe.reset()
    ppr(results)
    print(f"Number removed: {removed}")
    print(f"Policy limit: {int(limit)}")
    print(f"There were {len(attempts)} in the last {rolling_interval} seconds.")
    # if QuotaPolicyEvaluator(limit, attempts).would_allow():
    #     print("This email would be allowed.")
    # else:
    #     print("This email would not be allowed.")

### after making a decision, if an email is allowed to be sent, the sent amount needs
### to be increased, and the "remaining" amount re-evaluated according to some heuristic rules
### right now I think that if it has been an hour or more since the last attempt, we can restore up
### to twice an hour's worth of "remaining" emails, or up to enough to

class QuotaPolicyEvaluator():
    def __init__(self, limit, attempts_list):
        self.limit = limit
        self.attempts = attempts_list

    def would_allow(self):
        if min_delta > 0 and int(self.attempts[-1]) - int(self.attempts[-2]) < min_delta:
            return False
        if len(self.attempts) >= int(self.limit):
            return False
        return True




rh = redis.Redis()
policy_fixture(rh)
would_allow(rh)
