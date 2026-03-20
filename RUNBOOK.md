# LeadGen Platform — Runbook

> **Current status** (as of 2026-03-20): All 6 containers healthy. 22,826+ leads in DB,
> AI-scored ongoing, consumer-intent leads actively growing (14 permit cities live, 4 TX cities).
> New: TDLR scraper (12K+ TX electricians), Fort Worth ArcGIS permits (live daily). Scrapers running continuously.

---

## Access URLs (Local)

| Service | URL | What it is |
|---------|-----|-----------|
| **Shop (customer-facing)** | http://localhost:3000 | The storefront buyers use to search and purchase leads |
| **Shop → Search** | http://localhost:3000/shop | Lead search page with AI search toggle |
| **Platform Status** | http://localhost:8000/api/internal/status | JSON: lead counts, AI scoring progress, Yelp budget |
| **Shop Stats** | http://localhost:8000/api/shop/stats | Lead counts by industry (JSON) |
| **API Docs** | http://localhost:8000/docs | Interactive Swagger UI — all backend endpoints |
| **API (raw)** | http://localhost:8000 | FastAPI backend |
| **Database** | localhost:5432 | PostgreSQL (use TablePlus, DBeaver, or psql) |
| **Ollama (AI)** | http://localhost:11434 | Local LLM server |

---

## Starting Everything

### First time setup
```bash
# 1. Open the project folder
cd C:\Users\speco\Desktop\leadgen

# 2. Make sure your .env file has all required values (see .env section below)

# 3. Build and start all services
docker compose up -d --build

# 4. Pull the AI model (one-time, ~4.9GB download)
docker exec leadgen-ollama-1 ollama pull llama3.1:8b

# 5. Trigger first AI scoring batch
curl -X POST "http://localhost:8000/api/internal/score-leads?batch_size=100"
```

### Normal startup (already built)
```bash
cd C:\Users\speco\Desktop\leadgen
docker compose up -d
```

### Shut everything down
```bash
docker compose down
```

### Shut down and wipe all data (DANGER — deletes database and volumes)
```bash
docker compose down -v
```

---

## Services Overview

| Container | Role | Schedule |
|-----------|------|----------|
| `leadgen-postgres-1` | PostgreSQL 16 database | Always |
| `leadgen-ollama-1` | Local LLM (llama3.1:8b) | Always |
| `leadgen-backend-1` | FastAPI API server + APScheduler | Always |
| `leadgen-frontend-1` | Next.js customer storefront | Always |
| `leadgen-scraper-east-1` | Scraper — eastern US states | Every 6 hours |
| `leadgen-scraper-west-1` | Scraper — western US states | Every 6 hours |

**Scraper state split:**
- **Both instances now cover all of Texas** (Texas-first focus) — their separate history files ensure natural diversification across 11,718+ TX city×industry combos
- East/West state splits still apply for non-Texas states

---

## Environment Variables (.env)

Your `.env` file lives at `C:\Users\speco\Desktop\leadgen\.env`.

### Required
```env
POSTGRES_PASSWORD=your_db_password

STRIPE_SECRET_KEY=sk_live_...         # or sk_test_... for testing
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
```

### Optional (free API keys — add to unlock more scraper sources)
```env
# Yelp Places API (formerly "Fusion API") — free, 500 req/day
# Get key: https://www.yelp.com/developers/v3/manage_apps
#   → Click "Create New App" → fill in app name/description → copy "API Key"
YELP_API_KEY=

# Foursquare Places API — free, 950 req/day
# Get key: https://foursquare.com/developers/
FOURSQUARE_API_KEY=
```

After adding API keys, restart the scrapers:
```bash
docker compose restart scraper-east scraper-west
```

---

## Scraper Sources

The scraper rotates across 9 possible sources. Sources without an API key are skipped at startup.

| Source | Key required | Type | Notes |
|--------|-------------|------|-------|
| `yellowpages` | No | B2B business leads | Primary workhorse |
| `superpages` | No | B2B business leads | Good coverage, may rate-limit |
| `manta` | No | B2B business leads | Occasional 400s — scraper skips gracefully |
| `bbb` | No | B2B business leads | Better Business Bureau listings |
| `city_open_data` | No | B2B business leads | Municipal business license data |
| `tdlr` | No | **B2B Texas-only** | State-licensed TX electricians — 12K+ records with address+phone |
| `building_permits` | No | **Consumer intent** | Homeowners actively doing work (see below) |
| `yelp` | Yes (`YELP_API_KEY`) | B2B with ratings | Adds `yelp_rating` + `review_count` to leads |
| `foursquare` | Yes (`FOURSQUARE_API_KEY`) | B2B business leads | Additional coverage |

