"""Add email nurture sequence fields to sample_requests

Revision ID: 025
Revises: 024
Create Date: 2026-03-27

Tracks which nurture emails have been sent to each free-sample requester.
Sequence: Day 0 (immediate, handled by sample router) → Day 2 → Day 5 → Day 9 → Day 14
"""
from alembic import op
import sqlalchemy as sa

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sample_requests", sa.Column("nurture_stage", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("sample_requests", sa.Column("nurture_last_sent_at", sa.DateTime(), nullable=True))
    op.add_column("sample_requests", sa.Column("nurture_unsubscribed", sa.Boolean(), nullable=False, server_default="false"))


def downgrade():
    op.drop_column("sample_requests", "nurture_unsubscribed")
    op.drop_column("sample_requests", "nurture_last_sent_at")
    op.drop_column("sample_requests", "nurture_stage")
