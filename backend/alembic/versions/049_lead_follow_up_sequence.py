"""Expand follow-ups with a nullable per-lead creation sequence.

Existing rows are numbered by created_at and id. For timestamp ties, this
provides a deterministic backfill only; their true insertion order cannot be
recovered.

Revision ID: 049_lead_follow_up_sequence
Revises: 048_company_contact_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "049_lead_follow_up_sequence"
down_revision: str | None = "048_company_contact_foundation"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_LEGACY_SEQUENCE_FUNCTION = "flowpilot_assign_lead_follow_up_sequence"
_LEGACY_SEQUENCE_TRIGGER = "trg_lead_follow_ups_assign_legacy_sequence"


def upgrade() -> None:
    with op.batch_alter_table("lead_follow_ups") as batch_op:
        batch_op.add_column(sa.Column("sequence", sa.Integer(), nullable=True))
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
                        ORDER BY created_at, id
                    ) AS seq_num
                FROM lead_follow_ups
            ) AS numbered
            WHERE numbered.id = lead_follow_ups.id
        )
        """
    )
    with op.batch_alter_table("lead_follow_ups") as batch_op:
        batch_op.create_check_constraint(
            "ck_lead_follow_ups_sequence_positive", "sequence >= 1"
        )
        batch_op.create_unique_constraint(
            "uq_lead_follow_ups_organization_lead_sequence",
            ["organization_id", "lead_id", "sequence"],
        )
    if op.get_bind().dialect.name == "postgresql":
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


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            f"DROP TRIGGER IF EXISTS {_LEGACY_SEQUENCE_TRIGGER} ON lead_follow_ups"
        )
        op.execute(f"DROP FUNCTION IF EXISTS {_LEGACY_SEQUENCE_FUNCTION}()")
    with op.batch_alter_table("lead_follow_ups") as batch_op:
        batch_op.drop_constraint(
            "uq_lead_follow_ups_organization_lead_sequence", type_="unique"
        )
        batch_op.drop_constraint("ck_lead_follow_ups_sequence_positive", type_="check")
        batch_op.drop_column("sequence")
