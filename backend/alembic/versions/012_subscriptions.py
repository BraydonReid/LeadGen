"""Add subscriptions and subscription_downloads tables

Revision ID: 012
Revises: 011
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stripe_subscription_id", sa.String(255), unique=True, nullable=False),
        sa.Column("stripe_customer_id", sa.String(255), nullable=False),
        sa.Column("buyer_email", sa.String(255), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("plan", sa.String(20), nullable=False, server_default="pro"),
        sa.Column("leads_per_month", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("credits_remaining", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "subscription_downloads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), nullable=False, index=True),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("downloaded_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("subscription_downloads")
    op.drop_table("subscriptions")
