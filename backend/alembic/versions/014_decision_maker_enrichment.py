"""Add decision-maker enrichment fields: contact_title, linkedin_url, attempt trackers

Revision ID: 014
Revises: 013
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("contact_title", sa.String(100), nullable=True))
    op.add_column("leads", sa.Column("linkedin_url", sa.String(500), nullable=True))
    op.add_column("leads", sa.Column("contact_scrape_attempted_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("smtp_discovery_attempted_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("texas_sos_attempted_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("leads", "texas_sos_attempted_at")
    op.drop_column("leads", "smtp_discovery_attempted_at")
    op.drop_column("leads", "contact_scrape_attempted_at")
    op.drop_column("leads", "linkedin_url")
    op.drop_column("leads", "contact_title")
