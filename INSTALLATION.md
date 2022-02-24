# CHAPPS Installation

## A work in progress

### Prerequisites

CHAPPS requires Python 3.8+

A number of community packages are used:
 - `redis`: [**redis-py** by Redis, Inc.](https://pypi.org/project/redis/)
 - `mariadb`: [**MariaDB Connector/Python** by Georg Richter](https://pypi.org/project/mariadb/)
 - `python-pidfile`: [**PIDFile** by Dmitry Orlov](https://pypi.org/project/python-pidfile/)
 - and `expiring-dict`: [**py-expiring-dict** by David Parker](https://pypi.org/project/expiring-dict/)
 for the service itself.
 - `pyspf`: []() for SPF enforcement
 - `dnspython`: []() for **pyspf**, or `py3dns`

MariaDB (or some other relational database) is used as a source of **Outbound Quota Policy** data.  At present, no other mechanisms are included to provide this data.  However, some effort was made to design the adapter mechanism within the service in such a way that other adapters might provide data from other flavors of database, or from a file potentially, in small/static deployments.  The database is not used for **Greylisting** or for **SPF enforcement**, which gets its config from the DNS.

MariaDB and `pyspf` packages seem to require root privilege to install properly.

Services involving mail-filtering (at present, just the null filter) use `aiosmtpd`[The aiosmtpd Developers](https://pypi.org/project/aiosmtpd/).  This package is also used for testing, but not in the policy server.

The test suite has several more dependencies; in order to run tests, or otherwise set up for development work, consider using `pip -r requirements.txt` to install the last set of frozen dependencies.

### CHAPPS Services

Right now only one service may run at a time due to port-configuration inflexibility which will be addressed
in a future version.  The existing state of the software is sufficient for evaluation of its basic fitness.

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

Until the package is coming down from PyPI, it will be necessary to choose a location to place the git repo,
then make a copy of the SystemD profile and modify it to reflect the proper path to the scripts.  In addition,
the Python package (library) itself will need to be placed in a location which puts it in the Python search
path, or a virtualenv can be used (though there are some tricks to doing this with a service.)

Ideally, the whole thing gets installed by PyPI, and then tho' the paths to the scripts may be weird, they
will be known and can be substituted into the SystemD profile template during installation.

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

### Using the Install script

From the CHAPPS root, the top of the hierarchy checked out from the repository, run `install/install.sh`

This script is currently quite stupid and just assumes that your Python hierarchy is in a particular place.
As I plan to move to PyPI-based installation in short order, I do not desire to put a lot of extra work into it.
