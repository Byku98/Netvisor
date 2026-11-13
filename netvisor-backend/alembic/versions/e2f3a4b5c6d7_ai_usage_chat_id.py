"""ai_usage chat attribution column

Revision ID: e2f3a4b5c6d7
Revises: c5d6e7f8a9b0
Create Date: 2026-11-13 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: str | Sequence[str] | None = 'c5d6e7f8a9b0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Nullable: existing rows keep NULL (no backfill); new /ask calls set it.
    op.add_column('ai_usage', sa.Column('chat_id', sa.String(length=36), nullable=True))
    op.create_index('ix_ai_usage_chat_id', 'ai_usage', ['chat_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_ai_usage_chat_id', table_name='ai_usage')
    op.drop_column('ai_usage', 'chat_id')
