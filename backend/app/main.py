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
    orders,
    report,
    sample,
    search,
    seo,
    shop,
    submit,
    subscriptions,
    webhook,
)

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def _run_scoring_job():
    """APScheduler job: score a batch of unscored leads every 10 minutes."""
    from app.services.openai_client import is_available
    from app.services.ai_scoring import score_lead_batch

    if not await is_available():
        logger.debug("[scheduler] OpenAI not configured, skipping scoring run")
        return

    async with AsyncSessionLocal() as db:
        scored = await score_lead_batch(db, batch_size=200)
        if scored > 0:
            logger.info(f"[scheduler] Auto-scored {scored} leads")


async def _run_enrichment_job():
    """APScheduler job: enrich leads with Hunter.io emails once per day."""
    from app.services.email_enrichment import enrich_leads_batch
    async with AsyncSessionLocal() as db:
        # Free tier = 25 searches/month. Run 1/day to spread budget across the month.
        found = await enrich_leads_batch(db, batch_size=1)
        if found > 0:
            logger.info(f"[scheduler] Email enrichment found {found} new emails")


async def _run_website_scrape_job():
    """APScheduler job: scrape emails directly from lead websites every 20 minutes."""
    from app.services.website_scraper import scrape_email_batch
    async with AsyncSessionLocal() as db:
        found = await scrape_email_batch(db, batch_size=200)
        if found > 0:
            logger.info(f"[scheduler] Website scraper found {found} new emails")


async def _run_phone_clean_job():
    """APScheduler job: clean + normalize phone numbers every 30 minutes."""
    from app.services.phone_cleaner import clean_phones_batch
    async with AsyncSessionLocal() as db:
        result = await clean_phones_batch(db, batch_size=2000)
        if result["processed"] > 0:
            logger.info(f"[scheduler] Phone cleaning: {result['valid']} valid, {result['invalid']} invalid")


async def _run_dedup_job():
    """APScheduler job: deduplicate leads once per day."""
    from app.services.deduplication import run_dedup_pass
    async with AsyncSessionLocal() as db:
        result = await run_dedup_pass(db, batch_size=500)
        if result["marked_this_run"] > 0:
            logger.info(f"[scheduler] Dedup: marked {result['marked_this_run']} duplicates")


async def _run_subscriber_email_job():
    """APScheduler job: send subscriber lifecycle emails every hour."""
    from app.services.subscriber_mailer import run_subscriber_email_job
    async with AsyncSessionLocal() as db:
        result = await run_subscriber_email_job(db)
        total = sum(result.values()) if isinstance(result, dict) else 0
        if total > 0:
            logger.info(f"[scheduler] Subscriber emails: {result}")


async def _run_contact_scrape_job():
    """APScheduler job: extract contact names/titles from About pages every 30 minutes."""
    from app.services.contact_scraper import scrape_contact_batch
    async with AsyncSessionLocal() as db:
        found = await scrape_contact_batch(db, batch_size=100)
        if found > 0:
            logger.info(f"[scheduler] Contact scraper found {found} new contacts")


async def _run_smtp_discovery_job():
    """APScheduler job: SMTP email pattern discovery every hour."""
    from app.services.smtp_email_discovery import smtp_discovery_batch
    async with AsyncSessionLocal() as db:
        found = await smtp_discovery_batch(db, batch_size=30)
        if found > 0:
            logger.info(f"[scheduler] SMTP discovery found {found} new emails")


async def _run_linkedin_builder_job():
    """APScheduler job: build LinkedIn URLs for leads that don't have one (runs until caught up)."""
    from app.services.linkedin_builder import build_linkedin_batch
    async with AsyncSessionLocal() as db:
        updated = await build_linkedin_batch(db, batch_size=1000)
        if updated > 0:
            logger.info(f"[scheduler] LinkedIn builder updated {updated} leads")


async def _run_texas_sos_job():
    """APScheduler job: enrich TX leads with registered agent names every 2 hours."""
    from app.services.texas_sos_enricher import enrich_texas_contacts_batch
    async with AsyncSessionLocal() as db:
        found = await enrich_texas_contacts_batch(db, batch_size=20)
        if found > 0:
            logger.info(f"[scheduler] Texas SOS enriched {found} contacts")


async def _run_email_send_job():
    """APScheduler job: send pending campaign emails every 15 minutes."""
    from app.config import settings
    if not settings.smtp_password:
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
    scheduler.add_job(_run_website_scrape_job, "interval", minutes=20, id="website_scraper")
    # Email campaigns disabled — enable when ready to launch outbound emails
    # scheduler.add_job(_run_email_send_job, "interval", minutes=15, id="email_campaigns")
    scheduler.add_job(_run_phone_clean_job, "interval", minutes=30, id="phone_cleaner")
    scheduler.add_job(_run_dedup_job, "interval", hours=24, id="deduplication")
    scheduler.add_job(_run_subscriber_email_job, "interval", hours=1, id="subscriber_emails")
    # Decision-maker enrichment pipeline
    scheduler.add_job(_run_contact_scrape_job, "interval", minutes=30, id="contact_scraper")
    scheduler.add_job(_run_smtp_discovery_job, "interval", hours=1, id="smtp_discovery")
    scheduler.add_job(_run_linkedin_builder_job, "interval", minutes=15, id="linkedin_builder")
    scheduler.add_job(_run_texas_sos_job, "interval", hours=2, id="texas_sos")
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
app.include_router(orders.router, prefix="/api")
app.include_router(subscriptions.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok"}
