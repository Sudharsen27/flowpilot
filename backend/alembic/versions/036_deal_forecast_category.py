"""Add forecast categories to deals and record them in deal history.

Revision ID: 036_deal_forecast_category
Revises: 035_deal_history_probability
Create Date: 2026-10-30

Adds to deals:
- forecast_category (PIPELINE, BEST_CASE, COMMIT): the seller's confidence in an open
  deal, independent of stage and probability. Every existing open deal is backfilled to
  PIPELINE, the default for new deals; closed deals stay NULL because "Closed" is
  derived from the stage. A CHECK limits the column to those three values.

Expand step of an expand-and-contract change. The release before this revision keeps
serving while it runs (pre-deploy migration), and it neither sets nor clears the
column: it creates open deals with NULL and closes deals without clearing it. So the
"open deals have a category, closed deals have none" rule is NOT enforced here; the
application reads the column through effective_forecast_category() and repairs a row
whenever it writes it. A later migration, run only after this release is serving,
backfills open NULLs to PIPELINE, clears closed rows and adds that CHECK.

Adds to deal_stage_events:
- previous_forecast_category / new_forecast_category. Rows written before this revision
  never recorded a category, so both stay NULL; nothing is backfilled because the
  historical value is unknown. Two CHECKs: allowed values, and no category on a closed
  side of an event. The previous release writes NULL to both columns, so neither can
  block it.

No index is added: category is filtered together with the organization's existing
indexed columns, and forecast queries already scan an organization's open deals.

Only deals.forecast_category is written by the backfill; no history row is rewritten.
Downgrade drops the new columns and loses the recorded categories.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "036_deal_forecast_category"
down_revision: str | None = "035_deal_history_probability"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CLOSED = "'CLOSED_WON', 'CLOSED_LOST'"
_CATEGORIES = "'PIPELINE', 'BEST_CASE', 'COMMIT'"


def upgrade() -> None:
    with op.batch_alter_table("deals") as batch_op:
        batch_op.add_column(sa.Column("forecast_category", sa.String(length=16), nullable=True))
    op.execute(f"UPDATE deals SET forecast_category = 'PIPELINE' WHERE stage NOT IN ({_CLOSED})")
    with op.batch_alter_table("deals") as batch_op:
        batch_op.create_check_constraint(
            "ck_deals_forecast_category",
            f"forecast_category IS NULL OR forecast_category IN ({_CATEGORIES})",
        )

    with op.batch_alter_table("deal_stage_events") as batch_op:
        batch_op.add_column(
            sa.Column("previous_forecast_category", sa.String(length=16), nullable=True)
        )
        batch_op.add_column(sa.Column("new_forecast_category", sa.String(length=16), nullable=True))
        batch_op.create_check_constraint(
            "ck_deal_stage_events_forecast_category",
            f"(previous_forecast_category IS NULL OR previous_forecast_category IN "
            f"({_CATEGORIES})) AND (new_forecast_category IS NULL OR "
            f"new_forecast_category IN ({_CATEGORIES}))",
        )
        batch_op.create_check_constraint(
            "ck_deal_stage_events_forecast_category_open_only",
            f"(new_forecast_category IS NULL OR new_stage NOT IN ({_CLOSED})) "
            f"AND (previous_forecast_category IS NULL OR previous_stage NOT IN ({_CLOSED}))",
        )


def downgrade() -> None:
    with op.batch_alter_table("deal_stage_events") as batch_op:
        batch_op.drop_constraint("ck_deal_stage_events_forecast_category_open_only", type_="check")
        batch_op.drop_constraint("ck_deal_stage_events_forecast_category", type_="check")
        batch_op.drop_column("new_forecast_category")
        batch_op.drop_column("previous_forecast_category")
    with op.batch_alter_table("deals") as batch_op:
        batch_op.drop_constraint("ck_deals_forecast_category", type_="check")
        batch_op.drop_column("forecast_category")
