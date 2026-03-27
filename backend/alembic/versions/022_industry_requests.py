"""Add industry_requests demand waitlist table

Revision ID: 022
Revises: 021
Create Date: 2026-03-27
"""
from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "industry_requests",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("email", sa.String(255), nullable=False, index=True),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("notified_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("email", "industry", "state", name="uq_industry_request_email_industry_state"),
    )


def downgrade():
    op.drop_table("industry_requests")
