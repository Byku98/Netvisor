"""ai_usage cost/model columns + user_llm_keys price columns

Revision ID: f1a2b3c4d5e6
Revises: d8e9f0a1b2c3
Create Date: 2026-11-13 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: str | Sequence[str] | None = 'd8e9f0a1b2c3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('ai_usage', sa.Column('model', sa.Text(), nullable=True))
    op.add_column(
        'ai_usage',
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'ai_usage',
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column('ai_usage', sa.Column('cost_usd', sa.Float(), nullable=True))
    op.add_column('user_llm_keys', sa.Column('price_in', sa.Float(), nullable=True))
    op.add_column('user_llm_keys', sa.Column('price_out', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_llm_keys', 'price_out')
    op.drop_column('user_llm_keys', 'price_in')
    op.drop_column('ai_usage', 'cost_usd')
    op.drop_column('ai_usage', 'completion_tokens')
    op.drop_column('ai_usage', 'prompt_tokens')
    op.drop_column('ai_usage', 'model')
