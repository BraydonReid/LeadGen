# LeadGen Platform — Runbook

## Access URLs (Local)

| Service | URL | What it is |
|---------|-----|-----------|
| **Shop (customer-facing)** | http://localhost:3000 | The storefront buyers use to search and purchase leads |
| **Shop → Search** | http://localhost:3000/shop | Lead search page with AI search toggle |
| **Admin Stats** | http://localhost:8000/api/shop/stats | Live lead counts by industry (JSON) |
| **API Docs** | http://localhost:8000/docs | Interactive Swagger UI — all backend endpoints |
| **API (raw)** | http://localhost:8000 | FastAPI backend |
| **Database** | localhost:5432 | PostgreSQL (use TablePlus, DBeaver, or psql) |
| **Ollama (AI)** | http://localhost:11434 | Local LLM server |

---

## Starting Everything

### First time setup
```bash
# 1. Clone / open the project folder
cd C:\Users\speco\Desktop\leadgen

# 2. Make sure your .env file has all required values (see .env section below)

# 3. Build and start all services
docker compose up -d --build

# 4. Pull the AI model (one-time, ~4.7GB download)
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

### Shut down and wipe all data (DANGER — deletes database)
```bash
docker compose down -v
```

---

## Services Overview

| Container | Role | Runs |
|-----------|------|------|
| `leadgen-postgres-1` | Database | Always |
| `leadgen-ollama-1` | Local AI (LLM) | Always |
| `leadgen-backend-1` | API server (FastAPI) | Always |
| `leadgen-frontend-1` | Customer storefront (Next.js) | Always |
| `leadgen-scraper-east-1` | Scraper — eastern states | Every 6 hours |
| `leadgen-scraper-west-1` | Scraper — western states | Every 6 hours |

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

### Optional (free API keys — add to enable more scraper sources)
```env
# Yelp Places API (formerly "Fusion API") — free, 500 req/day
# Get key: https://www.yelp.com/developers/v3/manage_apps
#   → Click "Create New App" → fill in app name/description → copy "API Key"
#   → Use the "Yelp Places API" (REST API) — NOT GraphQL, NOT Transactions
YELP_API_KEY=

# Foursquare Places API — free, 950 req/day
# Get key: https://foursquare.com/developers/
FOURSQUARE_API_KEY=
```

After adding API keys, restart the scrapers:
```bash
docker compose up -d scraper-east scraper-west
```

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

> Note: The old `scraper` service was split into `scraper-east` and `scraper-west`.
> `docker compose logs -f scraper` will NOT work — use `scraper-east` or `scraper-west`.

### Check total leads in database
```bash
curl http://localhost:8000/api/shop/stats
```

Or connect to the database and run:
```sql
SELECT
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE conversion_score IS NOT NULL) AS ai_scored,
  COUNT(*) FILTER (WHERE yelp_rating IS NOT NULL) AS has_rating,
  COUNT(*) FILTER (WHERE review_count >= 10) AS has_reviews
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

## AI Scoring

The AI scoring job runs automatically every 30 minutes via APScheduler. To trigger it manually:

```bash
# Score 100 leads
curl -X POST "http://localhost:8000/api/internal/score-leads?batch_size=100"

# Score larger batch
curl -X POST "http://localhost:8000/api/internal/score-leads?batch_size=500"
```

To score ALL unscored leads (run until you see "scored: 0"):
```bash
# Windows PowerShell
do {
  $r = Invoke-RestMethod -Method POST "http://localhost:8000/api/internal/score-leads?batch_size=100"
  Write-Host "Scored: $($r.scored)"
  Start-Sleep 2
} while ($r.scored -gt 0)
```

---

## Stripe Webhook (Required for order fulfillment)

Stripe must be able to reach your server to deliver payment confirmations. For local development, use the Stripe CLI:

```bash
# Install Stripe CLI if not already installed
# https://stripe.com/docs/stripe-cli

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
- Host: `localhost`
- Port: `5432`
- Database: `leadgen`
- Username: `leadgen`
- Password: *(your POSTGRES_PASSWORD from .env)*

---

## Rebuilding After Code Changes

### Backend changes (most hot-reload automatically)
```bash
# Backend has hot-reload via uvicorn --reload
# Just save the file — changes apply instantly, no restart needed

# If you add new dependencies to requirements.txt:
docker compose up -d --build backend
```

### Scraper changes
```bash
docker compose up -d --build scraper-east scraper-west
```

### Frontend changes
```bash
# Frontend has hot-reload for src/ files
# Just save the file — changes apply instantly

# If you add new npm packages:
docker compose up -d --build frontend
```

### Full rebuild (everything)
```bash
docker compose up -d --build
```

---

## Adding a New Database Migration

```bash
# 1. Edit backend/app/models.py with your new columns/tables

# 2. Create a new migration file in backend/alembic/versions/
#    Name it: 009_your_description.py
#    Copy the format from an existing migration file

# 3. Alembic runs automatically on backend startup (alembic upgrade head)
#    Restart the backend to apply:
docker compose restart backend
```

---

## Troubleshooting

### Backend won't start
```bash
docker compose logs backend
# Usually a missing .env variable or migration error
```

### Scraper stopped adding leads
```bash
docker compose logs scraper-east --tail=50
# Common causes: site blocked IP, network timeout, all combos already scraped
# The scraper restarts automatically (restart: unless-stopped)
```

### AI scoring returns scored: 0
The Ollama model may not be loaded. Check:
```bash
docker exec leadgen-ollama-1 ollama list
# Should show: llama3.1:8b

# If missing, pull again:
docker exec leadgen-ollama-1 ollama pull llama3.1:8b
```

### Frontend shows stale data
Hard refresh the browser: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)

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

# View all logs
docker compose logs --follow

# Check lead count
curl http://localhost:8000/api/shop/stats

# Trigger AI scoring
curl -X POST "http://localhost:8000/api/internal/score-leads?batch_size=100"

# Open shop in browser
start http://localhost:3000

# Open API docs in browser
start http://localhost:8000/docs
```
