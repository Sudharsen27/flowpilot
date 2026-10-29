"""Create the deal, deal history and sales target foundation.

Revision ID: 034_deal_foundation
Revises: 033_company_prospect_activity
Create Date: 2026-10-29

Adds organizations.default_currency (NOT NULL, server default 'INR', so existing
rows are filled without a data rewrite step) and three new tables.

Downgrade is destructive: it drops deals, deal_stage_events and sales_targets with
all their rows, and organizations.default_currency. Take a backup first.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "034_deal_foundation"
down_revision: str | None = "033_company_prospect_activity"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_STAGES = (
    "'QUALIFICATION', 'DISCOVERY', 'PROPOSAL', 'NEGOTIATION', 'CLOSED_WON', 'CLOSED_LOST'"
)
_CLOSED = "'CLOSED_WON', 'CLOSED_LOST'"


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "default_currency",
                sa.String(length=3),
                nullable=False,
                server_default="INR",
            )
        )
        batch_op.create_check_constraint(
            "ck_organizations_default_currency",
            "length(default_currency) = 3 AND upper(default_currency) = default_currency",
        )

    op.create_table(
        "deals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("lead_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=4000), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("probability", sa.Integer(), nullable=True),
        sa.Column("expected_close_date", sa.Date(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("lost_reason", sa.String(length=1000), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("stage_entered_at", sa.DateTime(timezone=True), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(f"stage IN ({_STAGES})", name="ck_deals_stage"),
        sa.CheckConstraint("amount >= 0", name="ck_deals_amount_non_negative"),
        sa.CheckConstraint(
            "length(currency) = 3 AND upper(currency) = currency",
            name="ck_deals_currency",
        ),
        sa.CheckConstraint(
            "probability IS NULL OR (probability >= 0 AND probability <= 100)",
            name="ck_deals_probability_range",
        ),
        sa.CheckConstraint(
            f"probability IS NULL OR stage NOT IN ({_CLOSED})",
            name="ck_deals_probability_open_only",
        ),
        sa.CheckConstraint(
            f"(stage IN ({_CLOSED})) = (closed_at IS NOT NULL)",
            name="ck_deals_closed_at_matches_stage",
        ),
        sa.CheckConstraint(
            "lost_reason IS NULL OR stage = 'CLOSED_LOST'",
            name="ck_deals_lost_reason_lost_only",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_deals_revision_positive"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            name="fk_deals_lead_organization",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "owner_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_deals_owner_membership",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id", name="uq_deals_organization_id"),
    )
    op.create_index("ix_deals_organization_stage", "deals", ["organization_id", "stage"])
    op.create_index(
        "ix_deals_organization_expected_close_date",
        "deals",
        ["organization_id", "expected_close_date"],
    )
    op.create_index("ix_deals_organization_owner", "deals", ["organization_id", "owner_user_id"])
    op.create_index("ix_deals_organization_lead", "deals", ["organization_id", "lead_id"])
    op.create_index(
        "ix_deals_organization_created_at_id",
        "deals",
        ["organization_id", "created_at", "id"],
    )

    op.create_table(
        "deal_stage_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("deal_id", sa.String(length=36), nullable=False),
        sa.Column("previous_stage", sa.String(length=32), nullable=True),
        sa.Column("new_stage", sa.String(length=32), nullable=False),
        sa.Column("previous_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("new_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("previous_expected_close_date", sa.Date(), nullable=True),
        sa.Column("new_expected_close_date", sa.Date(), nullable=False),
        sa.Column("changed_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("change_reason", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(f"new_stage IN ({_STAGES})", name="ck_deal_stage_events_new_stage"),
        sa.CheckConstraint(
            f"previous_stage IS NULL OR previous_stage IN ({_STAGES})",
            name="ck_deal_stage_events_previous_stage",
        ),
        sa.CheckConstraint(
            "new_amount >= 0 AND (previous_amount IS NULL OR previous_amount >= 0)",
            name="ck_deal_stage_events_amount_non_negative",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "deal_id"],
            ["deals.organization_id", "deals.id"],
            name="fk_deal_stage_events_deal_organization",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_deal_stage_events_organization_deal_created_at",
        "deal_stage_events",
        ["organization_id", "deal_id", "created_at", "id"],
    )
    op.create_index(
        "ix_deal_stage_events_organization_created_at",
        "deal_stage_events",
        ["organization_id", "created_at"],
    )

    op.create_table(
        "sales_targets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("amount >= 0", name="ck_sales_targets_amount_non_negative"),
        sa.CheckConstraint(
            "length(currency) = 3 AND upper(currency) = currency",
            name="ck_sales_targets_currency",
        ),
        sa.CheckConstraint("period_end > period_start", name="ck_sales_targets_period_order"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organization_id", "owner_user_id"],
            ["memberships.organization_id", "memberships.user_id"],
            name="fk_sales_targets_owner_membership",
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_sales_targets_organization_period",
        "sales_targets",
        ["organization_id", "period_start"],
        unique=True,
        postgresql_where=sa.text("owner_user_id IS NULL"),
        sqlite_where=sa.text("owner_user_id IS NULL"),
    )
    op.create_index(
        "uq_sales_targets_organization_owner_period",
        "sales_targets",
        ["organization_id", "owner_user_id", "period_start"],
        unique=True,
        postgresql_where=sa.text("owner_user_id IS NOT NULL"),
        sqlite_where=sa.text("owner_user_id IS NOT NULL"),
    )
    op.create_index(
        "ix_sales_targets_organization_period",
        "sales_targets",
        ["organization_id", "period_start"],
    )


def downgrade() -> None:
    # Destructive: removes every deal, deal history event and sales target.
    op.drop_index("ix_sales_targets_organization_period", table_name="sales_targets")
    op.drop_index("uq_sales_targets_organization_owner_period", table_name="sales_targets")
    op.drop_index("uq_sales_targets_organization_period", table_name="sales_targets")
    op.drop_table("sales_targets")
    op.drop_index(
        "ix_deal_stage_events_organization_created_at", table_name="deal_stage_events"
    )
    op.drop_index(
        "ix_deal_stage_events_organization_deal_created_at", table_name="deal_stage_events"
    )
    op.drop_table("deal_stage_events")
    op.drop_index("ix_deals_organization_created_at_id", table_name="deals")
    op.drop_index("ix_deals_organization_lead", table_name="deals")
    op.drop_index("ix_deals_organization_owner", table_name="deals")
    op.drop_index("ix_deals_organization_expected_close_date", table_name="deals")
    op.drop_index("ix_deals_organization_stage", table_name="deals")
    op.drop_table("deals")
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.drop_constraint("ck_organizations_default_currency", type_="check")
        batch_op.drop_column("default_currency")
