"""add api_key_settings table

Revision ID: 7d8e9f0a1b2c
Revises: 4a4eb302255b
Create Date: 2026-09-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '7d8e9f0a1b2c'
down_revision: Union[str, None] = '4a4eb302255b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'api_key_settings',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('key_enc', sa.Text(), nullable=False),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'provider', name='uq_api_key_user_provider'),
    )
    op.create_index(op.f('ix_api_key_settings_user_id'), 'api_key_settings', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_api_key_settings_user_id'), table_name='api_key_settings')
    op.drop_table('api_key_settings')