### Building Permits — Consumer Intent Leads

Building permits are the highest-value lead type: a homeowner who pulled a **ROOFING permit** is literally replacing their roof right now. These leads are marked `lead_type="consumer"` and command a price premium.

**14 active permit cities** across 3 open-data platforms (all free, no API key):

| City | State | Platform | Notes |
|------|-------|----------|-------|
| **Dallas** | **TX** | **Socrata** | Sorted newest-first |
| **Austin** | **TX** | **Socrata** | contractor_full_name field, current 2026 data |
| **San Antonio** | **TX** | **CKAN** | PRIMARY CONTACT field, updated Jan 2026 |
| **Fort Worth** | **TX** | **ArcGIS** | Owner_Full_Name, live daily updates (2026-03-20) |
| Chicago | IL | Socrata | Sorted newest-first |
| New York City | NY | Socrata | No date sort (all records) |
| Seattle | WA | Socrata | No date sort (all records) |
| Honolulu | HI | Socrata | Boolean Y/N work-type fields |
| Boston | MA | CKAN | Sorted newest-first |
| Pittsburgh | PA | CKAN | Sorted newest-first |
| Philadelphia | PA | Carto SQL | Date-filtered SQL query |
| Raleigh | NC | ArcGIS | Parcel owner name — best homeowner data |
| Minneapolis | MN | ArcGIS | Epoch ms dates |
| Nashville | TN | ArcGIS | Epoch ms dates |

The scraper cycles through all active cities round-robin. Every `building_permits` slot routes to the correct platform automatically (Socrata → `BuildingPermitScraper`, CKAN → `CKANPermitScraper`, ArcGIS → `ArcGISPermitScraper`).

Only permits issued **within the last 90 days** are included — ensures leads are actively in-market.

**Industries that produce permit leads** (others return 0 and move on):
roofing, solar, electrician, plumbing, hvac, windows, siding, fencing, decking,
pool installation, gutters, insulation, drywall, concrete, foundation repair,
remodeling, generator, ev charger, waterproofing, painting, flooring, garage door,
mold remediation, landscaping, paving, masonry, radon mitigation

**Commercial filter**: leads where the contact name contains business-type keywords (`llc`, `inc`, `corp`, `ltd`, `lp`, `construction`, `properties`, `realty`, `builders`, `homes`, `development`, `trust`, `investments`, major homebuilders like `lennar`, `pulte`, etc.) are automatically excluded — only individual homeowners are kept.

---

## Monitoring

### View live scraper activity
```bash
# East instance (eastern US states)
docker compose logs scraper-east -f

# West instance (western US states)
docker compose logs scraper-west -f

# Both at once
docker compose logs scraper-east scraper-west -f
```

> Note: `docker compose logs -f scraper` will NOT work — use `scraper-east` or `scraper-west`.

### Check platform health (recommended)
```bash
curl http://localhost:8000/api/internal/status
```
Returns: total leads, AI-scored count, AI-scored %, consumer-intent count, Yelp budget.

### Check lead counts by industry
```bash
curl http://localhost:8000/api/shop/stats
```

### SQL query for lead breakdown
```sql
SELECT
  COUNT(*)                                               AS total,
  COUNT(*) FILTER (WHERE conversion_score IS NOT NULL)   AS ai_scored,
  COUNT(*) FILTER (WHERE lead_type = 'consumer')         AS consumer_intent,
  COUNT(*) FILTER (WHERE yelp_rating IS NOT NULL)        AS has_yelp_rating,
  COUNT(*) FILTER (WHERE review_count >= 10)             AS has_reviews
FROM leads;
```

### View all running containers
```bash
docker compose ps
```

### Check backend logs
```bash
docker compose logs backend --follow
```

---

## AI Features

### AI Conversion Scoring

Every lead gets a `conversion_score` (0–100) assigned by `llama3.1:8b`, estimating the probability the lead converts to a sale. Scored leads command up to 1.5× price premium.

The scoring job runs **automatically every 30 minutes** via APScheduler. To trigger manually:

```bash
# Score 100 leads
curl -X POST "http://localhost:8000/api/internal/score-leads?batch_size=100"

# Score larger batch
curl -X POST "http://localhost:8000/api/internal/score-leads?batch_size=500"
```

