"""Store hashed one-time auth tokens and a session version.

Revision ID: 040_auth_session_tokens
Revises: 039_auth_login_failures
Create Date: 2026-11-03

Existing users receive session_version 0. This revision does not increment it.
The API process does not apply Alembic on startup. Apply this revision before
any release that maps these columns starts serving traffic.

Downgrade drops the token table and the session version column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "040_auth_session_tokens"
down_revision: str | None = "039_auth_login_failures"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("session_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_check_constraint(
        "ck_users_session_version",
        "users",
        "session_version >= 0",
    )
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('verify_email', 'reset_password')",
            name="ck_auth_tokens_purpose",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_tokens_token_hash"),
    )
    op.create_index(op.f("ix_auth_tokens_user_id"), "auth_tokens", ["user_id"], unique=False)
    op.create_index(
        "uq_auth_tokens_active_user_purpose",
        "auth_tokens",
        ["user_id", "purpose"],
        unique=True,
        postgresql_where=sa.text("used_at IS NULL"),
        sqlite_where=sa.text("used_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_auth_tokens_active_user_purpose", table_name="auth_tokens")
    op.drop_index(op.f("ix_auth_tokens_user_id"), table_name="auth_tokens")
    op.drop_table("auth_tokens")
    op.drop_constraint("ck_users_session_version", "users", type_="check")
    op.drop_column("users", "session_version")
