"""Store daily forecast snapshots for forecast accuracy.

Revision ID: 038_forecast_snapshots
Revises: 036_deal_forecast_category
Create Date: 2026-10-30

Revises 036 directly. Revision 037 is reserved for the 4C contract step (backfill open
forecast_category NULLs, clear closed rows, add the open-only CHECK), which waits until
the 4C release is serving in production. That step does not depend on these tables;
when it ships it revises this one, so the chain keeps a single head and the files no
longer apply in number order.

Adds two new tables and changes no existing table or row:
- forecast_snapshots: what PipelineService.forecast() returned for an organization on
  one UTC day. Unique per (organization_id, snapshot_date, granularity), so a repeated
  capture on the same day cannot add a second snapshot.
- forecast_snapshot_periods: one row per forecast period. A composite foreign key to
  (forecast_snapshots.organization_id, forecast_snapshots.id) keeps every period in
  its snapshot's organization.

Money is stored as whole cents (BIGINT): the forecast sums integer cents, and a sum over
many deals can exceed the Numeric(14, 2) deal amount range.

Downgrade drops both tables and every snapshot in them.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "038_forecast_snapshots"
down_revision: str | None = "036_deal_forecast_category"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_GRANULARITIES = "'month', 'quarter'"
_TARGET_STATUSES = "'FULL', 'PARTIAL', 'NONE'"


def upgrade() -> None:
    op.create_table(
        "forecast_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("granularity", sa.String(length=16), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("method", sa.String(length=64), nullable=False),
        sa.Column("rounding", sa.String(length=64), nullable=False),
        sa.Column("horizon_start", sa.Date(), nullable=False),
        sa.Column("horizon_end", sa.Date(), nullable=False),
        sa.Column("period_count", sa.Integer(), nullable=False),
        sa.Column("stage_probabilities", sa.JSON(), nullable=False),
        sa.Column("past_due_count", sa.Integer(), nullable=False),
        sa.Column("past_due_cents", sa.BigInteger(), nullable=False),
        sa.Column("past_due_weighted_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            f"granularity IN ({_GRANULARITIES})", name="ck_forecast_snapshots_granularity"
        ),
        sa.CheckConstraint(
            "length(currency) = 3 AND upper(currency) = currency",
            name="ck_forecast_snapshots_currency",
        ),
        sa.CheckConstraint(
            "horizon_end >= horizon_start", name="ck_forecast_snapshots_horizon_order"
        ),
        sa.CheckConstraint("period_count >= 1", name="ck_forecast_snapshots_period_count"),
        sa.CheckConstraint(
            "past_due_count >= 0 AND past_due_cents >= 0 AND past_due_weighted_cents >= 0",
            name="ck_forecast_snapshots_past_due_non_negative",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_forecast_snapshots_organization_id"),
        sa.UniqueConstraint(
            "organization_id",
            "snapshot_date",
            "granularity",
            name="uq_forecast_snapshots_organization_date_granularity",
        ),
    )

    op.create_table(
        "forecast_snapshot_periods",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_id", sa.String(length=36), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("won_count", sa.Integer(), nullable=False),
        sa.Column("won_cents", sa.BigInteger(), nullable=False),
        sa.Column("open_count", sa.Integer(), nullable=False),
        sa.Column("open_cents", sa.BigInteger(), nullable=False),
        sa.Column("open_weighted_cents", sa.BigInteger(), nullable=False),
        sa.Column("projected_cents", sa.BigInteger(), nullable=False),
        sa.Column("commit_scenario_cents", sa.BigInteger(), nullable=False),
        sa.Column("best_case_scenario_cents", sa.BigInteger(), nullable=False),
        sa.Column("target_status", sa.String(length=8), nullable=False),
        sa.Column("target_cents", sa.BigInteger(), nullable=True),
        sa.CheckConstraint(
            "period_end >= period_start", name="ck_forecast_snapshot_periods_period_order"
        ),
        sa.CheckConstraint(
            "won_count >= 0 AND won_cents >= 0 AND open_count >= 0 AND open_cents >= 0 "
            "AND open_weighted_cents >= 0 AND projected_cents >= 0 "
            "AND commit_scenario_cents >= 0 AND best_case_scenario_cents >= 0",
            name="ck_forecast_snapshot_periods_non_negative",
        ),
        sa.CheckConstraint(
            f"target_status IN ({_TARGET_STATUSES})",
            name="ck_forecast_snapshot_periods_target_status",
        ),
        sa.CheckConstraint(
            "(target_status = 'NONE') = (target_cents IS NULL) "
            "AND (target_cents IS NULL OR target_cents >= 0)",
            name="ck_forecast_snapshot_periods_target_cents",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "snapshot_id"],
            ["forecast_snapshots.organization_id", "forecast_snapshots.id"],
            name="fk_forecast_snapshot_periods_snapshot_organization",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "snapshot_id", "period_start", name="uq_forecast_snapshot_periods_snapshot_period"
        ),
    )
    op.create_index(
        "ix_forecast_snapshot_periods_organization_period",
        "forecast_snapshot_periods",
        ["organization_id", "period_start"],
    )


def downgrade() -> None:
    # Destructive: removes every stored forecast snapshot.
    op.drop_index(
        "ix_forecast_snapshot_periods_organization_period",
        table_name="forecast_snapshot_periods",
    )
    op.drop_table("forecast_snapshot_periods")
    op.drop_table("forecast_snapshots")
