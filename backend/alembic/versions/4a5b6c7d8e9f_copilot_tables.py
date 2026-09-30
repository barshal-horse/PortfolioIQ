"""create copilot tables

Revision ID: 4a5b6c7d8e9f
Revises: 3e8f7a1b2c4d
Create Date: 2026-09-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '4a5b6c7d8e9f'
down_revision: Union[str, None] = '3e8f7a1b2c4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'copilot_sessions',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('portfolio_id', sa.UUID(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('message_count', sa.Integer(), nullable=False, default=0),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_copilot_sessions_user_id'), 'copilot_sessions', ['user_id', 'created_at'], unique=False)

    op.create_table(
        'copilot_messages',
        sa.Column('session_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('agent_name', sa.String(length=100), nullable=True),
        sa.Column('tool_calls', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False, default=[]),
        sa.Column('tool_results', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False, default=[]),
        sa.Column('citations', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False, default=[]),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=False, default=0),
        sa.Column('latency_ms', sa.Integer(), nullable=False, default=0),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['copilot_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_copilot_messages_session_id'), 'copilot_messages', ['session_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_copilot_messages_session_id'), table_name='copilot_messages')
    op.drop_table('copilot_messages')
    op.drop_index(op.f('ix_copilot_sessions_user_id'), table_name='copilot_sessions')
    op.drop_table('copilot_sessions')