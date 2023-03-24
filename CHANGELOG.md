# Change Log

## Beta Releases

### v0.5.15:

- Adding same debug information to
  `CascadingMultiresultPolicyHandler`, which is the one of interest to
  the strange interaction with Postfix under high load, and possibly
  with high DNS-resolution latency.

### v0.5.14:

- Adding debug information regarding obtained contents of incomplete
  reads from Postfix.  We are experiencing a strange situation wherein
  CHAPPS reports over and over again that Postfix is closing its
  connection before CHAPPS can read the end-record character sent at
  the end of Postfix policy requests.  This seems to somehow be
  related to periods of congestion occurring around the same time
  Postfix complains of not being able to reach CHAPPS, resulting in
  many emails being bounced.  And, in this mix, we see sometimes the
  `pyspf` library raising timeout errors while trying to resolve
  records for SPF checks.

  All of this seems to coincide with periods of greater overall load,
  and as there are other moving parts to how it all works, more
  observability is required in order to better understand where the
  breakdown is occurring.

  The altered message is issued at 'DEBUG' level, so if your logging
  level is not set to catch debug messages, they may not appear or may
  appear only in the debug log, depending upon your **syslog**
  configuration.

- Corrected format of `CHANGELOG.md` to get markup to render.
  Adjusted formatting and spacing as well.  This should probably have
  been an RST file from the beginning.

### v0.5.13:

- Adding an option for `SPFEnforcementPolicy` which allows the
  operator of a site to set the total-duration timeout for DNS
  checks against a single message.  Sometimes these can add up,
  and the RFC(s) on the subject call for allowing 20s to perform
  DNS lookups.  Sites which would rather limit their SPF-related
  DNS overhead may set this to a lower value.  Checks which time
  out are considered to have failed.

- Adjusted setuptools metadata a bit.  Added an `[all]` extras
  category to simplify the process of installing all the
  dependencies.  Right now API testing fails after a fresh `pip
  install -e` due to a missing file, which would appear if the
  module were installed normally.  I am not sure how to correct
  this problem; locally I just use a symlink.

- Added helpful comments to some of the integration tests.  Most
  of the individual files making up those tests, even if they are
  in the same directory, cannot actually run in the same session.
  They pass when run in separate sessions.

### v0.5.12:

- Correcting serious error-handling bug which would cause an
  endless, log-filling loop when encountering unexpected
  connection errors.  All users are recommended to update their
  software immediately.  This one was a bit sneaky for us; we've
  run this software in an intense production environment for
  months before finding this defect.

### v0.5.11:

- Correcting/completing `domain flush` functionality in `chapps-cli`

- Ensuring that SDA `allow`/`deny` functionality causes the relevant
  cache entry to be deleted in order to ensure it is repopulated when
  next accessed.

- Adjusting production syslog message format to preface it with
  the processName and PID as with the postfix logs.

### v0.5.10:

- Correcting a couple of bugs in the CLI script, wherein:
  - trying to show a nonexistent domain would cause an un-trapped
    error
  - trying to show a domain's option flags caused an un-trapped
    error if the SPF libraries are not installed

- Adding HELO whitelisting option to global CHAPPS config.  Right
  now, it is only implemented for inbound policies.  It would not
  be hard to add to outbound ones as well.  In such a case, one
  might want distinct lists.

### v0.5.9:

- Update the .readthedocs.yaml config file which I had completely
  forgotten about.  This file contains among other things the
  command line for `sphinx-apidoc`, and so it is the proper place
  for the exclusion pattern in order to ensure that builds on
  readthedocs.io function.

### v0.5.8:

- Implement exclusion pattern in Makefile to cause sphinx-apidoc
  to skip Alembic subhierarchy, because part of it throws an error
  when loaded during the doc-build and there seems to be no reason
  to embed its docs in these.

- Update CHAPPS modules list in its main `__init__.py` to reflect
  recent architectural changes.

### v0.5.7:

- Ongoing efforts to get the documentation to compile
  automatically at readthedocs.io.  Another debug log instance at
  module scope needed protection.  I think this is the last one
  based on some bogussy codebase searches.

