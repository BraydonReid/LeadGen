"""add pricing fields

Revision ID: 002
Revises: 001
Create Date: 2026-03-13
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("times_sold", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("purchases", sa.Column("avg_lead_price_cents", sa.Integer(), nullable=True))
    op.add_column("purchases", sa.Column("discount_pct", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "times_sold")
    op.drop_column("purchases", "avg_lead_price_cents")
    op.drop_column("purchases", "discount_pct")
