"""Add UTM tracking to purchases and website_scrape_attempted_at to leads

Revision ID: 011
Revises: 010
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade():
    # UTM attribution on purchases — track which ad/channel drove each sale
    op.add_column("purchases", sa.Column("utm_source", sa.String(100), nullable=True))
    op.add_column("purchases", sa.Column("utm_medium", sa.String(100), nullable=True))
    op.add_column("purchases", sa.Column("utm_campaign", sa.String(200), nullable=True))
    op.add_column("purchases", sa.Column("referrer", sa.String(500), nullable=True))

    # Website scraping — separate attempt tracker so it doesn't collide with Hunter.io
    op.add_column("leads", sa.Column("website_scrape_attempted_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("purchases", "utm_source")
    op.drop_column("purchases", "utm_medium")
    op.drop_column("purchases", "utm_campaign")
    op.drop_column("purchases", "referrer")
    op.drop_column("leads", "website_scrape_attempted_at")