- Corrected some old documentation which referred to an obsolete
  module called `actions` which became disused several revisions
  back.

- Removed `actions` module source file from repo, as it was no
  longer used and its old, deprecated code was breaking
  documentation auto-building.

### v0.5.6:

- Correct issues with handling unrecognized domains when checking
  inbound policy option settings.

- Protect config-module debug-logging with conditionals to prevent
  running during a doc-build in order to get readthedocs.io
  autobuild to function properly.

- Advance the metadata Development Stage identifier to Beta.  We
  continue to use the software in a production environment.  Feel
  free to reach out and let us know about your own deployment so
  we can collect more data about how it is functioning for others.

### v0.5.5:

- Now using SQLA-based adapters throughout.

- The environment variable `CHAPPS_DB_MODULE` may be set to `mysql`
  in order to cause the policy layer to use the older, previous
  adapter module based on `mysqlclient`.

### v0.5.4:

- Correcting major oversight -- until this release, the live API
  lacked a route to clear the SPF option flag for domains.  This
  is really necessary in order for updates to options to take
  effect immediately.  SPF software requirements are now also
  added to the API software requirements.

### v0.5.3:

- All major features of the software have now been in use in a
  large-scale production email context for a week or more.  The
  outbound features have been in production for a few months.  The
  software can no longer be considered to be in an "alpha" stage
  of development.

- Some improvements are made in this release to requirements of
  CREATE and UPDATE operations.  Variously, attributes of models
  have been made optional, and some routines which automate the
  database interactions have been modified to allow for certain
  attributes to be missing (defaulted or left alone) from either
  CREATE or UPDATE operations.  For instance, the greylisting and
  SPF flag attributes on Domain objects are optional during
  creation and will both default to False.  For updates on Domain
  or Quota objects, only the attribute(s) being adjusted need be
  included, apart from the ID.

  As promised in the notes for v0.5.2, this release provides a
  mechanism for providing arbitrary defaults for model attributes,
  in order to allow some settings to be defaulted during CREATE
  operations.  By default, there are no defaults.  When an
  attribute has no default, `Ellipsis` is used in order to signal
  via FastAPI/Starlette `Field` objects that the attribute is
  required.  Otherwise, the default value is provided when the
  closure is constructed by the `create_item` factory.

  It is perhaps worth noting that the solution to the problem of
  updates initially requiring all attributes to be included is not
  entirely satisfactory, as it consists mainly of making all but
  the `id` attribute optional on the Pydantic data model.  In
  practice this seems to work "okay" as the database refuses to
  create objects without fields which don't have defaults, like
  `name`.  However, due to some as-yet-unsolved intricacy of
  FastAPI and/or Starlette, the API simply locks up and eventually
  times out when it receives a request with malformed data -- such
  as a request to CREATE an entity with no `name` field.  It would
  of course be preferrable to send a code 400 with a reasonable
  explanation.  However, something earlier is hanging up, so that
  it seems the route closure itself never gets to execute.

- API documentation has been adjusted to reflect changes since the
  last time API documentation was updated, including the above.

## Alpha Releases

### v0.5.2:

- Adding in hardcoded "False" defaults for boolean values on
  models during record creation.  This is specifically in order to
  provide backward compatibility during upgrade of CHAPPS from
  versions v0.4.11-17 wherein there were no domain flags.  Now
  that there are flags on domains, the old domain-creation code on
  clients will break utterly if the API cannot provide defaults,
  which in v0.5.1 it was not doing.  Now, defaults of False are provided
  if the specified parameter type is Optional[bool] or any
  Union[bool|...].  This is a stopgap, which provides a hint as to
  how a wider change would allow for arbitrary defaults to be
  provided for any specified parameter.

  **TL;DR** There is a hacky kludge which fixes a
  reverse-compatibility issue which will be improved into a
  flexible way to provide defaults for any specified parameter to
  the `create_item` and probably also `update_item` factory
  functions.

### v0.5.1:

- The recent (major) adjustment to how the config object works was not
  reflected in the CLI script, and so in the last two revisions it was
  broken (since v0.4.17).  It is repaired in this release.

