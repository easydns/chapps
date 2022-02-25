# CHAPPS

## the Caching, Highly-Available Postfix Policy Service

### requires Python 3.8.10+
### makes use of Redis, (eventually Sentinel) and a relational database (MariaDB)

## Introduction

There is a need for a highly-available, high-performance, concurrent, clusterable solution for handling various
aspects of email policy.  Postfix farms out the job of policy decisions to a delegate over a socket, so we can
provide a framework for receiving that data, making a decision about it, and then sending a response back to Postfix.
There are some projects which have provided smaller-scale solutions to this issue.  We handle rather a large volume
of email, so we need something more performant than a script which makes a database access on every email.

My decision was to use Redis, since with Redis Sentinel it should be possible to achieve a degree of high-availability
using Redis as a common datastore between the various email servers in the farm(s) which will run local instances of
the policy server, which will itself use Redis to cache data and keep track of email quotas, etc.

In the first iteration, we propose to provide functionality for:
 - outbound quota tracking on a continuous, rolling, per-interval basis;
 - outbound sender domain authorization
 - inbound email greylisting;
 - inbound SPF checking

The framework is meant to be extensible, so that any conceivable email policy might be implemented in the future.

## Configuration

The library will create a config file for itself if does not find one at its default config path,
`/etc/chapps/chapps.ini`, or the value of
the environment variable `CHAPPS_CONFIG` if it is set.  Note that default settings for all available submodules
will be produced.  At the time of writing, each script runs its own type of policy handler, so only the settings
for that policy will be needed, plus the general CHAPPS settings and the Redis settings.  Policies have separate
listening addresses and ports, so that they may run simultaneously on the same server.

(The global CHAPPS listener config will be used in the future to provide an API for other components to query
CHAPPS on the status of quotas, etc.)

Example Postfix configs are included in the `postfix` directory, classified by which service they are for.  Most
access control policy services will be implemented in a very similar way in `main.cf`, probably in combination
with other policies.  The examples provided are the same configs used for testing, and are necessarily stripped
down to focus just on that particular service.

## Installation

Please ensure that MariaDB Connector/C is installed before attempting installation of this package.  The
Debian packages recommended are:
  - `mariadb-client`
  - `libmariadb-dev-compat`
  - `redis`
  - `python3-pip`
The package contains a dependency on the `mariadb` package; it will not install properly without Connector/C
installed, which is not a Python package.  (Perhaps this dependency should be left out.)

The package may be installed via PyPI, using the following command:

```
python3 -m pip install chapps
```
In such a case, the SystemD service files are installed to a folder called `install` inside the venv directory,
and Postfix example/testing configs are located in the `postfix` folder.  Scripts and package go to `bin`
and `lib/.../chapps` as expected.  Use of a venv is recommended, though it may mean some changes are needed to
the service files as provided.

Installation artifacts are available
in the `install` directory, including a shell script to copy things to their places, and the SystemD service
files for starting the outbound quota and greylisting services.  See the [INSTALLATION](INSTALLATION.md) file.
Install scripts were developed in our environment for test-deployment purposes and may be abandoned once the
package is available via PyPI.

There is also a Python script in the install directory, the purpose of which is to create the database schema
required by the library.  It does not create the database itself.  Before running this script, ensure that the
CHAPPS configuration file contains the correct credentials and other control data to be able to connect to the
database server, and also ensure that the database named in that config has been created on the server.  The
script will connect to the database and create the tables.  It uses `IF EXISTS` and does not contain any kind
of data deletion, so it should be safe to use at any time.

### Redis configuration

Redis is used to store the real-time state of every active user's outbound quota, sender-domain authorization
status cache, and also to keep track of greylisting status for greylisted emails.  An active user is one who
has sent email in the last _interval_, that interval defaulting to a day, since most quotas are expressed as
messages-per-day.

