"""add lead quality and type fields

Revision ID: 003
Revises: 002
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("zip_code", sa.String(10), nullable=True))
    op.add_column("leads", sa.Column("full_address", sa.String(500), nullable=True))
    op.add_column("leads", sa.Column("contact_name", sa.String(255), nullable=True))
    op.add_column("leads", sa.Column("quality_score", sa.SmallInteger(), nullable=True))
    op.add_column("leads", sa.Column("source", sa.String(50), nullable=True))
    op.add_column(
        "leads",
        sa.Column("lead_type", sa.String(20), nullable=False, server_default="business"),
    )

    # Backfill quality_score for existing rows
    op.execute("""
        UPDATE leads SET quality_score = (
            CASE WHEN phone IS NOT NULL AND phone != '' THEN 30 ELSE 0 END +
            CASE WHEN email IS NOT NULL AND email != '' THEN 25 ELSE 0 END +
            CASE WHEN website IS NOT NULL AND website != '' THEN 20 ELSE 0 END
        )
        WHERE quality_score IS NULL
    """)

    # Backfill source
    op.execute("UPDATE leads SET source = 'yellowpages' WHERE source IS NULL")

    op.create_index("ix_leads_lead_type", "leads", ["lead_type"])
    op.create_index("ix_leads_quality_score", "leads", ["quality_score"])


def downgrade() -> None:
    op.drop_index("ix_leads_quality_score", table_name="leads")
    op.drop_index("ix_leads_lead_type", table_name="leads")
    op.drop_column("leads", "lead_type")
    op.drop_column("leads", "source")
    op.drop_column("leads", "quality_score")
    op.drop_column("leads", "contact_name")
    op.drop_column("leads", "full_address")
    op.drop_column("leads", "zip_code")
