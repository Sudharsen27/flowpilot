"""Support Contact and Company Activity Events.

Revision ID: 052_activity_contact_company
Revises: 051_contact_lead_associations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "052_activity_contact_company"
down_revision: str | None = "051_contact_lead_associations"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_ENTITY_TYPES_BEFORE = (
    "'LEAD', 'SALES_RUN', 'LEAD_EMAIL_SEND', 'AGENT_EXECUTION', "
    "'LEAD_FOLLOW_UP', 'LEAD_FOLLOW_UP_EXECUTION', "
    "'LEAD_RESPONSE_DRAFT', 'LEAD_QUALIFICATION', 'KNOWLEDGE_ENTRY', "
    "'WORKFLOW_RULE', 'WEBHOOK_ENDPOINT', 'COMPANY_PROSPECT'"
)
_ENTITY_TYPES_AFTER = f"{_ENTITY_TYPES_BEFORE}, 'CONTACT', 'COMPANY'"


def upgrade() -> None:
    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.drop_constraint("ck_activity_events_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_activity_events_entity_type", f"entity_type IN ({_ENTITY_TYPES_AFTER})"
        )


def downgrade() -> None:
    new_events = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM activity_events WHERE entity_type IN ('CONTACT', 'COMPANY')")
    )
    if new_events:
        raise RuntimeError(
            "Cannot downgrade activity entity support while CONTACT or COMPANY "
            "Activity Events exist; no events were deleted."
        )

    with op.batch_alter_table("activity_events") as batch_op:
        batch_op.drop_constraint("ck_activity_events_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_activity_events_entity_type", f"entity_type IN ({_ENTITY_TYPES_BEFORE})"
        )