If your Redis deployment is on a different server and/or if CHAPPS is sharing a Redis instance with some
other services it may be necessary to adjust the Redis-related settings in the config file, to adjust the
address and/or port to connect to, or what database to use.  By default, CHAPPS tries to connect to Redis
on localhost, using the standard port assignment and db 0.

If Sentinel is in use, populate the Sentinel-oriented configuration elements `sentinel_servers` and
`sentinel_dataset`.  The servers list should be a space-separated list of each Sentinel server half-socket;
for example, "10.1.9.10:26379 10.1.9.12:26379".  The dataset name is the one you specified to Sentinel
when setting up the Sentinel cluster.  Sentinel's default dataset name is `mymaster`.  We, of course,
recommend `chapps`, or perhaps `chapps-outbound` at a site with a large volume of email.
Since SPF doesn't make much use of Redis, the inbound load may be lighter than the outbound load, depending
on which things happen more at a particular site.

## Outbound Services

Policy services can be divided into those which work on outbound mail, and those which work on inbound mail.
Some, possibly, might be applied to either flow, but none such are part of this project yet.  Outbound items
share some characteristics.

Outbound mail, for our purposes, is assumed to originate with an authenticated user.  That user may authenticate
with Postfix using a username/password or a client-side SSL cert, in which case the username or subject name
(of the cert) will be passed along by Postfix to the policy service.

In order to allow sites to specify exactly what field of the Postfix policy data they would like to use to
identify users, the configuration allows the user to specify the first field to check.

#### Setting the user key

Postfix submits a fairly large packet of data on each policy delegation request.  One prominent element of this
data is the MAIL FROM address, which is labelled as `sender`.  This is perhaps the obvious element to use to
count quotas, but some other fields are more interesting.

Current versions of the software allow the config file to specify what element of that delegation request payload
to use, defaulting to `sasl_username`.  This is because our customers use a password auth process, so the
`sasl_username`
directly corresponds to the entity which is paying for the email quota.  For a similar reason, `ccert_subject` is
used as a backup, after `sasl_username`.  If neither is populated, `sender` and `client_address` are checked in
that order.  The `client_address` is an extreme fallback because it will always have a value, while `sender`
may under some circumstances be empty.

At present, there is little sanitation on this field.  It is never evaluated as code, but it is used directly
as the attribute name for the value dereference.  If that yields no value, or if it is not specified, CHAPPS
looks for `sasl_username` first, then `ccert_subject`, and if there is none, it falls back to `sender`,
which can also be blank. In
that extreme case, CHAPPS uses `client_address`.  This will not work very well long-term if a lot of real senders
share a mail gateway, so it is recommended to make sure that the field specified is being populated.

Incidentally, this may be a reason for permitting senders which don't appear in the user-list, since
system-generated messages which don't have a sender listed will end up quota'd on their client address,
and probably most of them will be denied by quota, potentially generating a large number of confusing
secondary error messages.
CHAPPS currently expects any permitted sender to appear in the `users` table.  Note that the name
which appears in this table needs to match what will be discovered in the specified key field.  For sites
which use the user's email address as their login name for email access, this is easy.  For cert issuers,
it may simplify things to use the email address as the subject of the cert, but any unique string will work.

## Outbound Quota Policy Service

The service is designed to run locally side-by-side with the Postfix server, and connect to a Redis instance,
possibly via Sentinel.  As such it listens on 127.0.0.1, and on port 10225 by default, though both may be adjusted
in the config file.  It obtains quota policy data on a per-sender basis, from a relational database, and
caches that data in Redis for operational use.  Once a user's quota data has been stored, it will be cached for
a day, so that database accesses may be avoided.

Current quota usage is **not** kept in a relational database.

TODO: There is a plan to provide both CLI (scripted) and API access to data about current quota usage,
and to provide facilities for updating quota policy information immediately:
clearing quotas, upgrading them, adding new users, adding new quotas, etc.

