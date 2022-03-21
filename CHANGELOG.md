# Change Log

##v0.4:
	- introducing a new script to provide a REST API; INSTALLATION
	  instructions will be modified to discuss and provide references
	  for proper, highly-available deployment of the REST API, which
	  it is advised be run on separate servers in order to avoid
	  interfering with email throughput.
	- PyPI package now provides the [API] extras definition, to
      install API prerequisites (which are not otherwise needed)
	- CHANGELOG adapted to be Markdown-compatible

##v0.3.11
	- modifying logic around user-key extraction, and adding new
	  settings: require_user_key (boolean), and no_user_key_response
	  (Postfix response string).  See README for more information.
	- adding some logic to guard against IndexError conditions when
	  calculating time-delta from the attempts list

##v0.3.10
	- adding default config value for `min_delta` to
	  OutboundQuotaPolicy, which defaults to 5.  It represents the
	  minimum number of seconds between attempts; faster attempts will
	  be refused (but reset the timer).
	- correcting problem with recipient-counting wherein the
      recipients memoizing routine ran afoul of __getattr__()
	- correcting problem with recognizing at signs in email addresses

##v0.3.9:
	- correcting import of test library feature into main codebase
	- adding more comprehensive CHAPPSException handling

##v0.3.8:
	- correcting packaging error which prevented installation of
      dependencies

##v0.3.7:
	- removing static SystemD service profiles from pip package; they
      remain in the repo, for use via git clone.
	- correcting fatal bug wherein receiving email with a null sender
	  would cause the application to crash.  It is now possible to
	  specify for each policy whether null senders are "ok"; the
	  default is False.

##v0.3.6:
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

##v0.3.3-5:
	- improvements to setuptools install process (pip / setup.py)
	  which should make it possible to format correct SystemD service
	  description files to run the installed CHAPPS services, even
	  from within their venv

##v0.3.2:
	- putting extra artifacts in a chapps dir, w/i venv or /usr/local
      depending on whether a venv is used

##v0.3.1:
	- Updating documentation

##v0.3:
	- Sender-domain authorization policy allows an RDBMS to indicate
	  which domains a particular user is authorized to emit mail on
	  behalf of.
	- There are more updates to the config file.
	- There are additions to the database schema which should be
      compatible with v0.2

##v0.2.1:
	- Now supports connecting to Redis via Sentinel; provide a
	  space-separated list of host:port info for `sentinel_servers` in
	  the config, and specify the name of the dataset in
	  `sentinel_dataset`
	- Some minor changes to the config file have occured; the
	  `sentinel_master` param and the `db` param have been removed

##v0.2:
	- PLEASE NOTE: the database schema has changed with this update
	- DB access encapsulation and outbound-traffic user identification
      is now independent of any policy or handler
	- some symbol names have been updated for greater clarity
	- the documentation has been improved somewhat; more to come

##v0.1:
	- Outbound Quota and Greylisting policies function, but their
      feature sets may be incomplete.
	- Installation procedure just a bit wonky.