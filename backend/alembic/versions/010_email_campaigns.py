"""Add email_campaigns and email_sends tables

Revision ID: 010
Revises: 009
Create Date: 2026-03-21
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("industry_filter", sa.String(100), nullable=True),
        sa.Column("state_filter", sa.String(2), nullable=True),
        sa.Column("city_filter", sa.String(100), nullable=True),
        sa.Column("template_subject", sa.String(500), nullable=False),
        sa.Column("template_body_html", sa.Text(), nullable=False),
        sa.Column("from_name", sa.String(100), nullable=False, server_default="LeadGen"),
        sa.Column("from_email", sa.String(255), nullable=False),
        sa.Column("sequence_days", sa.String(50), nullable=False, server_default="0,3,8"),
        sa.Column("emails_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_opened", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_clicked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "email_sends",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), nullable=False, index=True),
        sa.Column("lead_id", sa.Integer(), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("sequence_step", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("next_send_at", sa.DateTime(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("clicked_at", sa.DateTime(), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(), nullable=True),
        sa.Column("unsubscribe_token", sa.String(64), nullable=False, unique=True),
        sa.Column("resend_message_id", sa.String(255), nullable=True),
    )
    op.create_index("ix_email_sends_next_send", "email_sends", ["next_send_at"])
    op.create_table(
        "email_unsubscribes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("unsubscribed_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("email_unsubscribes")
    op.drop_table("email_sends")
    op.drop_table("email_campaigns")
