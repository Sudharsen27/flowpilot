"""Add team-written knowledge entries used as trusted AI draft context.

Revision ID: 024_knowledge_entries
Revises: 023_inbound_emails
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "024_knowledge_entries"
down_revision: str | None = "023_inbound_emails"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_ENTITY_TYPES_BEFORE = (
    "'LEAD', 'SALES_RUN', 'LEAD_EMAIL_SEND', 'AGENT_EXECUTION', "
    "'LEAD_FOLLOW_UP', 'LEAD_FOLLOW_UP_EXECUTION', "
    "'LEAD_RESPONSE_DRAFT', 'LEAD_QUALIFICATION'"
)
_ENTITY_TYPES_AFTER = f"{_ENTITY_TYPES_BEFORE}, 'KNOWLEDGE_ENTRY'"


def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("use_in_ai", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('FAQ', 'PRODUCT', 'POLICY', 'COMPANY', 'OTHER')",
            name="ck_knowledge_entries_category",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'ARCHIVED')", name="ck_knowledge_entries_status"
        ),
        sa.CheckConstraint("revision >= 1", name="ck_knowledge_entries_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_knowledge_entries_organization_id"),
    )
    op.create_index(
        "ix_knowledge_entries_organization_id",
        "knowledge_entries",
        ["organization_id"],
    )
    op.create_index(
        "ix_knowledge_entries_organization_id_status_updated_at",
        "knowledge_entries",
        ["organization_id", "status", "updated_at"],
    )
    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.drop_constraint("ck_activity_events_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_activity_events_entity_type", f"entity_type IN ({_ENTITY_TYPES_AFTER})"
        )


def downgrade() -> None:
    op.execute("DELETE FROM activity_events WHERE entity_type = 'KNOWLEDGE_ENTRY'")
    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.drop_constraint("ck_activity_events_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_activity_events_entity_type", f"entity_type IN ({_ENTITY_TYPES_BEFORE})"
        )
    op.drop_index(
        "ix_knowledge_entries_organization_id_status_updated_at", table_name="knowledge_entries"
    )
    op.drop_index("ix_knowledge_entries_organization_id", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")