To score ALL unscored leads (run until output shows `"scored": 0`):
```bash
# Windows PowerShell
do {
  $r = Invoke-RestMethod -Method POST "http://localhost:8000/api/internal/score-leads?batch_size=100"
  Write-Host "Scored: $($r.scored)"
  Start-Sleep 2
} while ($r.scored -gt 0)
```

**Performance note**: On CPU-only Windows 11, llama3.1:8b scores ~1 lead every 2–4 seconds. 1,000 unscored leads ≈ 45–90 minutes. If you have an NVIDIA GPU, enable Docker GPU passthrough in `docker-compose.yml` (see commented `deploy` block in the `ollama` service).

### AI Natural Language Search

Buyers can search using plain English: _"small roofing companies in Texas without websites"_. The LLM parses the query into structured filters and returns ranked results.

```bash
# Test the AI search endpoint
curl -X POST http://localhost:8000/api/search/ai \
  -H "Content-Type: application/json" \
  -d '{"query": "roofers in Texas without a website"}'
```

If Ollama is unavailable, the endpoint returns HTTP 503 and the frontend automatically falls back to standard search — no buyer-facing breakage.

### Demand-Based Scraping

The scraper tracks which `(industry, state, city)` combos generate the most revenue and prioritises re-scraping those combos up to 5× more often than zero-revenue combos. Updated automatically on every purchase fulfillment.

---

## Running a 3rd Scraper from MacBook

Add a MacBook as a third scraper instance — all three write to the same Windows database, giving you ~3× throughput with no duplicate work (each instance has its own history file).

### One-time Windows setup (allow inbound DB connections)

Open PowerShell as Administrator and run:
```powershell
New-NetFirewallRule -DisplayName "LeadGen PostgreSQL" -Direction Inbound -Protocol TCP -LocalPort 5432 -Action Allow
```

Find your Windows local IP (needed for MacBook config):
```powershell
ipconfig
# Look for: IPv4 Address . . . . . . : 192.168.x.x   (under your Wi-Fi adapter)
```

### MacBook setup

```bash
# 1. Clone the repo
git clone https://github.com/BraydonReid/LeadGen.git
cd LeadGen

# 2. Create your .env from the template
cp .env.macbook.example .env

# 3. Edit .env — set WINDOWS_HOST to your Windows IP and POSTGRES_PASSWORD to match
nano .env   # or open in any editor

# 4. Start the scraper
docker compose -f docker-compose.macbook.yml up -d --build

# 5. Verify it's running and can reach the database
docker compose -f docker-compose.macbook.yml logs scraper-mac -f
# Should show: [scraper [mac]] Scheduler started — running every 6 hours.
```

The MacBook scraper runs as instance "mac" alongside "east" and "west" on Windows. Its separate history file ensures it naturally covers different city × industry combos rather than repeating what the Windows scrapers already hit.

### Monitor all three instances

From Windows:
```bash
# Windows scrapers
docker compose logs scraper-east scraper-west -f

# Lead count growth
curl http://localhost:8000/api/internal/status
```

From MacBook:
```bash
docker compose -f docker-compose.macbook.yml logs scraper-mac -f
```

---

## Stripe Webhook (Required for order fulfillment)

Stripe must reach your server to deliver payment confirmations. For local development:

```bash
# Forward webhook events to your local backend
stripe listen --forward-to localhost:8000/api/webhook
```

This prints a webhook secret — add it to your `.env` as `STRIPE_WEBHOOK_SECRET`.

For production, set the webhook URL in your Stripe dashboard to:
```
https://yourdomain.com/api/webhook
```

---

## Database Access

### Using psql (command line)
```bash
docker exec -it leadgen-postgres-1 psql -U leadgen -d leadgen
```

### Using a GUI (recommended)
Connect with any PostgreSQL client (TablePlus, DBeaver, pgAdmin):
- **Host**: `localhost`
- **Port**: `5432`
- **Database**: `leadgen`
- **Username**: `leadgen`
- **Password**: *(your POSTGRES_PASSWORD from .env)*

### Migrations
Alembic runs automatically on backend startup (`alembic upgrade head`). Current migrations:

| File | What it adds |
|------|-------------|
| `001_initial_schema.py` | `leads`, `purchases` tables |
| `002_add_pricing_fields.py` | Dynamic pricing columns |
| `003_add_lead_quality.py` | `quality_score` column |
| `004_add_purchase_zip_radius.py` | ZIP + radius purchase support |
| `005_buyer_email_and_credits.py` | `buyer_emails`, `store_credits` tables |
| `006_ai_conversion_score.py` | `conversion_score`, `ai_scored_at` on leads |
| `007_demand_tracking.py` | `industry_demand` table |
| `008_review_signals.py` | `yelp_rating`, `review_count` on leads |

