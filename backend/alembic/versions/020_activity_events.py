"""Organization activity event log.

Revision ID: 020_activity_events
Revises: 019_website_enquiry_capture
Create Date: 2026-09-17

Append-only tenant-scoped activity_events. Clients cannot write this table.
No historical backfill. Titles and summaries are server-authored; message
bodies, enquiry text, and secrets are not stored.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020_activity_events"
down_revision: str | None = "019_website_enquiry_capture"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "activity_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("agent_id", sa.String(length=36), nullable=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "type IN ('AI_ACTION', 'APPROVAL', 'HUMAN_ACTION', 'SYSTEM_EVENT')",
            name="ck_activity_events_type",
        ),
        sa.CheckConstraint(
            "actor_type IN ('USER', 'AGENT', 'SYSTEM', 'PUBLIC_VISITOR')",
            name="ck_activity_events_actor_type",
        ),
        sa.CheckConstraint(
            "entity_type IN ("
            "'LEAD', 'SALES_RUN', 'LEAD_EMAIL_SEND', 'AGENT_EXECUTION', "
            "'LEAD_FOLLOW_UP', 'LEAD_FOLLOW_UP_EXECUTION', "
            "'LEAD_RESPONSE_DRAFT', 'LEAD_QUALIFICATION')",
            name="ck_activity_events_entity_type",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_activity_events_organization_id"),
        sa.UniqueConstraint(
            "organization_id",
            "dedupe_key",
            name="uq_activity_events_organization_id_dedupe_key",
        ),
    )
    op.create_index(
        "ix_activity_events_organization_id",
        "activity_events",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_actor_user_id",
        "activity_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_agent_id",
        "activity_events",
        ["agent_id"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_lead_id",
        "activity_events",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_organization_id_occurred_at_id",
        "activity_events",
        ["organization_id", "occurred_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_organization_id_type_occurred_at",
        "activity_events",
        ["organization_id", "type", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_activity_events_organization_id_entity_type_entity_id",
        "activity_events",
        ["organization_id", "entity_type", "entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_activity_events_organization_id_entity_type_entity_id",
        table_name="activity_events",
    )
    op.drop_index(
        "ix_activity_events_organization_id_type_occurred_at",
        table_name="activity_events",
    )
    op.drop_index(
        "ix_activity_events_organization_id_occurred_at_id",
        table_name="activity_events",
    )
    op.drop_index("ix_activity_events_lead_id", table_name="activity_events")
    op.drop_index("ix_activity_events_agent_id", table_name="activity_events")
    op.drop_index("ix_activity_events_actor_user_id", table_name="activity_events")
    op.drop_index("ix_activity_events_organization_id", table_name="activity_events")
    op.drop_table("activity_events")