- Similarly broken were all of the outbound policy service
  scripts, and the standalone greylisting service script.  These
  have also been corrected now.

### v0.5.0:

- The v0.5.x version milestone represents the completion of the first
  major iteration of feature development for CHAPPS.  It can now limit
  outbound transmissions based on quota and authorization, and it can
  apply greylisting and SPF enforcement to inbound email.

- SPF headers are now prepended to all email flowing through an inbound
  policy service which includes the SPF handler.  This is to increase
  co-operation with downstream tools such as DMARC enforcement and spam
  filtering tools.

- An annotated version of the default CHAPPS configuration file
  has been included in the install directory, in order to serve as
  a form of documentation about config options.

- Consolidated how Redis handles are created for testing

### v0.4.17:

- Fix bug in Greylisting-via-SPF which caused errors when
  softfailing emails passed greylisting.

- Add some tests to ensure that the code referenced above is
  exercised properly to expose regressions.

- Add new "mail sink" for integration tests, which in fact does not
  sink the email but instead reflects it back to the test via a UDS,
  enabling integration tests to inspect the contents of the emails
  they send.

- Add inbound-flags-adapter code to SQLA adapters.

- Add tests for all inbound-flags-adapter classes.

- Sort out conflicts between SQLA tests; all can once again run at once.

- Refactor configuration stategy to avoid package-global config object.

### v0.4.16:

- Added basic admin functions in CLI: initialize/update database schema,
  change API config-flush password, perform config-flush (with option to
  write to an alternate location).

- Added Greylisting & SPF enforcement management commands in CLI.

- Added Greylisting & SPF enforcement management routes to API,
  including routes to set a domain's enforcement preference, and
  others to clear a domain's enforcement option cache in Redis.

### v0.4.15:

- added chapps.alembic.versions subpackage, because of course Alembic
  cannot work without the version files

### v0.4.14:

- added missing package data which prevented Alembic migrations
  from functioning as expected

### v0.4.13:

- Refactored elements of the adapter classes to reduce code duplication.

- Added Alembic to project to manage database migrations.

- Created as-of-0.4.12 base migration, and an update migration to
  add new option flag columns.

- Added greylisting and SPF-checking option flags to **Domain** records.

- Updated greylisting and SPF policy tests to accommodate new flags.

- Created new inbound handler class hierarchy, encompassing SPF
  and inbound multipolicy handler.

- Created new multipolicy inbound service which combines SPF and
  Greylisting in one service.

