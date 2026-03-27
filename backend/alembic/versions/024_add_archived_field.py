"""Add archived field to leads for 1-year retention cycle

Revision ID: 024
Revises: 023
Create Date: 2026-03-27

Leads not re-scraped within 365 days get soft-archived (hidden from customers
but preserved in the DB). When the annual re-scrape cycle finds the business
still active, dedup.py refreshes scraped_date and archived resets to False.
"""
from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "leads",
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_leads_archived", "leads", ["archived"])


def downgrade():
    op.drop_index("ix_leads_archived", table_name="leads")
    op.drop_column("leads", "archived")
