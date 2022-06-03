#!/usr/bin/env python3
"""Main CLI module"""
from typing import Optional, Union, List
from contextlib import contextmanager
from chapps.models import User, Email, Domain, Quota
from chapps.policy import OutboundQuotaPolicy
from chapps.rest.routers.users import (
    user_quota_assoc,
    user_emails_assoc,
    user_domains_assoc,
)
from chapps.dbsession import sql_engine, sessionmaker
from sqlalchemy.exc import IntegrityError
from pathlib import Path
import typer

app = typer.Typer(help="CHAPPS Configuration Management CLI")
Session = sessionmaker(sql_engine)
association = {
    "Email": user_emails_assoc,
    "Domain": user_domains_assoc,
    "Quota": user_quota_assoc,
}

MIN_IMPORT_LINE_LENGTH = 6 + 5 + 4  # assuming tiniest emails and domains
"""There is always an operation and there are 2 colons, username, and a resource"""


class CHAPPS_CLI_Exception(Exception):
    """Superclass for CLI Exceptions"""


class UnrecoverableException(CHAPPS_CLI_Exception):
    """
    Raising this error indicates that the underlying routine cannot continue
    """


class NoSuchUserException(UnrecoverableException):
    """No such User as the one provided exists in the control DB"""


class NoSuchAssocException(UnrecoverableException):
    """No matching associated resource could be found"""


class NoSuchQuotaException(UnrecoverableException):
    """No matching quota record cold be found"""


class ImportParseError(UnrecoverableException):
    """A line in the imported file could not be parsed"""


class NoSuchOperationError(ImportParseError):
    """A line in the imported file contained an unrecognized operation"""


def assocType(resource):
    """Determine resource type

    .. todo::

      Add validation to resource-type ID in CLI
    """
    return Email if "@" in resource else Domain


@contextmanager
def handle_cli_exceptions():
    try:
        yield
    except UnrecoverableException as e:
        raise typer.Exit(code=1)


def _print(msg):
    typer.echo(msg)


def _b(msg):
    return typer.style(msg, fg=typer.colors.WHITE, bold=True)


def _red(msg):
    return typer.style(msg, fg=typer.colors.RED, bold=True)


def _yellow(msg):
    return typer.style(msg, fg=typer.colors.YELLOW, bold=True, underline=True)


def _alert(msg):
    b = _red(">>>")
    e = _red("<<<")
    m = _yellow(msg)
    return " ".join([b, m, e])


def user_or_die(sess: Session, username: str) -> Optional[str]:
    user = sess.execute(User.select_by_name(username)).scalar()
    if user is None:
        _print(
            f"Cannot find user {_b(username)}\nPerhaps they "
            "are identified some other way?"
        )
        raise NoSuchUserException(f"No such user '{username}'.")
    return user


def showUser(username: str, *, quota: bool = False):
    with Session() as sess:
        user = user_or_die(sess, username)
        q = user.quota
        u_quota = Quota.wrap(q)
        emails = Email.wrap(user.emails)
        domains = Domain.wrap(user.domains)
        user = User.wrap(user)
        _print(
            f"User: {user}\n  Quota: {u_quota}\n  E: {emails}\n  D: {domains}"
        )
    if quota and q:
        oqp = OutboundQuotaPolicy()
        avail, remarks = oqp.current_quota(username, q)
        limit = oqp.redis.get(oqp._fmtkey(username, "limit"))
        limit = limit.decode("utf-8") if limit else "none"
        _print(f"Outbound email quota remaining: {_b(avail)}/{limit} (cached)")
        if remarks:
            _print("\n".join(remarks))
    if q is None:
        _print(
            _alert(
                "This user has no quota policy assigned and so "
                "cannot send mail"
            )
        )
    if len(domains) + len(emails) < 1:
        _print(
            _alert(
                "This user has no domains or emails assigned "
                "and so cannot send mail"
            )
        )


@app.command()
def allow(username: str, email_or_domain: str, create: bool = False):
    """Permit a user to send email from a domain or as a whole email address

    Pass the --create flag to this command in order to allow creation of
    nonexistent Email or Domain entries.
    """
    with handle_cli_exceptions():
        return _allow(username, email_or_domain, create)


