"""Growth P2 MVP columns: embed origins, chat capture, knowledge embeddings.

Revision ID: 047_growth_p2_mvps
Revises: 046_organization_invitations
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "047_growth_p2_mvps"
down_revision: str | None = "046_organization_invitations"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("website_embed_allowed_origins", sa.Text(), nullable=True),
    )
    op.add_column(
        "organizations",
        sa.Column(
            "chat_capture_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "knowledge_entries",
        sa.Column("embedding_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_entries", "embedding_json")
    op.drop_column("organizations", "chat_capture_enabled")
    op.drop_column("organizations", "website_embed_allowed_origins")
