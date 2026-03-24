# LeadGen Platform — Runbook

> **Current status (2026-03-23):** Production live at https://takeyourleadtoday.com
> 102k+ leads in local DB, 11k+ imported to production. Scrapers writing directly to production via Tailscale.
> AI scoring via OpenAI gpt-4o-mini. Subscriptions, magic link auth, referral program, and data quality jobs all live.

---

## Architecture Overview

```
takeyourleadtoday.com        → Hetzner CX23 (46.62.131.115)
api.takeyourleadtoday.com    → Hetzner CX23 (46.62.131.115)

Hetzner Server (production)
  ├── Nginx (reverse proxy + SSL)
  ├── Docker: frontend (Next.js, port 3000)
  ├── Docker: backend (FastAPI, port 8000)
  └── Docker: postgres (PostgreSQL 16, port 5432)

Local Windows Machine
  ├── Docker: scraper-east   (eastern US states → production DB via Tailscale)
  ├── Docker: scraper-west   (western US states → production DB via Tailscale)
  ├── Docker: scraper-north  (extra parallelism → production DB via Tailscale)
  ├── Docker: scraper-south  (extra parallelism → production DB via Tailscale)
  ├── Docker: backend        (local dev only — localhost:8000)
  ├── Docker: frontend       (local dev only — localhost:3000)
  └── Docker: postgres       (local dev DB — localhost:5432)

Tailscale VPN
  Local machine IP:  100.82.202.14
  Server IP:         100.75.12.63
  Scrapers connect to server postgres via: 100.75.12.63:5432
```

---

## Production URLs

| What | URL |
|------|-----|
| **Live site** | https://takeyourleadtoday.com |
| **API** | https://api.takeyourleadtoday.com |
| **Platform status** | https://api.takeyourleadtoday.com/api/internal/status |
| **API docs** | https://api.takeyourleadtoday.com/docs |
| **Stripe webhook** | https://api.takeyourleadtoday.com/api/stripe/webhook |

## Local Dev URLs

| What | URL |
|------|-----|
| **Local site** | http://localhost:3000 |
| **Local API** | http://localhost:8000 |
| **Local status** | http://localhost:8000/api/internal/status |
| **Local API docs** | http://localhost:8000/docs |
| **Local database** | localhost:5432 |

---

## Starting & Stopping

### Production server (SSH into Hetzner)
```bash
ssh root@46.62.131.115

# View running containers
cd /opt/leadgen
docker compose -f docker-compose.prod.yml ps

# Start (if stopped)
docker compose -f docker-compose.prod.yml up -d

# Stop
docker compose -f docker-compose.prod.yml down

# Restart a single service
docker compose -f docker-compose.prod.yml restart backend

# View logs
docker compose -f docker-compose.prod.yml logs backend --tail=50
docker compose -f docker-compose.prod.yml logs frontend --tail=50
```

### Local scrapers (Windows PowerShell)
```powershell
cd C:\Users\speco\Desktop\leadgen

# Start scrapers (writes to production DB via Tailscale)
docker compose up -d --no-deps scraper-east scraper-west scraper-north scraper-south

# Stop scrapers
docker compose stop scraper-east scraper-west scraper-north scraper-south

# View live scraper logs
docker compose logs scraper-east -f
docker compose logs scraper-west scraper-north scraper-south -f

# Restart scrapers after code changes
docker compose up -d --force-recreate --no-deps scraper-east scraper-west scraper-north scraper-south
```

### Local dev environment (optional — for testing changes before deploying)
```powershell
cd C:\Users\speco\Desktop\leadgen

# Start local stack (uses local DB, NOT production)
docker compose up -d --no-deps postgres backend frontend

# Stop local stack
docker compose stop postgres backend frontend
```

---

## Deploying Code Changes to Production

```powershell
# 1. On local machine — commit and push changes
cd C:\Users\speco\Desktop\leadgen
git add -A
git commit -m "describe your changes"
git push
```

```bash
# 2. On production server (SSH)
cd /opt/leadgen
git pull
docker compose -f docker-compose.prod.yml up -d --build backend
# Add --build frontend if you changed frontend files
```

---

## Scrapers

### How they work
- 4 scraper instances run locally (east/west/north/south) — each covers different US states
- Every 6 hours, each instance picks 100 industry×city combinations it hasn't scraped recently
- New leads go directly to the **production database** via Tailscale (100.75.12.63:5432)
- Tailscale must be running on the local machine for scrapers to work

