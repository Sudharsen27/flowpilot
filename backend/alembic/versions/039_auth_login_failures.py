"""Store authentication failures for shared login throttling.

Revision ID: 039_auth_login_failures
Revises: 038_forecast_snapshots
Create Date: 2026-11-03

One row per recorded password or Google-link failure. The API counts rows
inside a 15-minute window. Denied attempts are not inserted.

Downgrade drops the table and every recorded failure.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "039_auth_login_failures"
down_revision: str | None = "038_forecast_snapshots"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_login_failures",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("client_ip", sa.String(length=255), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_login_failures_ip_attempted",
        "auth_login_failures",
        ["client_ip", "attempted_at"],
    )
    op.create_index(
        "ix_auth_login_failures_pair_attempted",
        "auth_login_failures",
        ["normalized_email", "client_ip", "attempted_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_login_failures_pair_attempted", table_name="auth_login_failures")
    op.drop_index("ix_auth_login_failures_ip_attempted", table_name="auth_login_failures")
    op.drop_table("auth_login_failures")
