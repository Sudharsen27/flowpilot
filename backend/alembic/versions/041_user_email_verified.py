"""Record when a user email address was verified.

Revision ID: 041_user_email_verified
Revises: 040_auth_session_tokens
Create Date: 2026-11-04

Nullable on purpose: there is no server default, so a row inserted after this
revision stays unverified until the application sets the timestamp. Rows that
already exist are grandfathered by copying created_at. That marks "present
before this revision," not a completed verification click.

The API process does not apply Alembic on startup. Apply this revision before
any release that maps email_verified_at starts serving traffic.

Downgrade drops the column. It does not change session_version.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "041_user_email_verified"
down_revision: str | None = "040_auth_session_tokens"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
