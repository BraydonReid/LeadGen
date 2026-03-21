import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import AsyncSessionLocal
from app.routers import (
    ai_search,
    ai_tasks,
    checkout,
    download,
    email_campaigns,
    report,
    sample,
    search,
    seo,
    shop,
    submit,
    webhook,
)

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def _run_scoring_job():
    """APScheduler job: score a batch of unscored leads every 10 minutes."""
    from app.services.ollama_client import is_available
    from app.services.ai_scoring import score_lead_batch

    if not await is_available():
        logger.debug("[scheduler] Ollama not available, skipping scoring run")
        return

    async with AsyncSessionLocal() as db:
        scored = await score_lead_batch(db, batch_size=200)
        if scored > 0:
            logger.info(f"[scheduler] Auto-scored {scored} leads")


async def _run_enrichment_job():
    """APScheduler job: enrich leads with Hunter.io emails every hour."""
    from app.services.email_enrichment import enrich_leads_batch
    async with AsyncSessionLocal() as db:
        found = await enrich_leads_batch(db, batch_size=50)
        if found > 0:
            logger.info(f"[scheduler] Email enrichment found {found} new emails")


async def _run_email_send_job():
    """APScheduler job: send pending campaign emails every 15 minutes."""
    from app.config import settings
    if not settings.resend_api_key:
        return
    from app.routers.email_campaigns import send_pending
    async with AsyncSessionLocal() as db:
        result = await send_pending(db)
        if result.get("sent", 0) > 0:
            logger.info(f"[scheduler] Campaign emails sent: {result['sent']}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(_run_scoring_job, "interval", minutes=10, id="ai_scoring")
    scheduler.add_job(_run_enrichment_job, "interval", hours=1, id="email_enrichment")
    scheduler.add_job(_run_email_send_job, "interval", minutes=15, id="email_campaigns")
    scheduler.start()
    logger.info("[scheduler] APScheduler started — scoring/enrichment/campaigns active")
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="LeadGen API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(shop.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(checkout.router, prefix="/api")
app.include_router(download.router, prefix="/api")
app.include_router(webhook.router, prefix="/api")
app.include_router(submit.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(sample.router, prefix="/api")
app.include_router(ai_search.router, prefix="/api")
app.include_router(ai_tasks.router, prefix="/api")
app.include_router(email_campaigns.router, prefix="/api")
app.include_router(seo.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
