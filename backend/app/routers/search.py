from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import SearchResponse
from app.services.leads import search_leads

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
async def search(
    industry: str = Query(..., min_length=1),
    state: str = Query(..., min_length=2, max_length=2),
    city: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    return await search_leads(db, industry, state, city)
