"""CHAPPS REST API implementation

Originally, I had hoped to isolate all the API-related stuff
in this package, but as I should have known, references to the
data models crept back into the main codebase even before
the API was finished.

The :mod:`~.api` module serves to supply some top-level documentation strings related
to the groups of API routes, and to include all the various API routers into the
final :class:`~fastapi.FastAPI` object.

.. todo::

  some of the 'API' code, mainly the data models and database access logic,
  needs to migrate into the main package.  Since access to the database is
  already isolated into the adapter classes, this should not be too tough to
  do.

"""
__all__ = ["api", "routers"]