### Scraper state splits
| Instance | States |
|----------|--------|
| east | AL, AR, CT, DE, FL, GA, IL, IN, IA, KY, LA, ME, MD, MA, MI, MN, MS, MO, NH, NJ, NY, NC, ND, OH, PA, RI, SC, SD, TN, VT, VA, WV, WI |
| west | AK, AZ, CA, CO, HI, ID, KS, MT, NE, NV, NM, OK, OR, TX, UT, WA, WY |
| north/south | All states (extra parallelism) |

### Scraper sources
| Source | Key required | Type |
|--------|-------------|------|
| yellowpages | No | B2B business leads |
| superpages | No | B2B business leads |
| manta | No | B2B business leads |
| bbb | No | B2B business leads |
| city_open_data | No | B2B business leads |
| tdlr | No | TX-only licensed contractors |
| building_permits | No | Consumer intent (homeowners actively buying) |
| yelp | Yes (YELP_API_KEY) | B2B with ratings/reviews |
| foursquare | Yes (FOURSQUARE_API_KEY) | Additional B2B coverage |

### If scrapers stop writing to production
```powershell
# 1. Check Tailscale is connected (system tray — should show green checkmark)

# 2. Test connection to production DB
powershell -Command "Test-NetConnection -ComputerName 100.75.12.63 -Port 5432"
# TcpTestSucceeded should be True

# 3. Force restart scrapers
cd C:\Users\speco\Desktop\leadgen
docker compose up -d --force-recreate --no-deps scraper-east scraper-west scraper-north scraper-south

# 4. Verify leads flowing (check production)
curl -s https://api.takeyourleadtoday.com/api/internal/status
```

---

## AI Scoring (OpenAI gpt-4o-mini)

Every lead gets a `conversion_score` (0–100) estimating likelihood of converting to a sale.
Runs automatically every 10 minutes on the production server.

```bash
# Trigger manually on production (SSH)
curl -s -X POST "https://api.takeyourleadtoday.com/api/internal/score-leads?batch_size=200"

# Score ALL unscored leads (run in PowerShell loop locally)
while ($true) {
    $r = Invoke-RestMethod -Method Post "http://localhost:8000/api/internal/score-leads?batch_size=200"
    Write-Host "Scored: $($r.scored)"
    if ($r.scored -eq 0) { break }
    Start-Sleep -Seconds 2
}
```

**Cost reference:** ~$0.002 per 10 leads. Scoring 100k leads ≈ $2 total.

---

## Email Scraping

Scrapes contact emails directly from lead websites. Free, no API limits.
Runs automatically every 20 minutes on the production server.

```bash
# Trigger manually on production (SSH)
curl -s -X POST "https://api.takeyourleadtoday.com/api/internal/scrape-emails?batch_size=300"

# Run until complete (PowerShell loop locally)
while ($true) {
    $r = Invoke-RestMethod -Method Post "http://localhost:8000/api/internal/scrape-emails?batch_size=300"
    Write-Host "Found: $($r.found) | Remaining: $($r.remaining_unattempted)"
    if ($r.remaining_unattempted -eq 0) { break }
    Start-Sleep -Seconds 5
}
```

---

## Data Quality Jobs

Run automatically via scheduler. Can also be triggered manually.

```bash
# Normalize + validate all phone numbers (every 30 min automatically)
curl -s -X POST "https://api.takeyourleadtoday.com/api/internal/clean-phones?batch_size=2000"

# Find and mark duplicate leads (daily automatically)
curl -s -X POST "https://api.takeyourleadtoday.com/api/internal/dedup-leads?batch_size=500"
```

---

## Migrating Local Leads to Production

Use this when you have a batch of locally-scored leads ready to push to production.

```powershell
# Step 1 — Export ready leads from local DB (scored + email scraped + not duplicate)
docker exec leadgen-postgres-1 psql -U leadgen -d leadgen -c "\COPY (SELECT business_name, industry, city, state, website, email, phone, source_url, scraped_date, times_sold, zip_code, full_address, contact_name, lead_type, quality_score, source, conversion_score, website_quality_signal, contact_richness_signal, ai_scored_at, yelp_rating, review_count, years_in_business, email_source, email_found_at, enrichment_attempted_at, website_scrape_attempted_at, phone_valid, website_status FROM leads WHERE ai_scored_at IS NOT NULL AND website_scrape_attempted_at IS NOT NULL AND duplicate_of_id IS NULL) TO '/tmp/ready_leads.csv' CSV HEADER"

docker cp leadgen-postgres-1:/tmp/ready_leads.csv C:\Users\speco\Desktop\ready_leads.csv

# Step 2 — Transfer to server
scp C:\Users\speco\Desktop\ready_leads.csv root@46.62.131.115:/tmp/ready_leads.csv
```

