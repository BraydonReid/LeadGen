"""Add Nominatim address enrichment attempt tracker

Revision ID: 017
Revises: 016
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("nominatim_attempted_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("leads", "nominatim_attempted_at")
