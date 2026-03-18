"""add buyer_email to purchases, lead_credits and sample_requests tables

Revision ID: 005
Revises: 004
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("purchases", sa.Column("buyer_email", sa.String(255), nullable=True))

    op.create_table(
        "lead_credits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(20), nullable=False, unique=True),
        sa.Column("discount_cents", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(255), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_lead_credits_code", "lead_credits", ["code"])
    op.create_index("ix_lead_credits_session_id", "lead_credits", ["session_id"])

    op.create_table(
        "sample_requests",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("email", "industry", "state", name="uq_sample_email_industry_state"),
    )


def downgrade():
    op.drop_table("sample_requests")
    op.drop_index("ix_lead_credits_session_id", "lead_credits")
    op.drop_index("ix_lead_credits_code", "lead_credits")
    op.drop_table("lead_credits")
    op.drop_column("purchases", "buyer_email")
