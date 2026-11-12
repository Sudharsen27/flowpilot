"""Order deal history, qualifications, and attention episodes without timestamps.

Revision ID: 044_chronological_order
Revises: 043_auth_password_reset_events
Create Date: 2026-11-12

deal_stage_events.revision stores the deal revision at the time the row was
written. Existing rows are numbered per deal by created_at, then id.
lead_qualifications.sequence is the same kind of per-lead insertion number.
leads.human_attention_event_id points at the open episode's escalation event.
Clear leads stay null. No foreign key or index is added for that column.

Each required integer is added nullable, backfilled, then constrained. That
sequence works on PostgreSQL and SQLite. Downgrade drops the constraints and
columns. Historical ordering numbers and stored episode ids are lost.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "044_chronological_order"
down_revision: str | None = "043_auth_password_reset_events"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    _add_numbered_column(
        table="deal_stage_events",
        column="revision",
        check_name="ck_deal_stage_events_revision_positive",
        unique_name="uq_deal_stage_events_organization_deal_revision",
        unique_columns=["organization_id", "deal_id", "revision"],
        partition="organization_id, deal_id",
    )
    _add_numbered_column(
        table="lead_qualifications",
        column="sequence",
        check_name="ck_lead_qualifications_sequence_positive",
        unique_name="uq_lead_qualifications_organization_lead_sequence",
        unique_columns=["organization_id", "lead_id", "sequence"],
        partition="organization_id, lead_id",
    )
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(
            sa.Column("human_attention_event_id", sa.String(length=36), nullable=True)
        )
    op.execute(
        """
        UPDATE leads
        SET human_attention_event_id = (
            SELECT activity_events.id
            FROM activity_events
            WHERE activity_events.organization_id = leads.organization_id
              AND activity_events.lead_id = leads.id
              AND activity_events.dedupe_key LIKE
                  ('lead:' || leads.id || ':human_attention:qualification:%')
            ORDER BY activity_events.occurred_at DESC, activity_events.id DESC
            LIMIT 1
        )
        WHERE human_attention_required
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_column("human_attention_event_id")
    _drop_numbered_column(
        table="lead_qualifications",
        column="sequence",
        check_name="ck_lead_qualifications_sequence_positive",
        unique_name="uq_lead_qualifications_organization_lead_sequence",
    )
    _drop_numbered_column(
        table="deal_stage_events",
        column="revision",
        check_name="ck_deal_stage_events_revision_positive",
        unique_name="uq_deal_stage_events_organization_deal_revision",
    )


def _add_numbered_column(
    *,
    table: str,
    column: str,
    check_name: str,
    unique_name: str,
    unique_columns: list[str],
    partition: str,
) -> None:
    with op.batch_alter_table(table) as batch_op:
        batch_op.add_column(sa.Column(column, sa.Integer(), nullable=True))
    op.execute(
        f"""
        UPDATE {table}
        SET {column} = (
            SELECT numbered.seq_num
            FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY {partition}
                        ORDER BY created_at, id
                    ) AS seq_num
                FROM {table}
            ) AS numbered
            WHERE numbered.id = {table}.id
        )
        """
    )
    with op.batch_alter_table(table) as batch_op:
        batch_op.alter_column(column, existing_type=sa.Integer(), nullable=False)
        batch_op.create_check_constraint(check_name, f"{column} >= 1")
        batch_op.create_unique_constraint(unique_name, unique_columns)


def _drop_numbered_column(
    *,
    table: str,
    column: str,
    check_name: str,
    unique_name: str,
) -> None:
    with op.batch_alter_table(table) as batch_op:
        batch_op.drop_constraint(unique_name, type_="unique")
        batch_op.drop_constraint(check_name, type_="check")
        batch_op.drop_column(column)
