"""Add COMPANY_PROSPECT entity type to activity events.

Revision ID: 033_company_prospect_activity
Revises: 032_company_prospects
Create Date: 2026-10-26

"""

from collections.abc import Sequence

from alembic import op

revision: str = "033_company_prospect_activity"
down_revision: str | None = "032_company_prospects"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_ENTITY_TYPES_BEFORE = (
    "'LEAD', 'SALES_RUN', 'LEAD_EMAIL_SEND', 'AGENT_EXECUTION', "
    "'LEAD_FOLLOW_UP', 'LEAD_FOLLOW_UP_EXECUTION', "
    "'LEAD_RESPONSE_DRAFT', 'LEAD_QUALIFICATION', 'KNOWLEDGE_ENTRY', "
    "'WORKFLOW_RULE', 'WEBHOOK_ENDPOINT'"
)

_ENTITY_TYPES_AFTER = f"{_ENTITY_TYPES_BEFORE}, 'COMPANY_PROSPECT'"


def upgrade() -> None:
    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.drop_constraint("ck_activity_events_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_activity_events_entity_type", f"entity_type IN ({_ENTITY_TYPES_AFTER})"
        )


def downgrade() -> None:
    op.execute("DELETE FROM activity_events WHERE entity_type = 'COMPANY_PROSPECT'")
    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.drop_constraint("ck_activity_events_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_activity_events_entity_type", f"entity_type IN ({_ENTITY_TYPES_BEFORE})"
        )
