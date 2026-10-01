"""add file_checksum for deduplication.

Revision ID: c4d5e6f7a8b9
Revises: 2817dbafedb9
Create Date: 2026-09-20 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = '2817dbafedb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add file_checksum column for PCAP deduplication."""
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('file_checksum', sa.String(length=64), nullable=True))
        batch_op.create_index(batch_op.f('ix_sessions_file_checksum'), ['file_checksum'], unique=False)


def downgrade() -> None:
    """Remove file_checksum column."""
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sessions_file_checksum'))
        batch_op.drop_column('file_checksum')