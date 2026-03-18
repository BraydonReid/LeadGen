"""Add reputation signals: yelp_rating, review_count, years_in_business

Revision ID: 008
Revises: 007
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("yelp_rating", sa.Float(), nullable=True))
    op.add_column("leads", sa.Column("review_count", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("years_in_business", sa.SmallInteger(), nullable=True))


def downgrade():
    op.drop_column("leads", "years_in_business")
    op.drop_column("leads", "review_count")
    op.drop_column("leads", "yelp_rating")
