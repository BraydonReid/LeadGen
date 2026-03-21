"""Add email enrichment tracking fields to leads

Revision ID: 009
Revises: 008
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("email_source", sa.String(20), nullable=True))
    op.add_column("leads", sa.Column("email_found_at", sa.DateTime(), nullable=True))
    op.add_column("leads", sa.Column("enrichment_attempted_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("leads", "enrichment_attempted_at")
    op.drop_column("leads", "email_found_at")
    op.drop_column("leads", "email_source")