To add a new migration:
```bash
# 1. Edit backend/app/models.py
# 2. Create backend/alembic/versions/009_your_description.py (copy an existing file)
# 3. Restart backend to apply:
docker compose restart backend
```

---

## Rebuilding After Code Changes

### Backend changes
```bash
# Backend has hot-reload via uvicorn --reload
# Just save the file — changes apply instantly for most edits

# If you add new dependencies to requirements.txt:
docker compose up -d --build backend
```

### Scraper changes
```bash
# The scraper volume is mounted live (./scraper:/app)
# Python doesn't hot-reload, so restart after any .py change:
docker compose restart scraper-east scraper-west
```

### Frontend changes
```bash
# Frontend has hot-reload for src/ files — just save the file

# If you add new npm packages:
docker compose up -d --build frontend
```

### Full rebuild (everything)
```bash
docker compose up -d --build
```

---

## Troubleshooting

### Backend won't start
```bash
docker compose logs backend
# Usually: missing .env variable, DB connection error, or migration failure
```

### Scraper stopped adding leads
```bash
docker compose logs scraper-east --tail=50
# Common causes:
#   - Source site blocked IP (manta 400, superpages 429) — scraper skips and continues
#   - "Run complete. Total new leads this run: 0" — all targets already scraped or deduped
#   - DB connection error — scraper auto-reconnects and retries
# The scraper restarts automatically (restart: unless-stopped)
```

### Building permits returning 0 leads
```bash
# 1. Confirm the cities being called (should be Chicago, NYC, or Seattle):
docker compose logs scraper-east | grep building_permits

# 2. Test the Chicago API directly:
curl "https://data.cityofchicago.org/resource/ydr8-5enu.json?\$limit=3&\$order=issue_date+DESC" | python3 -m json.tool | head -30

# 3. The industry must have a permit equivalent to get results.
#    Roofing, HVAC, plumbing, electrical, solar are the most common.
#    Non-permit industries (towing, photography, etc.) will always return 0.
```

### AI scoring returns `"scored": 0`
```bash
# Check if Ollama is loaded:
docker exec leadgen-ollama-1 ollama list
# Should show: llama3.1:8b

# If missing, re-pull (requires internet, ~4.9GB):
docker exec leadgen-ollama-1 ollama pull llama3.1:8b

# Check if there are actually unscored leads:
curl http://localhost:8000/api/internal/status
# If ai_scored_pct is 100%, all leads are already scored
```

### Consumer intent count stays at 0 or very low
```bash
# Check if building_permits is hitting the right cities:
docker compose logs scraper-east scraper-west | grep building_permits

# Should show: Chicago IL, New York City NY, or Seattle WA
# If showing other cities, restart the scrapers:
docker compose restart scraper-east scraper-west

# Check DB directly:
docker exec -it leadgen-postgres-1 psql -U leadgen -d leadgen \
  -c "SELECT source, COUNT(*) FROM leads WHERE lead_type='consumer' GROUP BY source;"
```

### Yelp budget shows "no data yet"
Yelp API key is not configured. Add `YELP_API_KEY=` to your `.env` and restart the scrapers. The budget file appears after the first successful Yelp API call.

### Frontend shows stale data
Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)

### Port already in use
```bash
# Find what's using port 3000 or 8000
netstat -ano | findstr :3000
netstat -ano | findstr :8000
```

---

## Quick Reference

```bash
# Start everything
docker compose up -d

# Stop everything
docker compose down

# Live scraper logs (both instances)
docker compose logs scraper-east scraper-west -f

# Platform health
curl http://localhost:8000/api/internal/status

# Lead counts by industry
curl http://localhost:8000/api/shop/stats

# Trigger AI scoring (100 leads)
curl -X POST "http://localhost:8000/api/internal/score-leads?batch_size=100"

# Test AI natural language search
curl -X POST http://localhost:8000/api/search/ai \
  -H "Content-Type: application/json" \
  -d '{"query": "roofing companies in Illinois with phone numbers"}'

# Open shop in browser
start http://localhost:3000

# Open API docs in browser
start http://localhost:8000/docs

# DB shell
docker exec -it leadgen-postgres-1 psql -U leadgen -d leadgen

# Check Ollama model
docker exec leadgen-ollama-1 ollama list
```
