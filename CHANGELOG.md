# Change Log

## Alpha Releases

###v0.4.10:
	- Correcting some internal server errors raised under certain
      circumstances by the new API routines for bulk Quota queries.
      This fix may also address some other situations which were less
      pressing.
	- Added a synchronous (regular callable) DB interaction decorator
	  in order to standardize the handling of DB exceptions and of
	  HTTPException raising when the result set is empty.  This was part
	  of fixing the problems with the bulk routines.
	- Added a factory for creating object listers which accept ID
      lists and ensure that arbitrary associations are loaded on the
      returned models.

###v0.4.9:
	- The beginnings of a CLI, in order to allow direct, command-line
	  level control of permissions, creating **Email** and **Domain**
	  records, quota assignment, file-based permissions and quota
	  import, real-time quota checking, reset and refresh, and
	  descriptive help messages.
	- Adding new dependency on `typer` for the CLI, with extended
      dependencies for `typer`: `colorama` and `shellingham`
	- Adding bulk query operations for **Quota** records and status.
	  As separate routes, **User** ids may be supplied to:
		  - receive a list mapping **User** name to **Quota** id
		    (policy setting -- from the User section)
	      - available quota (real-time availability based
		    on cached policy, from the Live section)
	  The live route also generates some human-oriented remarks about unusual
	  situations encountered while running.

###v0.4.8:
    - Urgent fixes release: some PPR field values may contain `=`
	  which will cause parsing to fail spectacularly.  A fix is
	  included in this version.
	- A missing software dependency which impeded operation of the
      previous version has also been added (`email-validator`).

###v0.4.7:
	- Fixed uncaught error on nonexistent user-identifier when the
      user-key is required.  The application now sends the expected
      auth-failure rejection action to Postfix.
	- Fixed a handful of xfailing tests; the remaining one covers the
      experimental, non-working rate-limitation subfeature of outbound
      quota.
	- Trapping AttributeError in CHAPPSMetaModel and raising our own,
      more sensical one.
	- Simplified the coroutine factory in
      chapps.rest.routers.common.list_associated() -- the prototype
      coroutine's signature is actually invariate so there was no
      reason to build it dynamically.
	- There is now content validation for Domain and Email records.
	- The data models and database-session related modules created for
      the API have been relocated into the core of the project.
	- The adapter has been modified to use mysqlclient instead of
      mariadb (Python packages).
    - A new, SQLAlchemy-powered adapter layer has been included but as
	  yet tests are not complete, and so there is no way to actually
	  use it currently.

###v0.4.6:
	- Correcting dependency misalignments in setup.cfg which were preventing
      CHAPPS from launching after installation from PyPI
    - Massive documentation update, using rST and Sphinx
	- Some minor code cleanup, mainly removing completely extraneous code
	- logic added to `VenvDetector` to detect when the library is launched
	  by Sphinx; depends on code added to `docs/source/conf.py`
	- CHAPPS now defaults looking for its config in its venv by default if
	  one is being used. (`<venv>/etc/chapps.ini`)
	- CHAPPS does not attempt to write a config file when invoked by Sphinx

###v0.4.5:
    - Corrected missing statements which caused new email tables not to be
	  created by `chapps_database_init.py`
	- added more acknowledgements to INSTALLATION
	- added whole-email matching related docs to README.md

###v0.4.4:
    - Corrected incorrect homepage URL in setup.py
    - Polish documentation.
    - Added full-email auth to SDA module.
    - Added full-email auth object CRUD routes to API.
    - Changes to signature of route path for association-list management:
	  routes are now named for the association and use GET/PUT/DELETE
    - Add full-email checking cache maintenance routines to Live API
    - Live routes for bulk peeking and clearing of Redis cache now
      accept lists of both domain IDs and email IDs, and if both are
      provided, will provide all the output combined in a single dict.

###v0.4.3:
    - Correct error preventing automatic table building by provided
      setup script.
    - Provide better documentation about setting up the database.
    - Minor adjustments to API README

###v0.4.2:
	- Paginate associated objects
	  (paginate domains for users, and users for domains)
	- Adjusting location of API README to correct bug preventing API launch
	- Adding VenvDetector util class, to help find API README after installation
	- Adding CHANGELOG to PyPI package
	- Add a little extra documentation about **syslog** message configuration

