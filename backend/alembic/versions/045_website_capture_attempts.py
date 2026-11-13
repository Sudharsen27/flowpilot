"""Store shared website-capture attempt rows.

Revision ID: 045_website_capture_attempts
Revises: 044_chronological_order
Create Date: 2026-11-13

One row per accepted public enquiry or honeypot hit for an enabled
organization. The API counts rows inside the sliding burst window and the
UTC day. Denied attempts are not inserted. The table stores neither the
enquiry nor the visitor email.

Downgrade drops the table and every recorded attempt.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "045_website_capture_attempts"
down_revision: str | None = "044_chronological_order"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "website_capture_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("client_key", sa.String(length=255), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumes_daily", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_website_capture_attempts_organization_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_website_capture_attempts_org_client_attempted",
        "website_capture_attempts",
        ["organization_id", "client_key", "attempted_at"],
    )
    op.create_index(
        "ix_website_capture_attempts_org_attempted",
        "website_capture_attempts",
        ["organization_id", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_website_capture_attempts_org_attempted",
        table_name="website_capture_attempts",
    )
    op.drop_index(
        "ix_website_capture_attempts_org_client_attempted",
        table_name="website_capture_attempts",
    )
    op.drop_table("website_capture_attempts")
