"""Persist organization-scoped ICP configuration.

Revision ID: 031_ideal_customer_profiles
Revises: 030_user_google_oauth
Create Date: 2026-10-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "031_ideal_customer_profiles"
down_revision: str | None = "030_user_google_oauth"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ideal_customer_profiles",
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organization_id"),
    )


def downgrade() -> None:
    op.drop_table("ideal_customer_profiles")