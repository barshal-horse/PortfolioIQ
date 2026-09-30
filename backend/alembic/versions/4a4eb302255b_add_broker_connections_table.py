"""add broker_connections table

Revision ID: 4a4eb302255b
Revises: 6c7d8e9f0a1b
Create Date: 2026-09-30 21:04:23.618640

Minimal migration: creates only the new broker_connections table.
(Autogenerate detected drift from a legacy create_all database; that drift
is intentionally NOT migrated here.)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '4a4eb302255b'
down_revision: Union[str, None] = '6c7d8e9f0a1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'broker_connections',
        sa.Column('broker', sa.String(length=30), nullable=False, server_default='alpaca'),
        sa.Column('api_key_enc', sa.Text(), nullable=False),
        sa.Column('api_secret_enc', sa.Text(), nullable=False),
        sa.Column('account_id', sa.String(length=64), nullable=True),
        sa.Column('account_status', sa.String(length=30), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False, server_default='{}'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_broker_connections_user_id'), 'broker_connections', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_broker_connections_user_id'), table_name='broker_connections')
    op.drop_table('broker_connections')
