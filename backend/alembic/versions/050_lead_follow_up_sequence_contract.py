"""Backfill rollout-era follow-ups and require their per-lead sequence.

Revision ID: 050_follow_up_sequence
Revises: 049_lead_follow_up_sequence
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "050_follow_up_sequence"
down_revision: str | None = "049_lead_follow_up_sequence"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_SEQUENCE_CONSTRAINT = "uq_lead_follow_ups_organization_lead_sequence"
_LEGACY_SEQUENCE_FUNCTION = "flowpilot_assign_lead_follow_up_sequence"
_LEGACY_SEQUENCE_TRIGGER = "trg_lead_follow_ups_assign_legacy_sequence"


def _create_legacy_sequence_trigger() -> None:
    op.execute(
        f"""
        CREATE FUNCTION {_LEGACY_SEQUENCE_FUNCTION}() RETURNS trigger AS $$
        DECLARE
            next_sequence INTEGER;
        BEGIN
            IF NEW.sequence IS NULL THEN
                PERFORM 1
                FROM leads
                WHERE organization_id = NEW.organization_id
                  AND id = NEW.lead_id
                FOR UPDATE;

                SELECT COALESCE(MAX(sequence), 0) + 1
                INTO next_sequence
                FROM lead_follow_ups
                WHERE organization_id = NEW.organization_id
                  AND lead_id = NEW.lead_id;

                NEW.sequence := next_sequence;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {_LEGACY_SEQUENCE_TRIGGER}
        BEFORE INSERT ON lead_follow_ups
        FOR EACH ROW
        EXECUTE FUNCTION {_LEGACY_SEQUENCE_FUNCTION}()
        """
    )


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("LOCK TABLE lead_follow_ups IN ACCESS EXCLUSIVE MODE")
        op.execute(
            f"DROP TRIGGER IF EXISTS {_LEGACY_SEQUENCE_TRIGGER} ON lead_follow_ups"
        )
        op.execute(f"DROP FUNCTION IF EXISTS {_LEGACY_SEQUENCE_FUNCTION}()")

    with op.batch_alter_table("lead_follow_ups") as batch_op:
        batch_op.drop_constraint(_SEQUENCE_CONSTRAINT, type_="unique")

    op.execute(
        """
        UPDATE lead_follow_ups
        SET sequence = (
            SELECT numbered.seq_num
            FROM (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY organization_id, lead_id
                        ORDER BY
                            created_at,
                            CASE WHEN sequence IS NULL THEN 0 ELSE 1 END,
                            sequence,
                            id
                    ) AS seq_num
                FROM lead_follow_ups
            ) AS numbered
            WHERE numbered.id = lead_follow_ups.id
        )
        """
    )

    with op.batch_alter_table("lead_follow_ups") as batch_op:
        batch_op.alter_column("sequence", existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint(
            _SEQUENCE_CONSTRAINT,
            ["organization_id", "lead_id", "sequence"],
        )


def downgrade() -> None:
    with op.batch_alter_table("lead_follow_ups") as batch_op:
        batch_op.alter_column("sequence", existing_type=sa.Integer(), nullable=True)
    if op.get_bind().dialect.name == "postgresql":
        op.execute("LOCK TABLE lead_follow_ups IN ACCESS EXCLUSIVE MODE")
        _create_legacy_sequence_trigger()
