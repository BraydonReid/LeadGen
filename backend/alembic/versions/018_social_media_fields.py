"""Add social media fields to leads

Revision ID: 018
Revises: 017
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("facebook_url", sa.String(500), nullable=True))
    op.add_column("leads", sa.Column("instagram_url", sa.String(500), nullable=True))
    op.add_column("leads", sa.Column("social_scrape_attempted_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("leads", "social_scrape_attempted_at")
    op.drop_column("leads", "instagram_url")
    op.drop_column("leads", "facebook_url")
