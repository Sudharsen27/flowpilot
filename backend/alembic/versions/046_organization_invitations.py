"""Organization invitations and the active organization preference.

Revision ID: 046_organization_invitations
Revises: 045_website_capture_attempts
Create Date: 2026-11-16

Invitations store a SHA-256 token hash, never the raw token. The role check
allows only ADMIN and MEMBER. One live invite per organization and email is
the partial unique index. Existing users keep a null active organization, so
login continues to use the earliest membership until someone switches.

Downgrade drops the invitation tables and the active-organization column.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "046_organization_invitations"
down_revision: str | None = "045_website_capture_attempts"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("active_organization_id", sa.String(length=36), nullable=True),
    )
    op.create_index(
        op.f("ix_users_active_organization_id"),
        "users",
        ["active_organization_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_users_active_organization_id",
        "users",
        "organizations",
        ["active_organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('ADMIN', 'MEMBER')",
            name="ck_organization_invitations_role",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_organization_invitations_token_hash"),
    )
    op.create_index(
        op.f("ix_organization_invitations_organization_id"),
        "organization_invitations",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "uq_organization_invitations_live_email",
        "organization_invitations",
        ["organization_id", "email"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
        sqlite_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )
    op.create_table(
        "auth_invitation_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("client_ip", sa.String(length=255), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "purpose IN ('create', 'accept_failure')",
            name="ck_auth_invitation_events_purpose",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_invitation_events_purpose_ip_attempted",
        "auth_invitation_events",
        ["purpose", "client_ip", "attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_invitation_events_purpose_org_attempted",
        "auth_invitation_events",
        ["purpose", "organization_id", "attempted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_invitation_events_purpose_org_attempted",
        table_name="auth_invitation_events",
    )
    op.drop_index(
        "ix_auth_invitation_events_purpose_ip_attempted",
        table_name="auth_invitation_events",
    )
    op.drop_table("auth_invitation_events")
    op.drop_index(
        "uq_organization_invitations_live_email",
        table_name="organization_invitations",
    )
    op.drop_index(
        op.f("ix_organization_invitations_organization_id"),
        table_name="organization_invitations",
    )
    op.drop_table("organization_invitations")
    op.drop_constraint("fk_users_active_organization_id", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_active_organization_id"), table_name="users")
    op.drop_column("users", "active_organization_id")
