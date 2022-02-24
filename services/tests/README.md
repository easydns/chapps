# CHAPPS Service Testing Notes

## The gist: test only one at a time

The tests for CHAPPS service scripts are set up to be run separately, and currently with a fair amount of manual intervention.
This is primarily because on a regular workstation, Postfix may only be invoked by root.  Given that, it makes little sense to
struggle, instead, I have just been installing the proper Postfix config and restarting Postfix before running the integration
tests for each particular service.

What I think might be nicer is to have a bit of additional framework, to spin up however many VMs, and use each one to configure
a custom Postfix for testing that one service.  I think that with Vagrant and pytest-xdist something like this might be possible
but I need to stay focused on getting the primary features finished so that the team can make progress.

And so, here we are.  The postfix directory off the root of the project contains subdirs with `main.cf` and `master.cf` in them,
suitable for possibly using in `postfix -c` invocations.  Since my workstation is not generally a Postfix server, I have just
been hijacking it, copying the configs into place to test a service at a time, since each needs a different thing.

The configurations are not mutually-exclusive*, but having everything running at once must be its own, separate test; each
component must also be tested individually first.  (*Inbound and outbound functions rarely operate on the same server, at
this scale, so in a sense, some configurations may be exclusive.)

Once the configs are in place, possibly modified for your particular site, and Postfix is restarted, just run the particular
test like so:
```
pytest -v services/tests/test_outbound_quota
```
to test the outbound quota policy service (script).

Since this is the same service which will be running and providing the policy, these tests deliver an end-to-end validation
of the desired logic.  They also serve as a way to validate the Postfix config, to ensure that it will actually do what is
expected.
