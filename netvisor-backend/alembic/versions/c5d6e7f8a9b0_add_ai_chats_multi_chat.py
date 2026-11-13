"""add ai_chats table (multiple chats per session)

Revision ID: c5d6e7f8a9b0
Revises: a9b8c7d6e5f4
Create Date: 2026-11-13 00:00:00.000000

"""
import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: str | Sequence[str] | None = 'a9b8c7d6e5f4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ai_chats',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_ai_chats_user_session_created',
        'ai_chats',
        ['user_id', 'session_id', 'created_at'],
    )

    # 1) Add chat_id (nullable for the backfill window).
    with op.batch_alter_table('ai_chat_messages') as batch:
        batch.add_column(sa.Column('chat_id', sa.String(length=36), nullable=True))
        batch.create_foreign_key(
            'fk_ai_chat_messages_chat_id', 'ai_chats', ['chat_id'], ['id'],
            ondelete='CASCADE',
        )

    # 2) Backfill: one ai_chats row per distinct (user_id, session_id) that
    #    already has messages; title = first user message's first 50 chars.
    conn = op.get_bind()
    groups = conn.execute(sa.text(
        'SELECT user_id, session_id, MIN(created_at) AS first_created '
        'FROM ai_chat_messages GROUP BY user_id, session_id'
    )).fetchall()
    for user_id, session_id, first_created in groups:
        title_row = conn.execute(sa.text(
            "SELECT content FROM ai_chat_messages "
            "WHERE user_id = :u AND session_id = :s AND role = 'user' "
            "ORDER BY created_at ASC, id ASC LIMIT 1"
        ), {"u": user_id, "s": session_id}).first()
        title = title_row[0][:50] if title_row else None
        chat_id = str(uuid.uuid4())
        conn.execute(sa.text(
            'INSERT INTO ai_chats (id, user_id, session_id, title, created_at) '
            'VALUES (:id, :u, :s, :t, :ts)'
        ), {"id": chat_id, "u": user_id, "s": session_id, "t": title, "ts": first_created})
        conn.execute(sa.text(
            'UPDATE ai_chat_messages SET chat_id = :c '
            'WHERE user_id = :u AND session_id = :s'
        ), {"c": chat_id, "u": user_id, "s": session_id})

    # 3) Enforce NOT NULL now that every message points at a chat.
    with op.batch_alter_table('ai_chat_messages') as batch:
        batch.alter_column(
            'chat_id', existing_type=sa.String(length=36), nullable=False
        )
    op.create_index('ix_ai_chat_messages_chat_id', 'ai_chat_messages', ['chat_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_ai_chat_messages_chat_id', table_name='ai_chat_messages')
    with op.batch_alter_table('ai_chat_messages') as batch:
        batch.drop_column('chat_id')
    op.drop_index('ix_ai_chats_user_session_created', table_name='ai_chats')
    op.drop_table('ai_chats')
