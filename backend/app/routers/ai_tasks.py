"""
Internal AI task endpoints.
These are not exposed to the public — they're used to trigger background jobs
on-demand (e.g., for manual backfilling or testing).
"""
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.database import get_db
from app.models import Lead
from app.services.ollama_client import is_available

logger = logging.getLogger(__name__)
router = APIRouter()

YELP_BUDGET_FILE = Path("/app/history/yelp_budget.json")
YELP_MONTHLY_LIMIT = 5000
YELP_DAILY_LIMIT = 160


@router.post("/internal/score-leads")
async def trigger_scoring(
    batch_size: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Trigger AI scoring for unscored leads. Safe to call repeatedly."""
    if not await is_available():
        return {"error": "Ollama is not available", "scored": 0}

    from app.services.ai_scoring import score_lead_batch
    count = await score_lead_batch(db, batch_size)
    return {"scored": count, "batch_size": batch_size}


@router.get("/internal/status")
async def platform_status(db: AsyncSession = Depends(get_db)):
    """Overall platform health: lead counts, AI scoring progress, Yelp budget."""
    total = (await db.execute(select(func.count()).select_from(Lead))).scalar_one()
    scored = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.conversion_score.isnot(None))
    )).scalar_one()
    with_rating = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.yelp_rating.isnot(None))
    )).scalar_one()
    consumer = (await db.execute(
        select(func.count()).select_from(Lead).where(Lead.lead_type == "consumer")
    )).scalar_one()

    # Yelp budget — read from scraper volume
    yelp = {"status": "no data yet"}
    try:
        if YELP_BUDGET_FILE.exists():
            data = json.loads(YELP_BUDGET_FILE.read_text())
            yelp = {
                "month": data.get("month"),
                "monthly_used": data.get("monthly_used", 0),
                "monthly_remaining": YELP_MONTHLY_LIMIT - data.get("monthly_used", 0),
                "daily_used": data.get("daily_used", 0),
                "daily_remaining": YELP_DAILY_LIMIT - data.get("daily_used", 0),
                "monthly_limit": YELP_MONTHLY_LIMIT,
                "daily_limit": YELP_DAILY_LIMIT,
            }
    except Exception:
        pass

    return {
        "leads": {
            "total": total,
            "ai_scored": scored,
            "ai_scored_pct": round(scored / total * 100, 1) if total else 0,
            "with_yelp_rating": with_rating,
            "consumer_intent": consumer,
        },
        "yelp_budget": yelp,
    }
