"""Add NPI (healthcare provider) enrichment fields

Revision ID: 019
Revises: 018
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("npi_number", sa.String(20), nullable=True))
    op.add_column("leads", sa.Column("npi_attempted_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("leads", "npi_attempted_at")
    op.drop_column("leads", "npi_number")
