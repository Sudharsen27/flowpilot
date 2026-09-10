"""Human-authored email body for lead follow-ups.

Revision ID: 014_lead_follow_up_body_text
Revises: 013_lead_follow_ups
Create Date: 2026-09-10

Adds nullable body_text for future automated EMAIL_FOLLOW_UP sending.
Existing rows are left unchanged: EMAIL_FOLLOW_UP rows without a body stay
NULL rather than inventing message content. Application validation requires
a trimmed body on new/updated EMAIL_FOLLOW_UP records.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014_lead_follow_up_body_text"
down_revision: str | None = "013_lead_follow_ups"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lead_follow_ups",
        sa.Column("body_text", sa.String(length=8000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("lead_follow_ups", "body_text")
