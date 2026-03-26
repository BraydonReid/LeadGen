"""Reset AI scores for leads with Yelp rating or years_in_business so they
get re-scored using the enhanced prompt that includes reputation data.

Revision ID: 016
Revises: 015
Create Date: 2026-03-26
"""
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade():
    # Re-score leads that have enrichment data the old prompt didn't use.
    # The scoring job will pick these up within minutes of deploy.
    op.execute("""
        UPDATE leads
        SET ai_scored_at = NULL,
            conversion_score = NULL
        WHERE (yelp_rating IS NOT NULL OR years_in_business IS NOT NULL)
          AND ai_scored_at IS NOT NULL
    """)


def downgrade():
    pass  # Cannot un-score leads
