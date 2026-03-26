"""Add WHOIS and DuckDuckGo search enrichment attempt trackers

Revision ID: 015
Revises: 014
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("whois_attempted_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("ddg_search_attempted_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("leads", "ddg_search_attempted_at")
    op.drop_column("leads", "whois_attempted_at")