```bash
# Step 3 — Import on server (SSH)
docker cp /tmp/ready_leads.csv leadgen-postgres-1:/tmp/

docker exec -i leadgen-postgres-1 psql -U leadgen -d leadgen << 'SQL'
CREATE TEMP TABLE leads_stage (
  business_name VARCHAR(255), industry VARCHAR(100), city VARCHAR(100),
  state VARCHAR(50), website TEXT, email VARCHAR(255), phone VARCHAR(30),
  source_url VARCHAR(500), scraped_date TIMESTAMP, times_sold INTEGER,
  zip_code VARCHAR(10), full_address TEXT, contact_name VARCHAR(255),
  lead_type VARCHAR(20), quality_score SMALLINT, source VARCHAR(50),
  conversion_score SMALLINT, website_quality_signal SMALLINT,
  contact_richness_signal SMALLINT, ai_scored_at TIMESTAMP,
  yelp_rating FLOAT, review_count INTEGER, years_in_business SMALLINT,
  email_source VARCHAR(20), email_found_at TIMESTAMP,
  enrichment_attempted_at TIMESTAMP, website_scrape_attempted_at TIMESTAMP,
  phone_valid BOOLEAN, website_status VARCHAR(10)
);
\COPY leads_stage FROM '/tmp/ready_leads.csv' CSV HEADER;
INSERT INTO leads (business_name, industry, city, state, website, email, phone,
  source_url, scraped_date, times_sold, zip_code, full_address, contact_name,
  lead_type, quality_score, source, conversion_score, website_quality_signal,
  contact_richness_signal, ai_scored_at, yelp_rating, review_count,
  years_in_business, email_source, email_found_at, enrichment_attempted_at,
  website_scrape_attempted_at, phone_valid, website_status)
SELECT * FROM leads_stage
ON CONFLICT (source_url) DO NOTHING;
SELECT COUNT(*) as total_leads FROM leads;
SQL
```

---

## Database Access

### Production database (SSH)
```bash
ssh root@46.62.131.115
docker exec -it leadgen-postgres-1 psql -U leadgen -d leadgen
```

### Production database (GUI — TablePlus, DBeaver, etc.)
Connect via SSH tunnel:
- **SSH Host:** 46.62.131.115 | **SSH User:** root
- **Host:** localhost | **Port:** 5432
- **Database:** leadgen | **Username:** leadgen | **Password:** (your POSTGRES_PASSWORD)

### Local database
- **Host:** localhost | **Port:** 5432
- **Database:** leadgen | **Username:** leadgen | **Password:** (your POSTGRES_PASSWORD)

### Useful queries
```sql
-- Overall health
SELECT
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE ai_scored_at IS NOT NULL) as ai_scored,
  COUNT(*) FILTER (WHERE email IS NOT NULL) as has_email,
  COUNT(*) FILTER (WHERE phone_valid = true) as valid_phones,
  COUNT(*) FILTER (WHERE duplicate_of_id IS NOT NULL) as duplicates,
  COUNT(*) FILTER (WHERE lead_type = 'consumer') as consumer_intent,
  COUNT(*) FILTER (WHERE website_status = 'dead') as dead_websites
FROM leads;

-- Leads by state
SELECT state, COUNT(*) as count FROM leads
WHERE duplicate_of_id IS NULL GROUP BY state ORDER BY count DESC;

-- Leads by industry (top 20)
SELECT industry, COUNT(*) as count FROM leads
WHERE duplicate_of_id IS NULL GROUP BY industry ORDER BY count DESC LIMIT 20;
```

---

## Subscriptions & Payments

### How subscriptions work
1. Customer visits https://takeyourleadtoday.com/subscribe
2. Enters email → redirected to Stripe checkout ($99/month)
3. On payment: Stripe webhook → `POST /api/stripe/webhook` → subscription created in DB
4. Customer visits https://takeyourleadtoday.com/my-subscription
5. Enters email → receives magic link via email → clicks link → authenticated session
6. Downloads up to 300 leads/month as CSV

