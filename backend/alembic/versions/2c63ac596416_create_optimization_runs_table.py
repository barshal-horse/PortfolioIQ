"""create optimization runs table

Revision ID: 2c63ac596416
Revises: d7d491041870
Create Date: 2026-09-24 19:40:32.013793
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '2c63ac596416'
down_revision: Union[str, None] = 'd7d491041870'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'optimization_runs',
        sa.Column('portfolio_id', sa.UUID(), nullable=False),
        sa.Column('method', sa.String(length=50), nullable=False),
        sa.Column('calculation_date', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('constraints', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('current_weights', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('optimal_weights', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('expected_return', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('expected_volatility', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('expected_sharpe', sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column('current_metrics', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('trades', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('efficient_frontier', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('views', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('posterior_returns', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_optimization_runs_calculation_date'), 'optimization_runs', ['calculation_date'], unique=False)
    op.create_index(op.f('ix_optimization_runs_method'), 'optimization_runs', ['method'], unique=False)
    op.create_index(op.f('ix_optimization_runs_portfolio_id'), 'optimization_runs', ['portfolio_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_optimization_runs_portfolio_id'), table_name='optimization_runs')
    op.drop_index(op.f('ix_optimization_runs_method'), table_name='optimization_runs')
    op.drop_index(op.f('ix_optimization_runs_calculation_date'), table_name='optimization_runs')
    op.drop_table('optimization_runs')
