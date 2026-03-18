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
    report,
    sample,
    search,
    shop,
    submit,
    webhook,
)

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def _run_scoring_job():
    """APScheduler job: score a batch of unscored leads every 30 minutes."""
    from app.services.ollama_client import is_available
    from app.services.ai_scoring import score_lead_batch

    if not await is_available():
        logger.debug("[scheduler] Ollama not available, skipping scoring run")
        return

    async with AsyncSessionLocal() as db:
        scored = await score_lead_batch(db, batch_size=50)
        if scored > 0:
            logger.info(f"[scheduler] Auto-scored {scored} leads")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(_run_scoring_job, "interval", minutes=30, id="ai_scoring")
    scheduler.start()
    logger.info("[scheduler] APScheduler started — AI scoring runs every 30 minutes")
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


@app.get("/health")
async def health():
    return {"status": "ok"}
