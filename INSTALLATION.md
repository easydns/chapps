# CHAPPS Installation

## Prerequisites

CHAPPS requires Python 3.8+

Also required are a MariaDB client, and MariaDB Connector/C.  The Debian packages are:
  - `mariadb-client`
  - `libmariadb-dev-compat`
**Please note** that the package depends upon the `mariadb` package, and it will fail to
install if these system packages are not present.

A number of community packages are used:
 - `redis`: [**redis-py** by Redis, Inc.](https://pypi.org/project/redis/)
 - `mariadb`: [**MariaDB Connector/Python** by Georg Richter](https://pypi.org/project/mariadb/)
 - `python-pidfile`: [**PIDFile** by Dmitry Orlov](https://pypi.org/project/python-pidfile/)
 - and `expiring-dict`: [**py-expiring-dict** by David Parker](https://pypi.org/project/expiring-dict/)
 for the service itself.
 - `pyspf`: [by Stuart Gathman, et al.](https://pypi.org/project/pyspf/) for SPF enforcement
 - `dnspython`: [by Bob Halley](https://pypi.org/project/dnspython/) for **pyspf**, or `py3dns`

MariaDB (or some other relational database) is used as a source of policy config data.  At present, no other mechanisms are included to provide this data.  However, some effort was made to design the adapter mechanism within the service in such a way that other adapters might provide data from other flavors of database, or from a file potentially, in small/static deployments.  The database is not yet used for **Greylisting**; nor for **SPF enforcement**, which gets its config from the DNS.  Database schema information is provided in the README file, and a script is provided which will create all the required tables, provided the configured database is present when it attempts to connect to the server.

Redis is used by CHAPPS, but it doesn't have to be installed on the same server.

Services involving mail-filtering (at present, just the null filter and testing mail-sink) use `aiosmtpd`[The aiosmtpd Developers](https://pypi.org/project/aiosmtpd/).  This package is used for testing, but not in the policy server.

The test suite has several more dependencies.  In order to run tests, or otherwise set up for development work, consider using `pip -r requirements.txt` to install the last set of frozen dependencies into a development venv created within a checkout of a fork of this repo.  The tests are not as polished style-wise as the library code; you have been warned.

## CHAPPS Services

CHAPPS tools are generally meant to run as a service (daemon), and thus managed by SystemD or supervisord.
Since I am working in a Debian environment, with SystemD, that is what I am aiming to support first.

Right now, I am going to provide SystemD profiles which can be copied to the appropriate location on your
system; for me that location is `/usr/lib/systemd/system`

Once the SystemD profiles are in place, let SystemD know about them by running:
```
systemctl daemon-reload
```
And then, if desired, enable a service to run at boot time with:
```
systemctl enable <service>
```
This will cause the service to be launched at boot time, when Postfix is launched.
In order to start the service immediately, without rebooting, use:
```
systemctl start <service>
```

In bullet points:
- the library (and its dependencies) must be in the Python search path
- the script must be executable, and its path must be correct in the SystemD profile
- the SystemD profile needs to go into a place where SystemD will find it and act on it
- the command `systemctl daemon-reload` is required in order to allow SystemD to pick up the new profile(s)
- the command `systemctl enable <service>` is required in order to start the service running on boot
- the command `systemctl start <service>` is required in order to start the service immediately

Optionally:
- modify your Postfix service profile to add a `Requires=` line to ensure that the policy service is running
  before Postfix starts; we use RequiredBy= so this isn't strictly necessary.

## Using the Install script -- only for git checkouts

From the CHAPPS root, the top of the hierarchy checked out from the repository, run `install/install.sh`

This script is currently quite stupid and just assumes that your Python hierarchy is in a particular place.
As I plan to move to PyPI-based installation in short order, I do not desire to put a lot of extra work into it.

My plan at present is to create an alternative routine for installing the service files from a venv, but
it is not an extremely high priority.