###v0.4.1:
	- Improved Swagger/OpenAPI documentation.  Handling assignment of
	  path closure docstrings explicitly fixes the problem.  Various
	  formatting improvements have also been included.

###v0.4:
	- introducing the first version of the REST API; INSTALLATION
	  instructions will be modified to discuss and provide references
	  for proper, highly-available deployment of the REST API, which
	  it is advised be run on separate servers.
	- The API is powered by [FastAPI](https://fastapi.tiangolo.com/);
	  detailed instructions regarding API deployment may be found in
	  its documentation, including how to use a reverse proxy such as
	  **nginx** to provide SSL.
	- Database access for the API is performed using
	  [SQLAlchemy](https://www.sqlalchemy.org/), and in future
	  releases, all database accesses will be converted to using it,
	  for the sake of consistency and to eliminate the needless
	  dependency on the MariaDB client software.
	- PyPI package now provides the `[API]` extras definition, to
      install API prerequisites (which are not otherwise needed)
	- CHANGELOG adapted to be Markdown-compatible

###v0.3.13
	- fixing a problem with logging, wherein library logs were suppressed
	- generally tidying logging
	- updated documentation to discuss logging
	- refined installation instructions

###v0.3.12
	- making OQP throttling disabled by default; it needs some work
	- adding log handler to send messages to the mail log

###v0.3.11
	- modifying logic around user-key extraction, and adding new
	  settings: require_user_key (boolean), and no_user_key_response
	  (Postfix response string).  See README for more information.
	- adding some logic to guard against IndexError conditions when
	  calculating time-delta from the attempts list

###v0.3.10
	- adding default config value for `min_delta` to
	  OutboundQuotaPolicy, which defaults to 5.  It represents the
	  minimum number of seconds between attempts; faster attempts will
	  be refused (but reset the timer).
	- correcting problem with recipient-counting wherein the
      recipients memoizing routine ran afoul of __getattr__()
	- correcting problem with recognizing at signs in email addresses

###v0.3.9:
	- correcting import of test library feature into main codebase
	- adding more comprehensive CHAPPSException handling

###v0.3.8:
	- correcting packaging error which prevented installation of
      dependencies

###v0.3.7:
	- removing static SystemD service profiles from pip package; they
      remain in the repo, for use via git clone.
	- correcting fatal bug wherein receiving email with a null sender
	  would cause the application to crash.  It is now possible to
	  specify for each policy whether null senders are "ok"; the
	  default is False.

###v0.3.6:
	- bug fixes: due to poor design choice, all policies in a
	  multipolicy handler will end up with the same config, that being
	  the config for the last configured policy.  As such, earlier
	  ones would send the wrong messages, and possibly exhibit other
	  problematic issues.  This is fixed.
	- OQP default acceptance response changed from OK to DUNNO
	- ConfigParser instructed not to perform interpolation on INI
	  file, in order to allow all arbitrary garbage (for passwords)
	- handlers now provide property methods to obtain the appropriate
      listener address and port numbers

###v0.3.3-5:
	- improvements to setuptools install process (pip / setup.py)
	  which should make it possible to format correct SystemD service
	  description files to run the installed CHAPPS services, even
	  from within their venv

###v0.3.2:
	- putting extra artifacts in a chapps dir, w/i venv or /usr/local
      depending on whether a venv is used

###v0.3.1:
	- Updating documentation

###v0.3:
	- Sender-domain authorization policy allows an RDBMS to indicate
	  which domains a particular user is authorized to emit mail on
	  behalf of.
	- There are more updates to the config file.
	- There are additions to the database schema which should be
      compatible with v0.2

###v0.2.1:
	- Now supports connecting to Redis via Sentinel; provide a
	  space-separated list of host:port info for `sentinel_servers` in
	  the config, and specify the name of the dataset in
	  `sentinel_dataset`
	- Some minor changes to the config file have occured; the
	  `sentinel_master` param and the `db` param have been removed

###v0.2:
	- PLEASE NOTE: the database schema has changed with this update
	- DB access encapsulation and outbound-traffic user identification
      is now independent of any policy or handler
	- some symbol names have been updated for greater clarity
	- the documentation has been improved somewhat; more to come

###v0.1:
	- Outbound Quota and Greylisting policies function, but their
      feature sets may be incomplete.
	- Installation procedure just a bit wonky.
