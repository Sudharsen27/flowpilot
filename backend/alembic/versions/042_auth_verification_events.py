"""Store shared IP counters for verification email.

Revision ID: 042_auth_verification_events
Revises: 041_user_email_verified
Create Date: 2026-11-04

One row per counted resend or failed verification. The API counts rows for one
purpose and client IP inside a 15-minute window. Denied attempts are not
inserted. The table stores neither email addresses nor tokens.

Downgrade drops the table and every recorded event.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "042_auth_verification_events"
down_revision: str | None = "041_user_email_verified"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_verification_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("client_ip", sa.String(length=255), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('resend', 'verify_failure')",
            name="ck_auth_verification_events_purpose",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_verification_events_purpose_ip_attempted",
        "auth_verification_events",
        ["purpose", "client_ip", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_verification_events_purpose_ip_attempted",
        table_name="auth_verification_events",
    )
    op.drop_table("auth_verification_events")
