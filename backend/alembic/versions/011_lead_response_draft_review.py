"""Human review columns for lead response drafts.

Revision ID: 011_lead_response_draft_review
Revises: 010_lead_response_drafts
Create Date: 2026-09-10

Adds original/current response text, review lifecycle, reviewer, revision,
and rejection reason. Generation status remains COMPLETED/FAILED. Approval
does not send messages or change Lead.status.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011_lead_response_draft_review"
down_revision: str | None = "010_lead_response_drafts"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lead_response_drafts",
        sa.Column("review_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "lead_response_drafts",
        sa.Column("original_response", sa.String(length=8000), nullable=True),
    )
    op.add_column(
        "lead_response_drafts",
        sa.Column("current_response", sa.String(length=8000), nullable=True),
    )
    op.add_column(
        "lead_response_drafts",
        sa.Column("rejection_reason", sa.String(length=1000), nullable=True),
    )
    op.add_column(
        "lead_response_drafts",
        sa.Column("reviewed_by_user_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "lead_response_drafts",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lead_response_drafts",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "lead_response_drafts",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_foreign_key(
        "fk_lead_response_drafts_reviewed_by_user_id",
        "lead_response_drafts",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_lead_response_drafts_reviewed_by_user_id"),
        "lead_response_drafts",
        ["reviewed_by_user_id"],
    )
    op.create_check_constraint(
        "ck_lead_response_drafts_review_status",
        "lead_response_drafts",
        "review_status IS NULL OR review_status IN "
        "('GENERATED', 'EDITED', 'APPROVED', 'REJECTED')",
    )
    op.execute(
        sa.text(
            "UPDATE lead_response_drafts SET "
            "original_response = result->>'response', "
            "current_response = result->>'response', "
            "review_status = 'GENERATED', "
            "updated_at = created_at "
            "WHERE status = 'COMPLETED' AND result IS NOT NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE lead_response_drafts SET updated_at = created_at "
            "WHERE updated_at IS NULL"
        )
    )
    op.alter_column("lead_response_drafts", "revision", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "ck_lead_response_drafts_review_status",
        "lead_response_drafts",
        type_="check",
    )
    op.drop_index(
        op.f("ix_lead_response_drafts_reviewed_by_user_id"),
        table_name="lead_response_drafts",
    )
    op.drop_constraint(
        "fk_lead_response_drafts_reviewed_by_user_id",
        "lead_response_drafts",
        type_="foreignkey",
    )
    op.drop_column("lead_response_drafts", "updated_at")
    op.drop_column("lead_response_drafts", "revision")
    op.drop_column("lead_response_drafts", "reviewed_at")
    op.drop_column("lead_response_drafts", "reviewed_by_user_id")
    op.drop_column("lead_response_drafts", "rejection_reason")
    op.drop_column("lead_response_drafts", "current_response")
    op.drop_column("lead_response_drafts", "original_response")
    op.drop_column("lead_response_drafts", "review_status")
