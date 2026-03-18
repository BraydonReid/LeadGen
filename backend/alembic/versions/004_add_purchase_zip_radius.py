"""add zip_code and radius_miles to purchases

Revision ID: 004
Revises: 003
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("purchases", sa.Column("zip_code", sa.String(10), nullable=True))
    op.add_column("purchases", sa.Column("radius_miles", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("purchases", "radius_miles")
    op.drop_column("purchases", "zip_code")
