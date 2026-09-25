"""create stress test results table

Revision ID: 3e8f7a1b2c4d
Revises: 2c63ac596416
Create Date: 2026-09-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '3e8f7a1b2c4d'
down_revision: Union[str, None] = '2c63ac596416'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'stress_test_results',
        sa.Column('portfolio_id', sa.UUID(), nullable=False),
        sa.Column('scenario', sa.String(length=50), nullable=False),
        sa.Column('calculation_date', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('scenario_start_date', sa.Date(), nullable=False),
        sa.Column('scenario_end_date', sa.Date(), nullable=False),
        sa.Column('scenario_description', sa.Text(), nullable=False),
        sa.Column('portfolio_return', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('max_drawdown', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('recovery_days', sa.Integer(), nullable=True),
        sa.Column('benchmark_return', sa.Numeric(precision=12, scale=6), nullable=True),
        sa.Column('holding_impacts', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('sector_impacts', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_stress_test_results_calculation_date'), 'stress_test_results', ['calculation_date'], unique=False)
    op.create_index(op.f('ix_stress_test_results_portfolio_id'), 'stress_test_results', ['portfolio_id'], unique=False)
    op.create_index(op.f('ix_stress_test_results_scenario'), 'stress_test_results', ['scenario'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_stress_test_results_scenario'), table_name='stress_test_results')
    op.drop_index(op.f('ix_stress_test_results_portfolio_id'), table_name='stress_test_results')
    op.drop_index(op.f('ix_stress_test_results_calculation_date'), table_name='stress_test_results')
    op.drop_table('stress_test_results')