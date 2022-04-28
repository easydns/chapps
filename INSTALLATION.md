# CHAPPS Installation

## Prerequisites

CHAPPS requires Python 3.8+

Also required are a MariaDB client, and MariaDB Connector/C.  The
Debian packages are:
  - `mariadb-client`
  - `libmariadb-dev-compat` **Please note** that the package depends
upon the `mariadb` package, and it will fail to install if these
system packages are not present.

A number of community packages are used:
 - `redis`: [**redis-py** by Redis, Inc.](https://pypi.org/project/redis/)
 - `mariadb`: [**MariaDB Connector/Python** by Georg Richter](https://pypi.org/project/mariadb/)
 - `python-pidfile`: [**PIDFile** by Dmitry Orlov](https://pypi.org/project/python-pidfile/)
 - and `expiring-dict`: [**py-expiring-dict** by David Parker](https://pypi.org/project/expiring-dict/)

For SPF:
 - `pyspf`: [by Stuart Gathman, et al.](https://pypi.org/project/pyspf/) for SPF enforcement
 - `dnspython`: [by Bob Halley](https://pypi.org/project/dnspython/) for **pyspf**, or `py3dns`

For the API:
 - 'fastapi': [by Sebastián Ramírez](https://fastapi.tiangolo.com/)
 - 'sqlalchemy': [by Michael Bayer and SQLAlchemy contributors](https://www.sqlalchemy.org/)
 - 'pydantic': [by Samuel Colvin](https://pydantic-docs.helpmanual.io/)
 - 'uvicorn': [by Encode](https://www.uvicorn.org/)
 - 'gunicorn': [by Benoit Chesneau](https://gunicorn.org/)
 - 'mysqlclient': [by Inada Naoki](https://github.com/PyMySQL/mysqlclient)

For testing and development:
 - 'pytest':
 - 'coverage':
 - 'pytest-cov':
 - 'pytest-services':
 - 'pytest-order':
 - 'pytest-asyncio':
 - 'pytest-timeout':
 - 'aiosmtpd':
 - 'python-dotenv':
 - 'pylint-pytest':

MariaDB (or MySQL; support for others is planned) is used as a source of
policy config data.  At present, no other mechanisms are included to
provide this data.  However, some effort was made to design the
adapter mechanism within the service in such a way that other adapters
might provide data from other flavors of database, or from a file
potentially, in small/static deployments.  The database is not yet
used for **Greylisting**; nor for **SPF enforcement**, which gets its
config from the DNS.  Database schema information is provided in the
README file, and a script is provided which will create all the
required tables, provided the configured database is present when it
attempts to connect to the server.

Redis is used by CHAPPS, but it doesn't have to be installed on the
same server.

Services involving mail-filtering (at present, just the null filter
and testing mail-sink) use `aiosmtpd`[The aiosmtpd
Developers](https://pypi.org/project/aiosmtpd/).  This package is used
for testing, but not in the policy server.

The test suite has several more dependencies.  In order to run tests,
or otherwise set up for development work, consider using `pip -r
requirements.txt` to install the last set of frozen dependencies into
a development venv created within a checkout of a fork of this repo.
The tests are not as polished style-wise as the library code; perhaps
when the major features are finished they can be cleaned up some.

## Database Setup

Probably the most important thing to remember is that the CHAPPS
config file path is consciously decoupled from the `venv`, and so it
must be specified as a preface on the commandline, at the least.  It
could also be set in your environment by using `export`, or in your
session setup script (i.e. `.bashrc`).  In some way, it must be
correct when the database setup script runs, in order to ensure that
the proper config is used.

As an example:
```
> CHAPPS_CONFIG=/home/chapps/venv/etc/chapps.ini chapps_database_init.py
```

If you haven't, launch the app once to cause it to create a config
file.  If you have one you want to use, just put it in place.

Another prerequisite is that the database and user named in the config
exist, with proper GRANTs.  If the CHAPPS library is able to log into
the database it is configured to use, the script will cause it to
create the tables it expects to use during normal operation.

That said, running the script is pretty easy.  If the `venv` is
activated, then it is in the path.  If not, it may be invoked by its
full path, something like
`/home/chapps/venv/bin/chapps_database_init.py`.

Once this is done, you can start CHAPPS services once more, and start
configuring and using them.

## CHAPPS Services

CHAPPS tools are generally meant to run as a service (daemon), and
thus managed by SystemD or supervisord.  Since I am working in a
Debian environment, with SystemD, that is what I am aiming to support
first.

It is **highly recommended** to __install CHAPPS via PyPI into a
venv__, and use it from there.  When installed this way, CHAPPS
automatically formats SystemD configuration files which will invoke
the scripts properly so that there is no confusion about how to launch
a service which needs to run in a venv.

For example, in a shell, do this:
```
/home/chapps# python3 -m venv venv
/home/chapps# . venv/bin/activate
/home/chapps# pip install chapps
```
 or `python -m pip install chapps` if you're feeling canonical; once
the venv is activated they amount to the same thing.

Please note that your system may require various system (APT/yum, etc)
packages installed before CHAPPS can install properly.  They are
documented at the top of this file.

After installation, there will be a `chapps` directory under the venv
where installation artifacts and example Postfix configs may be found,
along with a copy of these instructions and the README.  In the
`<venv>/chapps/install` directory, then, you will find the SystemD
profiles and the example **rsyslog** config.  Copy the **rsyslog**
config to `/etc/rsyslog.d` (or whatever location is appropriate), edit
it to your liking, and restart **rsyslog**.  On Ubuntu, it may be
necessary to prepend the name with a number, such as `30-chapps.conf`,
in order to get it to run before all the default log routes are
defined.

It is worth noting that the supplied file only deals with splitting up
log messages locally.  If you want to send messages to a centralized
log server via **syslog**, insert an additional line into the log
config to send messages to that server.  That line might look like:
```
local0.info    @10.1.1.11
```
Replace `10.1.1.11` with the ingress IP address of your **syslog**
concentrator.

As for the SystemD profiles, you may choose to copy them to the system
location, but my recommendtation is to *link* them, using `systemctl
[link|enable] <path>` or the Ansible (et al.) equivalent, to cause
SystemD to make a link from its control directories to these profiles,
which makes administration, uninstallation, upgrading, etc. so much
easier.

If you're copying the files:
Once the SystemD profiles are in place, let SystemD know abouts them by running:
```
systemctl daemon-reload
```
And then, if desired, enable a service to run at boot time with:
```
systemctl enable <service>
```
This will cause the service to be launched at boot time, when Postfix is
launched.
In order to start the service immediately, without rebooting, use:
```
systemctl start <service>
```

### REST API Service

A SystemD service unit file is included, which should work in tandem with
the included socket unit file to allow **nginx** to communicate with the
API via a Unix domain socket (UDS), saving network file descriptors.  This
follows the [SystemD deployment pattern](https://docs.gunicorn.org/en/stable/deploy.html#systemd) outlined in the [Gunicorn documentation](https://docs.gunicorn.org/en/stable/).

Alternatively, the options included in a comment in the service unit
might be uncommented, and the `Type` changed to "normal", the
dependency on the gunicorn socket removed, and the service run as
[Uvicorn workers managed by
Gunicorn](https://fastapi.tiangolo.com/deployment/server-workers/).
At the time of writing, little in-situ testing has ben done to
determine which method is preferable.  This is a private API -- not
meant for public internet consumption -- so performance is not as
serious a concern as it might be otherwise.

For those who might like to do things totally differently, the WSGI
callable which implements the REST API is called `chapps.rest.api:api`,
which is an instance of `FastAPI`.

### To Sum Up
#### (or: Getting the dumb thing to run)

In bullet points, there are the prerequisites:
- the library (and its dependencies) must be in the Python search path
- the script must be executable, and its path must be correct in the
  SystemD profile
- the SystemD profile needs to go into a place where SystemD will find
  it and act on it
- the command `systemctl daemon-reload` is required in order to allow
  SystemD to pick up the new profile(s)
- the command `systemctl enable <service>` is required in order to
  start the service running on boot
- the command `systemctl start <service>` is required in order to
  start the service immediately

Optionally:
- modify your Postfix service profile to add a `Requires=` line to
  ensure that the policy service is running before Postfix starts; we
  use RequiredBy= so this isn't strictly necessary.

## Unrecommended: Global install via shell script

The rest of the instructions are left below in hopes they will be helpful to people who are trying to install with a script, into global system directories.  This really is not a very good idea, and is unlikely to go well, and also is likely to make upgrading really difficult

Proceed at your own risk.

## Using the Install script -- only for git checkouts

From the CHAPPS root, the top of the hierarchy checked out from the
repository, run `install/install.sh`

This script is currently quite stupid and just assumes that your
Python hierarchy is in a particular place.  As I plan to move to
PyPI-based installation in short order, I do not desire to put a lot
of extra work into it.

My plan at present is to create an alternative routine for installing
the service files from a venv, but it is not an extremely high
priority.
