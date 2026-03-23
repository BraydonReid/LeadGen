"""Data quality fields, magic link auth, credit rollover, referral program

Revision ID: 013
Revises: 012
Create Date: 2026-03-22
"""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade():
    # Lead data quality columns
    op.add_column("leads", sa.Column("phone_valid", sa.Boolean(), nullable=True))
    op.add_column("leads", sa.Column("duplicate_of_id", sa.Integer(), nullable=True))
    op.add_column("leads", sa.Column("website_status", sa.String(10), nullable=True))

    # Subscription growth columns
    op.add_column("subscriptions", sa.Column("rollover_credits", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("subscriptions", sa.Column("referral_code", sa.String(10), nullable=True))
    op.add_column("subscriptions", sa.Column("referred_by_code", sa.String(10), nullable=True))
    op.create_index("ix_subscriptions_referral_code", "subscriptions", ["referral_code"], unique=True)

    # Magic link auth
    op.create_table(
        "subscription_magic_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_subscription_magic_links_token", "subscription_magic_links", ["token"])

    # Session tokens
    op.create_table(
        "subscription_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_subscription_sessions_token", "subscription_sessions", ["token"])
    op.create_index("ix_subscription_sessions_email", "subscription_sessions", ["email"])

    # Subscriber lifecycle email tracking
    op.create_table(
        "subscriber_emails_sent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("email_type", sa.String(50), nullable=False),
        sa.Column("sent_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("email", "email_type", name="uq_subscriber_email_type"),
    )
    op.create_index("ix_subscriber_emails_sent_email", "subscriber_emails_sent", ["email"])


def downgrade():
    op.drop_table("subscriber_emails_sent")
    op.drop_table("subscription_sessions")
    op.drop_table("subscription_magic_links")
    op.drop_index("ix_subscriptions_referral_code", "subscriptions")
    op.drop_column("subscriptions", "referred_by_code")
    op.drop_column("subscriptions", "referral_code")
    op.drop_column("subscriptions", "rollover_credits")
    op.drop_column("leads", "website_status")
    op.drop_column("leads", "duplicate_of_id")
    op.drop_column("leads", "phone_valid")
