#!/usr/bin/env python3
"""Main CLI module"""
from typing import Optional
from chapps.models import User, Email, Domain, Quota
from chapps.policy import OutboundQuotaPolicy
from chapps.rest.routers.users import (
    user_quota_assoc,
    user_emails_assoc,
    user_domains_assoc,
)
from chapps.dbsession import sql_engine, sessionmaker
from sqlalchemy.exc import IntegrityError
import typer

app = typer.Typer()
Session = sessionmaker(sql_engine)
association = {
    "Email": user_emails_assoc,
    "Domain": user_domains_assoc,
    "Quota": user_quota_assoc,
}


def assocType(resource):
    return Email if "@" in resource else Domain


def showUser(username: str):
    with Session() as sess:
        user = sess.execute(User.select_by_name(username)).scalar()
        quota = Quota.wrap(user.quota)
        emails = Email.wrap(user.emails)
        domains = Domain.wrap(user.domains)
        user = User.wrap(user)
        print(f"User: {user}\n  Quota: {quota}\n  E: {emails}\n  D: {domains}")


def user_or_die(sess: Session, username) -> Optional[str]:
    user = sess.execute(User.select_by_name(username)).scalar()
    if user is None:
        print(
            f"Cannot find user {username}; perhaps they "
            "are identified some other way?"
        )
        raise SystemExit("No such user.")
    return user


@app.command()
def allow(
    username: str,
    email_or_domain: str,
    infile: bool = False,
    create: bool = False,
):
    assoc_type = assocType(email_or_domain)
    with Session() as sess:
        try:
            user = user_or_die(sess, username)
            assoc = sess.execute(
                assoc_type.select_by_name(email_or_domain)
            ).scalar()
            if assoc is None:
                print(
                    f"Creating {assoc_type.__name__.lower()} '{email_or_domain}'."
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
                    "Completely unable to find or create "
                    f"{assoc_type.__name__.lower()} '{email_or_domain}'."
                )
                raise SystemExit(f"No such {assoc_type.__name__.lower()}")
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
            print(f"An exception occurred.  Exiting.")
            raise SystemExit(str(e))
    showUser(username)


@app.command()
def deny(username: str, email_or_domain: str, infile: bool = False):
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
            raise SystemExit(f"No such {assoc_type.__name__.lower()}")
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
    oqp = OutboundQuotaPolicy()
    attkey = oqp._fmtkey(username, "attempts")
    old_att = oqp.redis.zrange(attkey, 0, -1)
    oqp.redis.delete(attkey)
    new_att = oqp.redis.zrange(attkey, 0, -1)
    print(
        f"Dropped {len(old_att)} xmits from log; new log has "
        f"{len(new_att) if new_att else 0}"
    )


@app.command()
def show(username: str):
    showUser(username)


if __name__ == "__main__":
    app()
