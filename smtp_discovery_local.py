"""
Local SMTP email discovery — run this weekly on your Windows machine.

Connects directly to the production DB, finds emails via SMTP pattern
verification (no email ever sent), and writes results back.

Requirements:
    pip install psycopg2-binary dnspython httpx

Usage:
    python smtp_discovery_local.py
"""
import asyncio
import random
import smtplib
import string
import time
from urllib.parse import urlparse

import dns.resolver
import psycopg2
import psycopg2.extras

# ── Production DB ────────────────────────────────────────────────────────────
DB = dict(
    host="46.62.131.115",
    port=5432,
    dbname="leadgen",
    user="leadgen",
    password="LeadGen_Secure_2026!",
)

BATCH_SIZE   = 5000  # leads per run
CONCURRENCY  = 8     # simultaneous SMTP checks

EHLO_DOMAIN  = "takeyourleadtoday.com"
SENDER       = f"verify@{EHLO_DOMAIN}"
GENERIC      = ["info", "contact", "hello", "office", "sales", "service", "admin"]

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_domain(website: str) -> str | None:
    try:
        netloc = urlparse(website).netloc.lower().replace("www.", "")
        return netloc if "." in netloc else None
    except Exception:
        return None


def get_mx(domain: str) -> str | None:
    try:
        records = dns.resolver.resolve(domain, "MX", lifetime=5)
        return str(sorted(records, key=lambda r: r.preference)[0].exchange).rstrip(".")
    except Exception:
        return None


def smtp_rcpt(email: str, mx: str) -> bool:
    try:
        with smtplib.SMTP(timeout=8) as s:
            s.connect(mx, 25)
            s.helo(EHLO_DOMAIN)
            s.mail(SENDER)
            code, _ = s.rcpt(email)
            return code == 250
    except Exception:
        return False


def is_catchall(mx: str, domain: str) -> bool:
    rand = "".join(random.choices(string.ascii_lowercase, k=18))
    return smtp_rcpt(f"{rand}@{domain}", mx)


# Domains shared across many franchise locations — same email on every lead, not useful
_CHAIN_DOMAINS = {
    "banfield.com", "supercuts.com", "kidsdentalonline.com", "petfolk.com",
    "bettervet.com", "blomedry.com", "housedoctors.com", "planetbeach.com",
    "angi.com", "homeadvisor.com", "thumbtack.com", "yelp.com",
    "yellowpages.com", "bbb.org", "angieslist.com",
}

def is_chain_domain(domain: str) -> bool:
    return domain in _CHAIN_DOMAINS


def name_patterns(contact_name: str, domain: str) -> list[str]:
    parts = contact_name.strip().split()
    if len(parts) < 2:
        return []
    f, l = parts[0].lower(), parts[-1].lower()
    return [
        f"{f}@{domain}",
        f"{f}.{l}@{domain}",
        f"{f}{l}@{domain}",
        f"{f[0]}{l}@{domain}",
        f"{f[0]}.{l}@{domain}",
    ]


def discover_email(website: str, contact_name: str | None) -> str | None:
    domain = get_domain(website)
    if not domain:
        return None

    if is_chain_domain(domain):
        return None  # skip — corporate chain, same email across all locations

    mx = get_mx(domain)
    if not mx:
        return None

    if is_catchall(mx, domain):
        return None  # skip — would accept anything, can't trust results

    candidates: list[str] = []
    if contact_name:
        candidates.extend(name_patterns(contact_name, domain))
    candidates.extend(f"{loc}@{domain}" for loc in GENERIC)

    # Deduplicate while keeping order
    seen: set[str] = set()
    unique = [c for c in candidates if not (c in seen or seen.add(c))]  # type: ignore

    for email in unique:
        if smtp_rcpt(email, mx):
            return email
    return None

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    conn = psycopg2.connect(**DB)
    cur  = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    # Count unprocessed
    cur.execute("""
        SELECT COUNT(*) FROM leads
        WHERE website IS NOT NULL
          AND website_status = 'ok'
          AND email IS NULL
          AND smtp_discovery_attempted_at IS NULL
    """)
    total = cur.fetchone()[0]
    print(f"Leads needing SMTP discovery: {total:,}")
    print(f"Processing batch of {BATCH_SIZE} this run\n")

    cur.execute("""
        SELECT id, website, contact_name
        FROM leads
        WHERE website IS NOT NULL
          AND website_status = 'ok'
          AND email IS NULL
          AND smtp_discovery_attempted_at IS NULL
        ORDER BY conversion_score DESC NULLS LAST, quality_score DESC NULLS LAST
        LIMIT %s
    """, (BATCH_SIZE,))
    leads = cur.fetchall()

    if not leads:
        print("Nothing to process.")
        conn.close()
        return

    found = 0
    now_str = "NOW()"

    for i, lead in enumerate(leads, 1):
        lid, website, contact_name = lead["id"], lead["website"], lead["contact_name"]
        try:
            email = discover_email(website, contact_name)
        except Exception as e:
            email = None
            print(f"  [{i}/{len(leads)}] ERROR {website}: {e}")

        for attempt in range(3):
            try:
                if email:
                    cur.execute("""
                        UPDATE leads
                        SET email = %s,
                            email_source = 'smtp_discovery',
                            email_found_at = NOW(),
                            smtp_discovery_attempted_at = NOW(),
                            ai_scored_at = NULL,
                            conversion_score = NULL
                        WHERE id = %s
                    """, (email, lid))
                else:
                    cur.execute("""
                        UPDATE leads
                        SET smtp_discovery_attempted_at = NOW()
                        WHERE id = %s
                    """, (lid,))
                break  # success
            except psycopg2.errors.DeadlockDetected:
                conn.rollback()
                time.sleep(0.5 * (attempt + 1))
                if attempt == 2:
                    print(f"  [{i}/{len(leads)}] DEADLOCK skip {lid}")

        if email:
            found += 1
            print(f"  [{i}/{len(leads)}] ✓ {website} → {email}")
        elif i % 50 == 0:
            print(f"  [{i}/{len(leads)}] ... {found} found so far")

        # Commit every 25 leads so progress isn't lost if you Ctrl+C
        if i % 25 == 0:
            try:
                conn.commit()
            except Exception:
                conn.rollback()

    conn.commit()
    conn.close()

    hit_rate = round(found / len(leads) * 100, 1)
    print(f"\nDone — {found}/{len(leads)} emails found ({hit_rate}% hit rate)")
    remaining = total - len(leads)
    print(f"Remaining unprocessed: {remaining:,} (run again next week)")


if __name__ == "__main__":
    main()