### Stripe dashboard
- Live keys: dashboard.stripe.com
- Webhook endpoint: `https://api.takeyourleadtoday.com/api/stripe/webhook`
- Events: `checkout.session.completed`, `invoice.payment_succeeded`, `customer.subscription.deleted`

### Updating Stripe keys on production
```bash
ssh root@46.62.131.115
nano /opt/leadgen/.env
# Update STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY
cd /opt/leadgen && docker compose -f docker-compose.prod.yml restart backend
```

---

## Environment Variables

### Local (.env at C:\Users\speco\Desktop\leadgen\.env)
```env
POSTGRES_PASSWORD=          # Local DB password
STRIPE_SECRET_KEY=          # sk_live_...
STRIPE_WEBHOOK_SECRET=      # whsec_...
STRIPE_PUBLISHABLE_KEY=     # pk_live_...
YELP_API_KEY=               # Yelp Fusion API key
FOURSQUARE_API_KEY=         # Foursquare Places API key
HUNTER_API_KEY=             # Hunter.io (email enrichment)
RESEND_API_KEY=             # Resend (email sending)
RESEND_FROM_EMAIL=          # hello@takeyourleadtoday.com
RESEND_FROM_NAME=           # Texas LeadGen
OPENAI_API_KEY=             # OpenAI API key (gpt-4o-mini)
SITE_URL=                   # https://takeyourleadtoday.com
SCRAPER_DATABASE_URL=       # postgresql://leadgen:PASSWORD@100.75.12.63:5432/leadgen
```

### Production (.env at /opt/leadgen/.env on server)
Same keys as above except:
- No `SCRAPER_DATABASE_URL` (scrapers don't run on server)
- `CORS_ORIGINS` set to production domain in docker-compose.prod.yml

---

## Nginx & SSL

Config lives at `/etc/nginx/sites-available/leadgen` on the server.
SSL certificates auto-renew via Certbot (expires 2026-06-21, renews automatically).

```bash
# Test nginx config
nginx -t

# Reload nginx (after config changes)
systemctl reload nginx

# Check SSL certificate expiry
certbot certificates

# Force SSL renewal (if needed)
certbot renew
```

---

## Server Maintenance

```bash
# Check disk space
df -h

# Check memory usage
free -m

# Check running containers
docker compose -f docker-compose.prod.yml ps

# View all container logs live
docker compose -f docker-compose.prod.yml logs -f

# Restart entire production stack
cd /opt/leadgen
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d

# Pull latest code and rebuild
cd /opt/leadgen
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Scheduled Jobs (run automatically on production)

| Job | Frequency | What it does |
|-----|-----------|-------------|
| AI scoring | Every 10 min | Scores unscored leads via OpenAI |
| Website email scraper | Every 20 min | Scrapes emails from lead websites |
| Email campaigns | Every 15 min | Sends cold outreach emails |
| Phone cleaner | Every 30 min | Normalizes + validates phone numbers |
| Deduplication | Every 24 hours | Marks duplicate leads |
| Subscriber emails | Every 1 hour | Sends lifecycle emails to subscribers |

---

## Quick Reference

```bash
# SSH to server
ssh root@46.62.131.115

# Check production health
curl -s https://api.takeyourleadtoday.com/api/internal/status

# Trigger AI scoring (production)
curl -s -X POST "https://api.takeyourleadtoday.com/api/internal/score-leads?batch_size=200"

# Trigger email scraping (production)
curl -s -X POST "https://api.takeyourleadtoday.com/api/internal/scrape-emails?batch_size=300"

# Trigger phone cleaning (production)
curl -s -X POST "https://api.takeyourleadtoday.com/api/internal/clean-phones?batch_size=2000"

# Trigger deduplication (production)
curl -s -X POST "https://api.takeyourleadtoday.com/api/internal/dedup-leads?batch_size=500"

# View backend logs (production)
ssh root@46.62.131.115 "cd /opt/leadgen && docker compose -f docker-compose.prod.yml logs backend --tail=50"

# View scraper logs (local)
docker compose logs scraper-east -f

# DB shell (production)
ssh root@46.62.131.115 "docker exec -it leadgen-postgres-1 psql -U leadgen -d leadgen"

# DB shell (local)
docker exec -it leadgen-postgres-1 psql -U leadgen -d leadgen
```
