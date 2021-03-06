"""v0.4.12 DB setup

Revision ID: ce81767cec26
Revises:
Create Date: 2022-06-17 14:10:18.442341

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ce81767cec26"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "domains",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_domains")),
    )
    op.create_index(op.f("ix_domains_name"), "domains", ["name"], unique=True)
    op.create_table(
        "emails",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_emails")),
    )
    op.create_index(op.f("ix_emails_name"), "emails", ["name"], unique=True)
    op.create_table(
        "quotas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("quota", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_quotas")),
    )
    op.create_index(op.f("ix_quotas_name"), "quotas", ["name"], unique=True)
    op.create_index(op.f("ix_quotas_quota"), "quotas", ["quota"], unique=True)
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_name"), "users", ["name"], unique=True)
    op.create_table(
        "domain_user",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("domain_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["domain_id"],
            ["domains.id"],
            name=op.f("fk_domain_user_domain_id_domains"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_domain_user_user_id_users"),
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "domain_id", name=op.f("pk_domain_user")
        ),
    )
    op.create_table(
        "email_user",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("email_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["email_id"],
            ["emails.id"],
            name=op.f("fk_email_user_email_id_emails"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_email_user_user_id_users"),
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "email_id", name=op.f("pk_email_user")
        ),
    )
    op.create_table(
        "quota_user",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("quota_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["quota_id"],
            ["quotas.id"],
            name=op.f("fk_quota_user_quota_id_quotas"),
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_quota_user_user_id_users"),
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_quota_user")),
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table("quota_user")
    op.drop_table("email_user")
    op.drop_table("domain_user")
    op.drop_index(op.f("ix_users_name"), table_name="users")
    op.drop_table("users")
    op.drop_index(op.f("ix_quotas_quota"), table_name="quotas")
    op.drop_index(op.f("ix_quotas_name"), table_name="quotas")
    op.drop_table("quotas")
    op.drop_index(op.f("ix_emails_name"), table_name="emails")
    op.drop_table("emails")
    op.drop_index(op.f("ix_domains_name"), table_name="domains")
    op.drop_table("domains")
    # ### end Alembic commands ###
