"""smart_hybrid_schema — remove Node/Edge/Packet tables, add cookie/session fields.

Revision ID: 2817dbafedb9
Revises: a1b2c3d4e5f6
Create Date: 2026-09-15 19:53:41.074292

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2817dbafedb9'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — Smart Hybrid architecture."""
    # Drop old tables (nodes, edges, packets no longer needed)
    op.drop_table('edges')
    op.drop_table('nodes')
    with op.batch_alter_table('packets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('idx_packets_session_dst'))
        batch_op.drop_index(batch_op.f('idx_packets_session_src'))
        batch_op.drop_index(batch_op.f('idx_packets_session_ts'))

    op.drop_table('packets')

    # Add new columns to sessions table
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cookie_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('topology_json_path', sa.Text(), nullable=False, server_default=''))
        batch_op.create_index(batch_op.f('ix_sessions_cookie_id'), ['cookie_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema — restore packet tables."""
    # Remove new columns from sessions
    with op.batch_alter_table('sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sessions_cookie_id'))
        batch_op.drop_column('topology_json_path')
        batch_op.drop_column('expires_at')
        batch_op.drop_column('cookie_id')

    # Recreate packets table
    op.create_table('packets',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('session_id', sa.VARCHAR(length=36), nullable=False),
        sa.Column('packet_index', sa.INTEGER(), nullable=False),
        sa.Column('timestamp', sa.FLOAT(), nullable=False),
        sa.Column('src_ip', sa.TEXT(), nullable=False),
        sa.Column('dst_ip', sa.TEXT(), nullable=False),
        sa.Column('src_port', sa.INTEGER(), nullable=True),
        sa.Column('dst_port', sa.INTEGER(), nullable=True),
        sa.Column('protocol', sa.TEXT(), nullable=False),
        sa.Column('length', sa.INTEGER(), nullable=False),
        sa.Column('info', sa.TEXT(), nullable=False),
        sa.Column('headers', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('packets', schema=None) as batch_op:
        batch_op.create_index('idx_packets_session_ts', ['session_id', 'timestamp'], unique=False)
        batch_op.create_index('idx_packets_session_src', ['session_id', 'src_ip'], unique=False)
        batch_op.create_index('idx_packets_session_dst', ['session_id', 'dst_ip'], unique=False)

    # Recreate nodes table
    op.create_table('nodes',
        sa.Column('id', sa.VARCHAR(length=36), nullable=False),
        sa.Column('session_id', sa.VARCHAR(length=36), nullable=False),
        sa.Column('ip_address', sa.TEXT(), nullable=False),
        sa.Column('label', sa.TEXT(), nullable=False),
        sa.Column('type', sa.TEXT(), nullable=False),
        sa.Column('total_packets', sa.INTEGER(), nullable=False),
        sa.Column('total_bytes', sa.INTEGER(), nullable=False),
        sa.Column('protocols', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Recreate edges table
    op.create_table('edges',
        sa.Column('id', sa.VARCHAR(length=36), nullable=False),
        sa.Column('session_id', sa.VARCHAR(length=36), nullable=False),
        sa.Column('source_ip', sa.TEXT(), nullable=False),
        sa.Column('target_ip', sa.TEXT(), nullable=False),
        sa.Column('total_packets', sa.INTEGER(), nullable=False),
        sa.Column('total_bytes', sa.INTEGER(), nullable=False),
        sa.Column('protocols', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )