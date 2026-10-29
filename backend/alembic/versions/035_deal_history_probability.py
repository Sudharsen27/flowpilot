"""Record probability overrides and won-amount corrections in deal history.

Revision ID: 035_deal_history_probability
Revises: 034_deal_foundation
Create Date: 2026-10-29

Adds to deal_stage_events:
- previous_probability / new_probability: the deal's probability *override* before and
  after the event (NULL = stage default). Rows written before this revision were never
  told the override, so both columns stay NULL for them; nothing is backfilled because
  the historical value is unknown.
- is_correction (NOT NULL, server default false): marks a manager's amount correction
  on a CLOSED_WON deal. A CHECK keeps it to won -> won rows that carry a reason.

Adds deals index (organization_id, closed_at) for won-revenue period queries.

No existing row is rewritten. Downgrade drops the new columns and index; it loses the
recorded probability history and correction flags (the amount changes themselves stay).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "035_deal_history_probability"
down_revision: str | None = "034_deal_foundation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CLOSED = "'CLOSED_WON', 'CLOSED_LOST'"


def upgrade() -> None:
    with op.batch_alter_table("deal_stage_events") as batch_op:
        batch_op.add_column(sa.Column("previous_probability", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("new_probability", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "is_correction",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.create_check_constraint(
            "ck_deal_stage_events_probability_range",
            "(previous_probability IS NULL OR previous_probability BETWEEN 0 AND 100) "
            "AND (new_probability IS NULL OR new_probability BETWEEN 0 AND 100)",
        )
        batch_op.create_check_constraint(
            "ck_deal_stage_events_probability_open_only",
            f"(new_probability IS NULL OR new_stage NOT IN ({_CLOSED})) "
            f"AND (previous_probability IS NULL OR previous_stage NOT IN ({_CLOSED}))",
        )
        batch_op.create_check_constraint(
            "ck_deal_stage_events_correction_won_only",
            "NOT is_correction OR (previous_stage = 'CLOSED_WON' "
            "AND new_stage = 'CLOSED_WON' AND change_reason IS NOT NULL)",
        )
    op.create_index(
        "ix_deals_organization_closed_at",
        "deals",
        ["organization_id", "closed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_deals_organization_closed_at", table_name="deals")
    with op.batch_alter_table("deal_stage_events") as batch_op:
        batch_op.drop_constraint("ck_deal_stage_events_correction_won_only", type_="check")
        batch_op.drop_constraint("ck_deal_stage_events_probability_open_only", type_="check")
        batch_op.drop_constraint("ck_deal_stage_events_probability_range", type_="check")
        batch_op.drop_column("is_correction")
        batch_op.drop_column("new_probability")
        batch_op.drop_column("previous_probability")