In order to set up Postfix for policy delegation, consult
[Postfix documentation](http://www.postfix.org/SMTPD_POLICY_README.html) to gain a complete understanding
of how policy delegation works.  In short, the `smtpd_recipient_restrictions` block should contain the setting
`check_policy_service inet:127.0.0.1:10225`.  In addition, it is necessary to ensure that the service itself,
the script `chapps_outbound_quota.py` is running.  This should be accomplished using `systemd` or similar;
scripts/file assets to assist with that are to be found in the install directory.
For now, according to current wisdom, Postfix's own `spawn` functionality from `master.cf` should be avoided.

### Outbound Quota Policy Configuration: Database Setup

At present, the service expects to obtain quota policy enforcement parameters from a relational database, in
particular, MariaDB.  The framework has been designed to make it easy to write adapters to any particular
backend datasource regarding quota information.

The database schema used has been kept as simple as possible:
```
CREATE TABLE `users` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `quotas` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(32) NOT NULL,
  `quota` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`),
  UNIQUE KEY `quota` (`quota`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `quota_user` (
  `quota_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  PRIMARY KEY (`user_id`)
  KEY `fk_quota` (`quota_id`),
  CONSTRAINT `fk_quota_user` FOREIGN KEY (`quota_id`) REFERENCES `quotas` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_user_quota` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```
The `users` table contains a record for each authorized user who is allowed to send email.  Users without
entries will not be able to send email, despite authenticating with Postfix.

The `quotas` table contains quota definitions, the `name` is meant to hold a user-readable tag for the
quota and max outbound email count (`quota`) of that quota.

The `quota_user` table joins the `users` table with the `quotas` table.
The `quota_user.user_id` column joins with `users.id` to map usernames onto IDs.  Usernames may be
email addresses, but they also may not.  How they are obtained is configurable as `user_key` -- the specified
field will be extracted from the policy request payload presented by Postfix.

Once the `quotas` table has been populated with the desired quota policies, the `quota_user` table may then
be populated to reflect each user's quota.

The application sets cached quota limit data to expire after 24 hours, so it will occasionally refresh quota
policy settings, in case they get changed.  In order to flush the quota information, all that is required is
to delete that user's policy tracking data from Redis.  TODO: A tool will be provided to do this.

**Please note:** Users with no `users` entry will not be able to send outbound email.

### Quota policy settings (non-database)

#### Counting all outbound messages against the quota

Some quota systems count any email as a single email regardless of the number of recipients included in the
envelope To: recipients list.  This software can operate that way, but it can also count an email for each
recipient in the list.  Whether it does so is governed by the boolean setting "counting_recipients": setting
this to True will cause CHAPPS OutboundQuotaPolicy to count a sent email for each recipient.

#### Outbound quota grace margins

There is a "margin" setting which will allow for some fuzziness over the established quota for multi-recipient
emails, allowing a user to go over their quota on a single (multi-recipient) email as long as the total number
of mails sent fits within the margin.  This obviously has no meaning if recipients aren't being counted, since
no email will ever represent more than a single outbound message.

Margins specified in **integers** are absolute message counts.

Those specified as **floats** represent a proportion of the total margin.  If a float value is less than 1 it
is assumed to be the ratio.  If it is larger than 1 and less than 100, it is assumed to be a percentage, and
it is divided by 100.0 and used as the ratio.

## Sender Domain Authorization (Outbound multi-policy service)

As of this writing, sender-domain authorization (SDA) is only available as part of the outbound multi-policy
service, consisting of SDA followed by outbound quota.
There is a plan (TODO:) to produce a standalone SDA service script.

The SDA policy allows an email service provider to specify exactly which domains may appear after the @ in the
sender address, the "sender" field in the Postfix policy delegation data packet.  User identification for
outbound emails is covered in a previous section of this document (see: 'Setting the user key').
The pool of users is all those entities
which authenticate with unique name/password pairs (via SASL); or the set of all `ccert_subject`s in the
case of client-side cert authentication.

It is generally possible to configure vanilla Postfix to limit outbound domains for users, but we encountered
some difficulty getting it to work reliably, and this method opens the door to a great deal of additional
nuance which would not otherwise be available to us.

CHAPPS expects to find SDA policy control data in its RDBMS (or other policy-config source), in a fairly
simple, normalized scheme.  This feature uses a new table to store source domains, and a new join table
to link users with domains they are allowed to use for outbound mail.

The service has room to grow, but should already be useful for real applications.  The domain matching is
intentionally inflexible -- the entire string after the @ sign must match a domain in the table.  That is
to say: in order to allow users to send from subdomains, those subdomains must have entries in the domains
table, and those entries must be linked to the logged-in (email-sending) user via the `domain_user` join
table.

Here is the schema, for reference:

```
CREATE TABLE `domains` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `name` varchar(64) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

 CREATE TABLE `domain_user` (
  `domain_id` bigint(20) NOT NULL,
  `user_id` bigint(20) NOT NULL,
  PRIMARY KEY (`domain_id`,`user_id`),
  KEY `fk_user_domain` (`user_id`),
  CONSTRAINT `fk_domain_user`
    FOREIGN KEY (`domain_id`) REFERENCES `domains` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_user_domain`
    FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

As with the quota policy, the logic used is inherently conservative.  If a user has no entry in the `users`
table, that user will not be able to send mail (even though they have authenticated).  If a user is trying
to send an email from an address (the `sender` address) which has a domain string (everything after the @ sign)
which does not appear in the `domains` table, or for which that user lacks a join record in `domain_user`, the
email will be denied.

In practice, this will mean that when a new email customer signs up, the domain(s) included in that service
agreement should be added to the `domains` table.  Any users which are authorized to send email appearing to
originate from that domain should be added to the `users` table, with join records linking their IDs to the
IDs of the domain(s) they can send for, in `domain_user`.

TODO: Currently, CHAPPS causes cached policy data to have an expiry timer of a day.  For outbound quota, this
makes a great deal of sense because the quotas are expressed in emails per day.  However, a day's worth of
authorized email senders' Redis cache keys may actually cause quite a bit of memory usage for no particular
reason.  Users don't send an evenly-spaced stream of email throughout the day; they send some emails, often
in clusters, separated by long pauses.  As such, the expiry time of SDA Redis caches should probably be a
tunable parameter, in order to allow operators to tune how much RAM on their Redis servers ends up devoted to
SDA caching.  6 or 8 hours seems like a reasonable trade-off between Redis-RAM bloat and RDBMS latency, but
different sites are different.

## Greylisting Policy Service

Greylisting is an [approach to spam prevention](https://en.wikipedia.org/wiki/Greylisting_(email))
based on the tendency of spammers to emit emails without using
gateways.  Spam is typically sent _to_ one or more gateways by malware programs which amount to viral MUAs,
able to connect to SMTP servers to send mail, but not capable of noting response codes and retrying deferred
deliveries.  Because a large proportion of spam is (or was) sent this way, the simple act of deferring emails
from unknown (untrusted) sources eliminates a large amount of spam.

If greylisting is being performed then
emails will be greylisted--that is, deferred--when they are associated with source tuples which are not
recognized.  Tracking data regarding recognized tuples is stored in Redis.  Config data regarding which
inbound domains request greylisting will be obtained from the database (feature TBD) and cached in Redis.

Please note that in the context of comprehensive inbound email filtering, SPF and greylisting have an
interesting relationship which is not entirely straightforward, and so a special combined, inbound
multi-policy service is planned, which will combine the features of greylisting and SPF checking in a
sane fashion, and provide a framework for adding further policies.

## SPF Policy Enforcement

The [Sender Policy Framework](https://en.wikipedia.org/wiki/Sender_Policy_Framework)
is a complicated and intricate beast, and so I will not try to describe it
in great detail, but instead link to relevant documentation about what SPF is.  Important to note
is the fact that SPF provides a framework for using DNS as the policy configuration source.

There is no provision in the RFC for the caching of SPF results in order to apply them to other
circumstances, such as another email with the same inputs.  It is possible that the policy itself,
i.e. the TXT record containing the SPF policy string, could change between emails.  As such, this
module does not use Redis.

There is a very widely-used and well-supported implementation of the SPF check itself in the Python
community called [pyspf](https://pypi.org/project/pyspf/), by Stuart Gathman and Terence Way.  CHAPPS
uses this library to get SPF check results.

The SPF policy enforcement framework included in CHAPPS makes it possible for an operator to specify
clearly and flexibly what they would like to have happen in response to any of the different SPF
check results.  The [SPF specification in RFC 7208](https://datatracker.ietf.org/doc/html/rfc7208)
does not address exactly what response to take in
each case, saying that it is a site's prerogative to decide the fates of those emails.

There is currently no local configuration of SPF.  As of this writing, there is no completed SPF service,
though there is a completed SPF enforcement handler, which needs only a script wrapper to become a service.
However, I am more interested in writing a multi-policy service for inbound email, because of the odd
interaction of greylisting with SPF.

## Inbound Multi-policy Service (SPF + Greylisting)

What does it mean to use both greylisting and SPF?  The trivial answer is to pass one filter, and then
pass the next filter.  But which comes first?

If one greylists first, a legitimate email may be deferred for ten minutes, then pass SPF checking;
should emails which pass SPF be subject to greylisting?  Conversely, a greylisted email may also come
from a server which is not allowed by its SPF record, and then be deferred only to be denied for an
unrelated reason after ten minutes of taking up disk space and using up cycles needlessly.

On the other hand, if one uses an SPF filter first, in a trivial fashion, then emails must pass muster
on the SPF check first, which seems right and proper to me, certainly.  And if greylisting is to be used
also, then it makes sense for emails which get `pass` from SPF to be deferred.  When they are sent again
they will of course incur another SPF check, and then they will pass greylisting, provided that the SPF
record they depend on has not changed in the meantime.

In the realm of SPF, there are a couple of grey areas, no pun intended.  SPF can return `softfail` if it
isn't sure enough about the check failing to indicate a hard fail.  It can also return `none` or `neutral`
which are required to be treated the same way.  In such cases, the SPF checker is saying that the SPF
record either doesn't exist or might as well not exist for all the good it does in this case.

Generally, sites are left to determine whether to accept these emails, or possibly tag them and/or
quarantine them.  So far, this software does not address any of those possible outcomes.  But we can provide
the interesting option of using greylisting for grey areas.

By default, CHAPPS SPF policy enforcement service uses *greylisting* for emails which receive
`softfail` and `none`/`neutral` responses on their SPF checks.  The plan, as it becomes possible for
domain admins to control whether greylisting and/or SPF are applied to their inbound email, is to
greylist even emails which receive `pass` from SPF, meaning that any "deliverable" email will be
deferred unless it is already coming from a recognized source (tuple) when both are enabled.
(Non-deliverable categories are: `fail`, `temperror`, `permerror`.)

## Upcoming features

A mini-roadmap of upcoming changes:

minor:

  - CHAPPS config file INI parsing by ConfigParser will no longer perform interpolation,
    in order to allow passwords to contain any character

major:

  - CHAPPS services will present an API listener on a configurable half-socket, and be able to perform REST
    operations against its own config database, as well as perform live queries against the Redis environment
	in order to report on a user's available quota in real-time, and perform other real-time adjustment
	functions, such as quota reset, user policy flushing, etc.
  - CHAPPS will also offer a multipolicy-inbound service as described above, with SPF+Greylisting.  It will
    allow for a per-domain option indicating whether to apply each of greylisting and SPF.
  - It seems inevitable that other features will also be added.  There is some skeletal code in the repo
    for building email content filters, which are not the same as policy delegates.
  - Using Redis makes it possible to send pub/sub messages when certain sorts of conditions occur, such
    as a user making a large number of attempts to send mail in a short time while overquota, or when
	a user (repeatedly?) attempts to send email as being from a domain that user lacks authorization for.
