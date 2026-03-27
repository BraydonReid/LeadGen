"""Add email_verified flag to leads

Revision ID: 023
Revises: 022
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("email_verified", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("leads", "email_verified")
