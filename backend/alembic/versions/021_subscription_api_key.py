"""Add API key and webhook URL to subscriptions

Revision ID: 021
Revises: 020
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("subscriptions", sa.Column("api_key", sa.String(64), nullable=True, unique=True))
    op.add_column("subscriptions", sa.Column("webhook_url", sa.String(500), nullable=True))
    op.create_index("ix_subscriptions_api_key", "subscriptions", ["api_key"], unique=True)


def downgrade():
    op.drop_index("ix_subscriptions_api_key", table_name="subscriptions")
    op.drop_column("subscriptions", "webhook_url")
    op.drop_column("subscriptions", "api_key")
