"""Website enquiry capture fields on organizations and leads.

Revision ID: 019_website_enquiry_capture
Revises: 018_sales_run_follow_up
Create Date: 2026-09-16

Adds organizations.website_capture_enabled (default false) and leads.enquiry.
No new tables. Capture remains off until an OWNER or ADMIN enables it.
Enquiry is optional on existing leads and is not unique.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019_website_enquiry_capture"
down_revision: str | None = "018_sales_run_follow_up"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "website_capture_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(sa.Column("enquiry", sa.String(length=8000), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_column("enquiry")
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_column("website_capture_enabled")
