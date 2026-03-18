"""Add AI conversion scoring columns to leads table

Revision ID: 006
Revises: 005
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("conversion_score", sa.SmallInteger(), nullable=True))
    op.add_column("leads", sa.Column("website_quality_signal", sa.SmallInteger(), nullable=True))
    op.add_column("leads", sa.Column("contact_richness_signal", sa.SmallInteger(), nullable=True))
    op.add_column("leads", sa.Column("ai_scored_at", sa.DateTime(), nullable=True))
    op.create_index("ix_leads_conversion_score", "leads", ["conversion_score"])


def downgrade():
    op.drop_index("ix_leads_conversion_score", table_name="leads")
    op.drop_column("leads", "ai_scored_at")
    op.drop_column("leads", "contact_richness_signal")
    op.drop_column("leads", "website_quality_signal")
    op.drop_column("leads", "conversion_score")
