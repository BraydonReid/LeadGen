"""Create industry_demand table for demand-based scraping

Revision ID: 007
Revises: 006
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "industry_demand",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("purchase_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("leads_sold", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revenue_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_updated", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("industry", "state", "city", name="uq_demand_industry_state_city"),
    )
    op.create_index("ix_demand_industry_state", "industry_demand", ["industry", "state"])


def downgrade():
    op.drop_index("ix_demand_industry_state", table_name="industry_demand")
    op.drop_table("industry_demand")
