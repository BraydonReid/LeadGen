"""Consumer service request submission — creates intent leads from homeowner form."""
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Lead
from app.schemas import ServiceRequestCreate, ServiceRequestResponse

router = APIRouter()

VALID_TIMELINES = {"asap", "1_3_months", "3_6_months", "planning"}
VALID_PROPERTY_TYPES = {"residential", "commercial"}


def _normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def _quality_score(req: ServiceRequestCreate, phone: str | None) -> int:
    score = 0
    if phone:
        score += 30
    if req.email:
        score += 25
    # No website for consumer leads — skip that +20
    if req.zip_code:
        score += 15
    if req.full_name:
        score += 10
    return min(100, score)


@router.post("/leads/submit", response_model=ServiceRequestResponse)
async def submit_service_request(
    body: ServiceRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    if body.timeline not in VALID_TIMELINES:
        raise HTTPException(status_code=422, detail="Invalid timeline value")
    if body.property_type not in VALID_PROPERTY_TYPES:
        raise HTTPException(status_code=422, detail="Invalid property_type value")

    phone = _normalize_phone(body.phone)
    if not phone:
        raise HTTPException(status_code=422, detail="Invalid phone number — must be a 10-digit US number")

    industry = body.service_needed.lower().strip()

    # Duplicate check: same email + industry already submitted
    dup_stmt = select(func.count()).select_from(Lead).where(
        func.lower(Lead.email) == body.email.lower().strip(),
        Lead.industry == industry,
        Lead.lead_type == "consumer",
    )
    if (await db.execute(dup_stmt)).scalar_one() > 0:
        return ServiceRequestResponse(
            success=True,
            message="Your request is already on file. Local contractors will be in touch soon!",
        )

    full_address = f"{body.city.strip()}, {body.state.strip().upper()} {body.zip_code.strip()}"
    quality = _quality_score(body, phone)

    lead = Lead(
        business_name=body.full_name.strip(),
        industry=industry,
        city=body.city.strip(),
        state=body.state.strip().upper(),
        email=body.email.strip().lower(),
        phone=phone,
        source_url=None,
        zip_code=body.zip_code.strip(),
        full_address=full_address,
        contact_name=body.full_name.strip(),
        quality_score=quality,
        source="consumer_form",
        lead_type="consumer",
        times_sold=0,
    )
    db.add(lead)
    await db.commit()

    return ServiceRequestResponse(
        success=True,
        message="Your request has been submitted. Local contractors will be in touch soon!",
    )
