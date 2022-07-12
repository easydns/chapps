"""adds SPF and Greylisting defaulting to non-enforcement

Revision ID: 0b5ef72836bd
Revises: ce81767cec26
Create Date: 2022-06-20 13:54:10.920850

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0b5ef72836bd"
down_revision = "ce81767cec26"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "domains",
        sa.Column("greylist", sa.Boolean(name="greylist"), nullable=False),
    )
    op.add_column(
        "domains",
        sa.Column("check_spf", sa.Boolean(name="check_spf"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("domains", "check_spf")
    op.drop_column("domains", "greylist")
