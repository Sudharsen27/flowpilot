"""Add outgoing webhook endpoints and their delivery log.

Revision ID: 026_webhooks
Revises: 025_workflows
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "026_webhooks"
down_revision: str | None = "025_workflows"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_ENTITY_TYPES_BEFORE = (
    "'LEAD', 'SALES_RUN', 'LEAD_EMAIL_SEND', 'AGENT_EXECUTION', "
    "'LEAD_FOLLOW_UP', 'LEAD_FOLLOW_UP_EXECUTION', "
    "'LEAD_RESPONSE_DRAFT', 'LEAD_QUALIFICATION', 'KNOWLEDGE_ENTRY', 'WORKFLOW_RULE'"
)
_ENTITY_TYPES_AFTER = f"{_ENTITY_TYPES_BEFORE}, 'WEBHOOK_ENDPOINT'"


def _timestamp(name: str, *, nullable: bool = False, default: bool = True) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP") if default else None,
        nullable=nullable,
    )


def upgrade() -> None:
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("secret_salt", sa.String(length=64), nullable=False),
        sa.Column("secret_hint", sa.String(length=8), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint("revision >= 1", name="ck_webhook_endpoints_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_webhook_endpoints_organization_id"),
    )
    op.create_index(
        "ix_webhook_endpoints_organization_id", "webhook_endpoints", ["organization_id"]
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("endpoint_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("event_key", sa.String(length=300), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        _timestamp("next_attempt_at", nullable=True, default=False),
        sa.Column("last_status_code", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        _timestamp("created_at"),
        _timestamp("last_attempt_at", nullable=True, default=False),
        _timestamp("delivered_at", nullable=True, default=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SENDING', 'DELIVERED', 'FAILED')",
            name="ck_webhook_deliveries_status",
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_webhook_deliveries_attempts"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "endpoint_id"],
            ["webhook_endpoints.organization_id", "webhook_endpoints.id"],
            name="fk_webhook_deliveries_endpoint_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "id", name="uq_webhook_deliveries_organization_id"
        ),
        sa.UniqueConstraint(
            "organization_id",
            "endpoint_id",
            "event_key",
            name="uq_webhook_deliveries_organization_id_endpoint_id_event_key",
        ),
    )
    op.create_index(
        "ix_webhook_deliveries_organization_id", "webhook_deliveries", ["organization_id"]
    )
    op.create_index(
        "ix_webhook_deliveries_status_next_attempt_at",
        "webhook_deliveries",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        "ix_webhook_deliveries_organization_id_endpoint_id_created_at",
        "webhook_deliveries",
        ["organization_id", "endpoint_id", "created_at"],
    )

    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.drop_constraint("ck_activity_events_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_activity_events_entity_type", f"entity_type IN ({_ENTITY_TYPES_AFTER})"
        )


def downgrade() -> None:
    op.execute("DELETE FROM activity_events WHERE entity_type = 'WEBHOOK_ENDPOINT'")
    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.drop_constraint("ck_activity_events_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_activity_events_entity_type", f"entity_type IN ({_ENTITY_TYPES_BEFORE})"
        )
    op.drop_table("webhook_deliveries")
    op.drop_table("webhook_endpoints")
