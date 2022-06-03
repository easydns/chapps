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

app = typer.Typer()
Session = sessionmaker(sql_engine)
association = {
    "Email": user_emails_assoc,
    "Domain": user_domains_assoc,
    "Quota": user_quota_assoc,
}

MIN_IMPORT_LINE_LENGTH = 6 + 5 + 4  # assuming tiniest emails and domains
"""There is always an operation and there are 2 colons, for a minimum of 6"""


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
        raise SystemExit(str(e))


def showUser(username: str, *, quota: bool = False):
    with Session() as sess:
        user = user_or_die(sess, username)
        q = user.quota
        u_quota = Quota.wrap(q)
        emails = Email.wrap(user.emails)
        domains = Domain.wrap(user.domains)
        user = User.wrap(user)
        print(
            f"User: {user}\n  Quota: {u_quota}\n  E: {emails}\n  D: {domains}"
        )
    if quota and q:
        oqp = OutboundQuotaPolicy()
        avail, remarks = oqp.current_quota(username, q)
        limit = oqp.redis.get(oqp._fmtkey(username, "limit"))
        limit = limit.decode("utf-8") if limit else "none"
        print(f"Outbound email quota remaining: {avail}/{limit} (cached)")
        print("\n".join(remarks))
    if q is None:
        print(
            ">>> This user has no quota policy assigned and so "
            "cannot send mail <<<"
        )
    if len(domains) + len(emails) < 1:
        print(
            ">>> This user has no domains or emails assigned"
            "and so cannot send mail <<<"
        )


def user_or_die(sess: Session, username: str) -> Optional[str]:
    user = sess.execute(User.select_by_name(username)).scalar()
    if user is None:
        print(
            f"Cannot find user {username}; perhaps they "
            "are identified some other way?"
        )
        raise NoSuchUserException(f"No such user '{username}'.")
    return user


@app.command()
def allow(username: str, email_or_domain: str, create: bool = False):
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
                print(
                    f"Creating {assoc_type.__name__.lower()} "
                    f"'{email_or_domain}'."
                )
                try:
                    sess.add(assoc_type.Meta.orm_model(name=email_or_domain))
                except IntegrityError as e:
                    print(
                        f"  Encountered integrity error: {e}; "
                        "attempting to look up resource afresh."
                    )
                    pass
                assoc = sess.execute(
                    assoc_type.select_by_name(email_or_domain)
                ).scalar()
            if assoc is None:
                print(
                    "Unable to find or create "
                    f"{assoc_type.__name__.lower()} '{email_or_domain}'."
                )
                raise NoSuchAssocException(
                    f"No such {assoc_type.__name__.lower()} '{email_or_domain}'."
                )
            sess.execute(
                association[assoc_type.__name__].insert_assoc(
                    user.id, assoc.id
                )
            )
            print(
                f"Allowing user '{username}' to send from "
                f"{assoc_type.__name__.lower()} '{assoc.name}'"
            )
            sess.commit()
        except Exception as e:
            raise e
    showUser(username)


@app.command()
def deny(username: str, email_or_domain: str):
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
            print(
                f"No {assoc_type.__name__.lower()} named '{email_or_domain}'"
                f" could be found.  Please check the spelling and try again."
            )
            raise NoSuchAssocException(
                f"No such {assoc_type.__name__.lower()} '{email_or_domain}'."
            )
        sess.execute(
            association[assoc_type.__name__].delete_assoc(user.id, assoc.id)
        )
        print(
            f"Denying user '{username}' ability to send from "
            f"{assoc_type.__name__.lower()} '{assoc.name}'"
        )
        sess.commit()
    showUser(username)


@app.command()
def reset(username: str):
    with handle_cli_exceptions():
        with Session() as sess:
            user = user_or_die(sess, username)
            quota = user.quota
        oqp = OutboundQuotaPolicy()
        attkey = oqp._fmtkey(username, "attempts")
        limitkey = oqp._fmtkey(username, "limit")
        old_att = oqp.redis.zrange(attkey, 0, -1)
        old_limit = oqp.redis.get(limitkey).decode("utf-8")
        oqp.redis.delete(attkey)
        new_att = oqp.redis.zrange(attkey, 0, -1)
        print(
            f"Dropped {len(old_att)} xmits from log; new log has "
            f"{len(new_att) if new_att else 0}"
        )
        if old_limit != quota.quota:
            print(
                f"Cached quota {old_limit} does not match quota policy limit "
                f"{quota.quota}; adjusting."
            )
            oqp.refresh_policy_cache(username, quota)
        showUser(username, quota=True)


@app.command()
def refresh(username: str):
    with handle_cli_exceptions():
        with Session() as sess:
            user = user_or_die(sess, username)
            quota = user.quota
        print(f"Refreshing quota policy cache for user '{username}'")
        OutboundQuotaPolicy().refresh_policy_cache(username, quota)
        showUser(username, quota=True)


@app.command()
def show(username: str, quota: bool = False):
    with handle_cli_exceptions():
        showUser(username, quota=True)


operation_map = dict(allow=_allow, deny=_deny)


@app.command()
def import_file(filename: str, create: bool = False):
    import_path = Path(filename)
    if not import_path.exists():
        raise SystemExit(f"No such file as {filename} can be found.")
    exceptions = []
    with import_path.open("r") as fh:
        lineno = 0
        for line in fh:
            lineno += 1
            line = line.strip()
            if (len(line) < MIN_IMPORT_LINE_LENGTH) or (line[0] == "#"):
                continue
            print(f"\nLine {lineno}:")
            try:
                operation, user, resource = line.split(":")
                op = operation_map[operation]
                op(user, resource, create)
            except ValueError as e:
                print(
                    "Lines are expected to be three tokens separated by ':' "
                    "(colon); the tokens themselves may not contain colons."
                )
                exceptions.append(f"Line {lineno}: {e}: " + line)
                continue
            except KeyError:
                msg = f"Nonexistent operation {operation}"
                print(msg)
                exceptions.append(f"Line {lineno}: {msg}")
                continue
            except UnrecoverableException as e:
                exceptions.append(f"Line {lineno}: {e}")
                continue
    if exceptions:
        print(
            "\nThe following lines of the input file caused exceptions and"
            " were not executed:"
        )
        print("\n".join(exceptions))


if __name__ == "__main__":
    app()
