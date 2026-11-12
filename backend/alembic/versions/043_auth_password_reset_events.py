"""Store shared IP counters for password-reset requests.

Revision ID: 043_auth_password_reset_events
Revises: 042_auth_verification_events
Create Date: 2026-11-12

One row per counted password-reset request. The API counts rows for one client
IP inside a 15-minute window. Denied attempts are not inserted. The table
stores neither email addresses nor tokens.

Downgrade drops the table and every recorded event.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "043_auth_password_reset_events"
down_revision: str | None = "042_auth_verification_events"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_password_reset_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_ip", sa.String(length=255), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_password_reset_events_ip_attempted",
        "auth_password_reset_events",
        ["client_ip", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_password_reset_events_ip_attempted",
        table_name="auth_password_reset_events",
    )
    op.drop_table("auth_password_reset_events")
