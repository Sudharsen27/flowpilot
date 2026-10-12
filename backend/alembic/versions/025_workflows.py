"""Add workflow rules and their queued runs.

Revision ID: 025_workflows
Revises: 024_knowledge_entries
Create Date: 2026-10-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "025_workflows"
down_revision: str | None = "024_knowledge_entries"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_ENTITY_TYPES_BEFORE = (
    "'LEAD', 'SALES_RUN', 'LEAD_EMAIL_SEND', 'AGENT_EXECUTION', "
    "'LEAD_FOLLOW_UP', 'LEAD_FOLLOW_UP_EXECUTION', "
    "'LEAD_RESPONSE_DRAFT', 'LEAD_QUALIFICATION', 'KNOWLEDGE_ENTRY'"
)
_ENTITY_TYPES_AFTER = f"{_ENTITY_TYPES_BEFORE}, 'WORKFLOW_RULE'"


def _timestamp(name: str, *, nullable: bool = False, default: bool = True) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        server_default=sa.text("CURRENT_TIMESTAMP") if default else None,
        nullable=nullable,
    )


def upgrade() -> None:
    op.create_table(
        "workflow_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("source_filter", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("follow_up_delay_hours", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
        _timestamp("created_at"),
        _timestamp("updated_at"),
        sa.CheckConstraint(
            "trigger IN ('LEAD_CREATED', 'INBOUND_REPLY_RECEIVED', 'HUMAN_ATTENTION_REQUIRED')",
            name="ck_workflow_rules_trigger",
        ),
        sa.CheckConstraint(
            "action IN ('ANALYZE_LEAD', 'DRAFT_RESPONSE', 'CREATE_FOLLOW_UP')",
            name="ck_workflow_rules_action",
        ),
        sa.CheckConstraint(
            "follow_up_delay_hours IS NULL OR "
            "(follow_up_delay_hours >= 1 AND follow_up_delay_hours <= 720)",
            name="ck_workflow_rules_follow_up_delay_hours",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_workflow_rules_revision"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_workflow_rules_organization_id"),
    )
    op.create_index(
        "ix_workflow_rules_organization_id", "workflow_rules", ["organization_id"]
    )
    op.create_index(
        "ix_workflow_rules_organization_id_trigger_enabled",
        "workflow_rules",
        ["organization_id", "trigger", "enabled"],
    )

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=False),
        sa.Column("inbound_email_id", sa.String(length=36), nullable=True),
        sa.Column("trigger_key", sa.String(length=300), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("result_entity_id", sa.String(length=36), nullable=True),
        _timestamp("created_at"),
        _timestamp("started_at", nullable=True, default=False),
        _timestamp("completed_at", nullable=True, default=False),
        sa.CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'SKIPPED', 'FAILED')",
            name="ck_workflow_runs_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "rule_id"],
            ["workflow_rules.organization_id", "workflow_rules.id"],
            name="fk_workflow_runs_rule_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_workflow_runs_lead_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_workflow_runs_organization_id"),
        sa.UniqueConstraint(
            "organization_id",
            "rule_id",
            "trigger_key",
            name="uq_workflow_runs_organization_id_rule_id_trigger_key",
        ),
    )
    op.create_index("ix_workflow_runs_organization_id", "workflow_runs", ["organization_id"])
    op.create_index("ix_workflow_runs_lead_id", "workflow_runs", ["lead_id"])
    op.create_index(
        "ix_workflow_runs_status_created_at", "workflow_runs", ["status", "created_at"]
    )
    op.create_index(
        "ix_workflow_runs_organization_id_rule_id_created_at",
        "workflow_runs",
        ["organization_id", "rule_id", "created_at"],
    )

    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.drop_constraint("ck_activity_events_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_activity_events_entity_type", f"entity_type IN ({_ENTITY_TYPES_AFTER})"
        )


def downgrade() -> None:
    op.execute("DELETE FROM activity_events WHERE entity_type = 'WORKFLOW_RULE'")
    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.drop_constraint("ck_activity_events_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_activity_events_entity_type", f"entity_type IN ({_ENTITY_TYPES_BEFORE})"
        )
    op.drop_table("workflow_runs")
    op.drop_table("workflow_rules")
