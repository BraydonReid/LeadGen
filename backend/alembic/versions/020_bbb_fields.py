"""Add BBB rating and accreditation fields

Revision ID: 020
Revises: 019
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("leads", sa.Column("bbb_rating", sa.String(5), nullable=True))
    op.add_column("leads", sa.Column("bbb_accredited", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("leads", "bbb_accredited")
    op.drop_column("leads", "bbb_rating")
