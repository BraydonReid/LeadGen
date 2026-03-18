"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-12
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("business_name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("source_url", sa.String(500), nullable=True, unique=True),
        sa.Column("scraped_date", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_leads_industry_state", "leads", ["industry", "state"])
    op.create_index("ix_leads_industry_state_city", "leads", ["industry", "state", "city"])

    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stripe_session_id", sa.String(255), nullable=False, unique=True),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("fulfilled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_purchases_stripe_session_id", "purchases", ["stripe_session_id"])


def downgrade() -> None:
    op.drop_table("purchases")
    op.drop_table("leads")
