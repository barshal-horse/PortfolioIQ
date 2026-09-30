"""create news tables

Revision ID: 5b6c7d8e9f0a
Revises: 4a5b6c7d8e9f
Create Date: 2026-09-26 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '5b6c7d8e9f0a'
down_revision: Union[str, None] = '4a5b6c7d8e9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'news_articles',
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('related_tickers', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False, default=[]),
        sa.Column('raw_data', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False, default={}),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id', 'source', name='uq_news_external_id_source'),
    )
    op.create_index(op.f('ix_news_articles_published_at'), 'news_articles', ['published_at'], unique=False)
    op.create_index(op.f('ix_news_articles_source'), 'news_articles', ['source'], unique=False)
    op.create_index('ix_news_articles_tickers', 'news_articles', ['related_tickers'], unique=False, postgresql_using='gin')

    op.create_table(
        'sentiment_scores',
        sa.Column('article_id', sa.UUID(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=True),
        sa.Column('sentiment', sa.String(length=20), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('impact_score', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('analysis', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(length=100), nullable=False, default='gemini'),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['article_id'], ['news_articles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sentiment_scores_article_id'), 'sentiment_scores', ['article_id'], unique=False)
    op.create_index(op.f('ix_sentiment_scores_ticker'), 'sentiment_scores', ['ticker'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_sentiment_scores_ticker'), table_name='sentiment_scores')
    op.drop_index(op.f('ix_sentiment_scores_article_id'), table_name='sentiment_scores')
    op.drop_table('sentiment_scores')
    op.drop_index('ix_news_articles_tickers', table_name='news_articles', postgresql_using='gin')
    op.drop_index(op.f('ix_news_articles_source'), table_name='news_articles')
    op.drop_index(op.f('ix_news_articles_published_at'), table_name='news_articles')
    op.drop_table('news_articles')