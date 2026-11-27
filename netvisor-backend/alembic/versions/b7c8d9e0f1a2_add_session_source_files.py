"""sessions.source_files JSON column (multi-PCAP upload)

Revision ID: b7c8d9e0f1a2
Revises: e2f3a4b5c6d7
Create Date: 2026-11-27 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: str | Sequence[str] | None = 'e2f3a4b5c6d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable: legacy single-file rows keep NULL (no backfill needed —
    # a single-file upload's source list is just its own filename).
    op.add_column('sessions', sa.Column('source_files', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sessions', 'source_files')