def _allow(username: str, email_or_domain: str, create: bool = False):
    assoc_type = assocType(email_or_domain)
    with Session() as sess:
        try:
            user = user_or_die(sess, username)
            assoc = sess.execute(
                assoc_type.select_by_name(email_or_domain)
            ).scalar()
            if create and (assoc is None):
                _print(
                    f"Creating {assoc_type.__name__.lower()} "
                    f"'{email_or_domain}'."
                )
                try:
                    sess.add(assoc_type.Meta.orm_model(name=email_or_domain))
                except IntegrityError as e:
                    _print(
                        f"  Encountered integrity error: {e}; "
                        "attempting to look up resource afresh."
                    )
                    pass
                assoc = sess.execute(
                    assoc_type.select_by_name(email_or_domain)
                ).scalar()
            if assoc is None:
                _print(
                    "Unable to find or create "
                    f"{assoc_type.__name__.lower()} '{_b(email_or_domain)}'."
                )
                raise NoSuchAssocException(
                    f"No such {assoc_type.__name__.lower()} '{email_or_domain}'."
                )
            sess.execute(
                association[assoc_type.__name__].insert_assoc(
                    user.id, assoc.id
                )
            )
            _print(
                f"Allowing user '{username}' to send from "
                f"{assoc_type.__name__.lower()} '{assoc.name}'"
            )
            sess.commit()
        except Exception as e:
            raise e
    showUser(username)


@app.command()
def deny(username: str, email_or_domain: str):
    """Prevent a user sending email appearing to come from a domain or email

    Both entities must already exist; not having any record for a domain
    or email means no one has permission.
    """
    with handle_cli_exceptions():
        return _deny(username, email_or_domain)


def _deny(username: str, email_or_domain: str, *args):
    assoc_type = assocType(email_or_domain)
    with Session() as sess:
        user = user_or_die(sess, username)
        assoc = sess.execute(
            assoc_type.select_by_name(email_or_domain)
        ).scalar()
        if assoc is None:
            _print(
                f"No {assoc_type.__name__.lower()} named '{_b(email_or_domain)}'"
                f" could be found.  Please check the spelling and try again."
            )
            raise NoSuchAssocException(
                f"No such {assoc_type.__name__.lower()} '{email_or_domain}'."
            )
        sess.execute(
            association[assoc_type.__name__].delete_assoc(user.id, assoc.id)
        )
        _print(
            f"Denying user '{username}' ability to send from "
            f"{assoc_type.__name__.lower()} '{assoc.name}'"
        )
        sess.commit()
    showUser(username)


@app.command()
def reset(username: str, refresh: bool = True):
    """Reset a user's quota, making it seem they've sent no email

    CHAPPS keeps a day-long log of all attempts to send email.  This routine
    drops those records for the named user.  It reports the length of the list
    before and after, for clarity and verification.

    If this routine discovers that the cached sending limit in Redis does not
    match the current contents of the policy configuration database, it will
    cause Redis to be updated with the correct data from the policy database.
    Provide the --no-refresh flag to suppress this behavior.

    """
    with handle_cli_exceptions():
        with Session() as sess:
            user = user_or_die(sess, username)
            quota = user.quota
        oqp = OutboundQuotaPolicy()
        attkey = oqp._fmtkey(username, "attempts")
        limitkey = oqp._fmtkey(username, "limit")
        old_att = oqp.redis.zrange(attkey, 0, -1)
        old_limit = oqp.redis.get(limitkey)
        old_limit = int(old_limit.decode("utf-8")) if old_limit else None
        oqp.redis.delete(attkey)
        new_att = oqp.redis.zrange(attkey, 0, -1)
        _print(
            f"Dropped {len(old_att)} xmits from log; new log has "
            f"{len(new_att) if new_att else 0}"
        )
        if quota and refresh and (old_limit != quota.quota):
            _print(
                _b(
                    f"Cached quota {old_limit} does not match quota policy "
                    f"limit {quota.quota}; adjusting."
                )
            )
            oqp.refresh_policy_cache(username, quota)
        showUser(username, quota=True)


