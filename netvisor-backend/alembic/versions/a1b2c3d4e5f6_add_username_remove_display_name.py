"""add_username_remove_display_name

Revision ID: a1b2c3d4e5f6
Revises: 7a9ed7812213
Create Date: 2026-09-10 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '7a9ed7812213'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add username column (nullable first to handle existing rows)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('username', sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)
        batch_op.drop_column('display_name')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(length=128), nullable=False, server_default=''))
        batch_op.drop_index(batch_op.f('ix_users_username'))
        batch_op.drop_column('username')