- NB: pre-existing databases need special care during upgrade, see
  [README](README.md#db-initialization)

### v0.4.12:

- Adding missing documentation to new bulk user-domain and
  user-email auth policy routes.

- Completed overhaul of database adapter layer.  There is now an
  adapter layer based entirely on SQLAlchemy rather than the
  low-level driver.  This is not currently used but it passes
  tests.  Some comparative performance analysis seems indicated
  before adoption.  Also its tests break the API tests for some reason.

- Relocating join-assoc instance definitions to models.py: the API
  extras are no longer required in order for the CLI to run.

- Refactored instance-caching code (based on Postfix instance ID)
  into the policy parent class in order to reduce code duplication.

### v0.4.11:

- Adding bulk policy access for user-domains and user-emails along
  the same lines as the bulk quota policy query.  Lists of
  **Domain** or **Email** ids are returned, tagged with the name
  of the user.  Keys: `user_name`, `domain_ids` or `email_ids`

- Edge condition testing is performed only once because all three
  of these routines are based on the same factory which is already
  being tested.

- CLI file location changed w/i the repo, called `chapps-cli`,
  made executable, added `version` command to detect current
  CHAPPS version.

- HTTPExceptions were accidentally being trapped by the DB
  interaction wrappers; this has been resolved so that 409s are
  returned properly in such cases.

### v0.4.10:

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

### v0.4.9:

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

### v0.4.8:

- Urgent fixes release: some PPR field values may contain `=`
  which will cause parsing to fail spectacularly.  A fix is
  included in this version.

- A missing software dependency which impeded operation of the
  previous version has also been added (`email-validator`).

### v0.4.7:

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

### v0.4.6:

- Correcting dependency misalignments in setup.cfg which were preventing
  CHAPPS from launching after installation from PyPI

- Massive documentation update, using rST and Sphinx

- Some minor code cleanup, mainly removing completely extraneous code

- logic added to `VenvDetector` to detect when the library is launched
  by Sphinx; depends on code added to `docs/source/conf.py`

- CHAPPS now defaults looking for its config in its venv by default if
  one is being used. (`<venv>/etc/chapps.ini`)

- CHAPPS does not attempt to write a config file when invoked by Sphinx

### v0.4.5:

- Corrected missing statements which caused new email tables not to be
  created by `chapps_database_init.py`

- added more acknowledgements to INSTALLATION

- added whole-email matching related docs to README.md

### v0.4.4:

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

### v0.4.3:

- Correct error preventing automatic table building by provided
  setup script.

- Provide better documentation about setting up the database.

- Minor adjustments to API README

### v0.4.2:

- Paginate associated objects
  (paginate domains for users, and users for domains)

- Adjusting location of API README to correct bug preventing API launch

- Adding VenvDetector util class, to help find API README after installation

- Adding CHANGELOG to PyPI package

- Add a little extra documentation about **syslog** message configuration

### v0.4.1:

- Improved Swagger/OpenAPI documentation.  Handling assignment of
  path closure docstrings explicitly fixes the problem.  Various
  formatting improvements have also been included.

### v0.4:

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

### v0.3.13

- fixing a problem with logging, wherein library logs were suppressed

- generally tidying logging

- updated documentation to discuss logging

- refined installation instructions

### v0.3.12

- making OQP throttling disabled by default; it needs some work

- adding log handler to send messages to the mail log

### v0.3.11

- modifying logic around user-key extraction, and adding new
  settings: require_user_key (boolean), and no_user_key_response
  (Postfix response string).  See README for more information.

- adding some logic to guard against IndexError conditions when
  calculating time-delta from the attempts list

### v0.3.10

- adding default config value for `min_delta` to
  OutboundQuotaPolicy, which defaults to 5.  It represents the
  minimum number of seconds between attempts; faster attempts will
  be refused (but reset the timer).

- correcting problem with recipient-counting wherein the
  recipients memoizing routine ran afoul of __getattr__()

- correcting problem with recognizing at signs in email addresses

### v0.3.9:

- correcting import of test library feature into main codebase

- adding more comprehensive CHAPPSException handling

### v0.3.8:

- correcting packaging error which prevented installation of
  dependencies

### v0.3.7:

- removing static SystemD service profiles from pip package; they
  remain in the repo, for use via git clone.

- correcting fatal bug wherein receiving email with a null sender
  would cause the application to crash.  It is now possible to
  specify for each policy whether null senders are "ok"; the
  default is False.

### v0.3.6:

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

### v0.3.3-5:

- improvements to setuptools install process (pip / setup.py)
  which should make it possible to format correct SystemD service
  description files to run the installed CHAPPS services, even
  from within their venv

### v0.3.2:

- putting extra artifacts in a chapps dir, w/i venv or /usr/local
  depending on whether a venv is used

### v0.3.1:

- Updating documentation

### v0.3:

- Sender-domain authorization policy allows an RDBMS to indicate
  which domains a particular user is authorized to emit mail on
  behalf of.

- There are more updates to the config file.

- There are additions to the database schema which should be
  compatible with v0.2

### v0.2.1:

- Now supports connecting to Redis via Sentinel; provide a
  space-separated list of host:port info for `sentinel_servers` in
  the config, and specify the name of the dataset in
  `sentinel_dataset`

- Some minor changes to the config file have occured; the
  `sentinel_master` param and the `db` param have been removed

### v0.2:

- PLEASE NOTE: the database schema has changed with this update

- DB access encapsulation and outbound-traffic user identification
  is now independent of any policy or handler

- some symbol names have been updated for greater clarity

- the documentation has been improved somewhat; more to come

### v0.1:

- Outbound Quota and Greylisting policies function, but their
  feature sets may be incomplete.

- Installation procedure just a bit wonky.
