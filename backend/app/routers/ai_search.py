"""
AI natural language search endpoint.
POST /api/search/ai — accepts free-text queries, returns structured lead results.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import AISearchRequest, AISearchResponse
from app.services.ai_search import ai_search
from app.services.openai_client import is_available

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/search/ai", response_model=AISearchResponse)
async def ai_search_endpoint(body: AISearchRequest, db: AsyncSession = Depends(get_db)):
    """
    Parse a natural language query and return matching leads.

    If Ollama is unavailable, returns 503 so the frontend can fall back
    to standard search without breaking the purchase flow.
    """
    if not await is_available():
        raise HTTPException(
            status_code=503,
            detail="AI search temporarily unavailable — use standard search",
        )

    try:
        return await ai_search(db, body.query, body.max_results)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Could not parse query: {e}")
    except Exception as e:
        logger.error(f"[ai_search] Unexpected error: {e}")
        raise HTTPException(
            status_code=503,
            detail="AI search temporarily unavailable — use standard search",
        )
