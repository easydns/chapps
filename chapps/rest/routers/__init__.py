"""API route implementations

Each major category of route gets its own router.

Much of the actual code is contained in the :mod:`common` module,
which contains factories for building the routes related to object
manipulation.  The :mod:`live` module contains routes for interacting
with Redis, which represents the live state of CHAPPS.

"""
__all__ = ["common", "email", "users", "quotas", "domains", "live"]
