## Overview

The bulk of the documentation is generated automatically via FastAPI.

### Conventions

 The primary answer to a query is always returned in the element named
`response`.  So for example, when GETting a **User** object, that object
is the value of the `response` key, and there may be ancillary keys
named for its associations, which are `quota` and `domains`.

In general, a parameter named `q` indicates a string which will be
used in a basic substring match against the `name` attribute (column)
of the object.  The `skip` and `limit` parameters may be used to
paginate through what might otherwise be long lists of associations.
Since the objects are small in this case, the default is to skip none,
and to limit to 1000 rows returned.  In many cases this may mean that
the entire set of associated objects is returned: say, the list of
users for a domain which has a lot of mailboxes.

In the automatically-generated documents for the
automatically-generated CRUD routes, the generic variable `item_id` is
used to refer to the object ID of the main object concerned by the
route in question.  This seems fairly intuitive but seems worth
stating since it is not worth the effort to make the variable name
match the name of the model.  Maybe in a future revision.

In the examples, square brackets have been used to indicate portions
which may or may not occur; in general, **no brackets of any kind**
should actually be included in any names.


### Categories
API routes fall under a few different categories:
- user manipulation
- domain manipulation
- quota manipulation
- live interaction with CHAPPS Redis environment
- system commands like rewriting CHAPPS config file, etc. (lumped in
  with live for now)
