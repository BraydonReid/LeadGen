"""
Standalone AI scoring expedite script — uses local Ollama (no rate limits).
Run: python expedite_scoring.py
"""
import asyncio
import json
import logging
import time

import httpx
import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DB_CONN = dict(
    host="localhost", port=5432,
    dbname="leadgen", user="leadgen",
    password="LeadGen_Secure_2026!"
)
OLLAMA_URL   = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"
CONCURRENCY  = 6
BATCH_SIZE   = 60

SCORING_PROMPT = """\
You are a lead quality analyst for a B2B lead generation company.

Score this business lead for CONVERSION LIKELIHOOD (probability that a sales rep \
will get a qualified conversation or sale). Score 0-100.

Lead:
- Business: {business_name}
- Industry: {industry}
- Location: {city}, {state}
- Has Phone: {has_phone}
- Has Email: {has_email}
- Has Website: {has_website}
- Has Street Address: {has_address}
- Has Named Contact: {has_contact}
- Website: {website}

Scoring:
85-100: Multiple contacts, named person, established web presence, high-value industry
65-84: Good contact data, appears active, reachable
45-64: Partial data, reachable but extra effort needed
25-44: Minimal data, cold outreach difficult
0-24: Very limited data, likely outdated

Respond ONLY with valid JSON, nothing else:
{{"conversion_score": <0-100>, "website_quality": <0-100>, "contact_richness": <0-100>, "reasoning": "<one sentence>"}}"""

sem = asyncio.Semaphore(CONCURRENCY)


def db_get_batch():
    conn = psycopg2.connect(**DB_CONN)
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT id, business_name, industry, city, state,
                   phone, email, website, full_address, contact_name
            FROM leads WHERE ai_scored_at IS NULL
            ORDER BY scraped_date DESC NULLS LAST
            LIMIT %s
        """, (BATCH_SIZE,))
        rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def db_count_unscored():
    conn = psycopg2.connect(**DB_CONN)
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM leads WHERE ai_scored_at IS NULL")
        count = cur.fetchone()[0]
    conn.close()
    return count


def db_save_batch(results):
    conn = psycopg2.connect(**DB_CONN)
    with conn.cursor() as cur:
        for r in results:
            cur.execute("""
                UPDATE leads
                SET conversion_score=%s, website_quality_signal=%s,
                    contact_richness_signal=%s, ai_scored_at=NOW()
                WHERE id=%s
            """, (r["conversion_score"], r["website_quality_signal"],
                  r["contact_richness_signal"], r["id"]))
    conn.commit()
    conn.close()


async def score_one(lead: dict, client: httpx.AsyncClient) -> dict:
    prompt = SCORING_PROMPT.format(
        business_name=lead["business_name"],
        industry=lead["industry"] or "Unknown",
        city=lead["city"] or "Unknown",
        state=lead["state"] or "Unknown",
        has_phone="Yes" if lead["phone"] else "No",
        has_email="Yes" if lead["email"] else "No",
        has_website="Yes" if lead["website"] else "No",
        has_address="Yes" if lead["full_address"] else "No",
        has_contact="Yes" if lead["contact_name"] else "No",
        website=lead["website"] or "None",
    )
    async with sem:
        try:
            resp = await client.post(
                OLLAMA_URL,
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                timeout=90.0,
            )
            resp.raise_for_status()
            raw = resp.json().get("response", "")
            s, e = raw.find("{"), raw.rfind("}") + 1
            if s == -1:
                raise ValueError(f"No JSON: {raw[:80]}")
            data = json.loads(raw[s:e])
            return {
                "id": lead["id"],
                "conversion_score":        min(100, max(0, int(data["conversion_score"]))),
                "website_quality_signal":  min(100, max(0, int(data.get("website_quality", 50)))),
                "contact_richness_signal": min(100, max(0, int(data.get("contact_richness", 50)))),
            }
        except Exception as ex:
            log.warning(f"Lead {lead['id']} failed: {ex}")
            return {"id": lead["id"], "conversion_score": 50,
                    "website_quality_signal": 50, "contact_richness_signal": 50}


async def main():
    # Verify Ollama
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get("http://127.0.0.1:11434/api/tags", timeout=5)
            models = [m["name"] for m in r.json().get("models", [])]
            if not any("llama3.1" in m for m in models):
                log.error(f"llama3.1:8b not found. Run: ollama pull llama3.1:8b")
                return
            log.info(f"Ollama ready | models: {models}")
        except Exception as e:
            log.error(f"Cannot reach Ollama: {e}")
            return

    # Verify DB
    try:
        total = await asyncio.to_thread(db_count_unscored)
        log.info(f"Unscored leads: {total:,} | model: {OLLAMA_MODEL} | concurrency: {CONCURRENCY}")
    except Exception as e:
        log.error(f"Cannot connect to DB at localhost:5432 — is Docker running? {e}")
        return

    scored = 0
    start = time.time()

    async with httpx.AsyncClient() as client:
        while True:
            leads = await asyncio.to_thread(db_get_batch)
            if not leads:
                break

            results = await asyncio.gather(*[score_one(l, client) for l in leads])
            await asyncio.to_thread(db_save_batch, results)

            scored += len(results)
            elapsed = time.time() - start
            rate = scored / elapsed * 60
            eta = (total - scored) / rate if rate > 0 else 0
            log.info(f"Scored {scored:,}/{total:,} ({scored/total*100:.1f}%) | {rate:.0f}/min | ETA {eta:.0f}min")

    log.info(f"Done! {scored:,} leads scored in {(time.time()-start)/60:.1f} min")


if __name__ == "__main__":
    asyncio.run(main())