@app.command()
def refresh(username: str):
    """Refresh quota policy cache for a user

    This syncs up CHAPPS's operational idea of a user's limit with their
    configured limit in the policy database.
    """
    with handle_cli_exceptions():
        with Session() as sess:
            user = user_or_die(sess, username)
            quota = user.quota
        _print(f"Refreshing quota policy cache for user '{username}'")
        OutboundQuotaPolicy().refresh_policy_cache(username, quota)
        showUser(username, quota=True)


@app.command()
def show(username: str, quota: bool = False):
    """Show data about a user's configuration

    Supply the --quota flag to see real-time data about available quota and
    cached quota limit.

    """
    with handle_cli_exceptions():
        showUser(username, quota=quota)


@app.command()
def set_quota(username: str, quota: str):
    """Assign a user an existing quota

    The user and quota are both referred to by their names.

    This command cannot create Quota records.
    """
    with handle_cli_exceptions():
        return _set_quota(username, quota)


def _set_quota(username: str, quota: str, *args):
    with Session() as sess:
        user = user_or_die(sess, username)
        quota_orm = sess.execute(Quota.select_by_name(quota)).scalar()
        if quota_orm:
            _print(f"Assigning quota '{quota}' to user '{username}'")
            user.quota = quota_orm
            sess.commit()
        else:
            _print(f"Unable to find a quota named '{_b(quota)}'")
            raise NoSuchQuotaException("No such quota " + quota)
    showUser(username)


operation_map = dict(allow=_allow, deny=_deny, quota=_set_quota)


@app.command()
def import_file(filename: str, create: bool = False):
    """Import a permissions assigment file

    Provided for simplifying entry of large amounts of data at once.  This
    routine is not currently optimized for 1000s of entries, but should be okay
    for 100s.

    This feature runs successive `allow`, `deny` or `set-quota` commands, as
    specified by the first token in the line:

      ['allow', 'deny', 'quota']:<user>:<email,domain, or quota>

    using the next two tokens as the user and the resource in that order, just
    like on the commandline.  In the file, the tokens are separated by colons
    (:) without spaces.  Leading and trailing whitespace is ignored.  Lines
    starting with a hash mark (#) are ignored, as are lines under 15 characters
    in length.

    As an example, to allow user `caleb@chapps.io` to send email which appears to
    originate from `chapps.com`, create an entry in the import file like so:

      allow:caleb@chapps.io:chapps.com
      quota:caleb@chapps.io:Q1000

    The second line assigns the quota named `Q1000` to the user `caleb@chapps.io`.

    Pass the filename as an argument to the import_file command.

    Optionally, supply the --create flag to be passed through to allow, in
    order to allow nonexistent resources to be created.

    """
    import_path = Path(filename)
    if not import_path.exists():
        _print("Cannot find " + _b(filename))
        raise typer.Exit(code=1)
    exceptions = []
    with import_path.open("r") as fh:
        lineno = 0
        for line in fh:
            lineno += 1
            line = line.strip()
            if (len(line) < MIN_IMPORT_LINE_LENGTH) or (line[0] == "#"):
                continue
            _print(f"\nLine {lineno}:")
            try:
                operation, user, resource = line.split(":")
                op = operation_map[operation]
                op(user, resource, create)
            except ValueError as e:
                _print(
                    "Lines are expected to be three tokens separated by ':' "
                    "(colon); the tokens themselves may not contain colons."
                )
                exceptions.append(f"Line {lineno}: {e}: " + line)
                continue
            except KeyError:
                msg = f"Nonexistent operation {operation}"
                _print(msg)
                exceptions.append(f"Line {lineno}: {msg}")
                continue
            except UnrecoverableException as e:
                # no print here as the other routines generally do that
                exceptions.append(f"Line {lineno}: {e}")
                continue
    if exceptions:
        _print(
            _b(
                "\nThe following lines of the input file caused exceptions and"
                " were not executed:"
            )
        )
        _print("\n".join(exceptions))


if __name__ == "__main__":
    app()
