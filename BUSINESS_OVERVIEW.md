# LeadGen Platform — Complete Business & Feature Overview

**Prepared for:** Business Analysis / Investor Review
**Date:** March 2026
**Stack:** Next.js 14 (frontend) · FastAPI + PostgreSQL (backend) · Python scrapers · Stripe Checkout · Docker

---

## 1. What the Business Does

LeadGen is a self-serve B2B and B2C lead marketplace. Businesses (roofers, plumbers, solar installers, lawyers, dentists, etc.) visit the site, search for prospects in their target industry and geography, preview a sample of matching leads, and purchase a CSV download instantly — no sales call, no contract, no minimum commitment.

There are two distinct lead products:

| Product | Source | Who Buys It | Premium |
|---|---|---|---|
| **Business Directory Leads** | Scraped from YellowPages, Superpages, Manta, BBB | B2B marketers, sales teams | Standard pricing |
| **Consumer Intent Leads** | Homeowners submit a service request form | Contractors, home service providers | 1.5× price multiplier |

---

## 2. Site Pages & User Flow

### 2.1 Homepage (`/`)
- **Hero section** with live stats: total leads in database, number of consumer intent leads, industries covered, and states covered.
- **How It Works:** 3 steps (Search → Preview → Purchase & Download).
- **Competitor Comparison Table:** 8-row table comparing LeadGen to typical lead vendors across: no sales call, instant CSV delivery, max resales per lead, quality score transparency, freshness guarantee, bad lead protection, free sample, and no monthly contract.
- **Consumer Portal CTA:** Two-column section explaining intent leads to potential buyers (left) and prompting homeowners to submit a service request (right).
- **Features section:** Highlights "Max 5 Resales — Ever" (resale cap explained), "Bad Lead Guarantee" (credit policy explained), "Instant Download," and bulk discounts.
- Footer with navigation links.

### 2.2 Lead Shop (`/shop`)
The core conversion page.

**Search inputs:**
- Industry (free text, e.g. "roofing", "solar", "HVAC")
- **Search mode toggle:** City/State *or* ZIP + Radius
  - City/State: state dropdown + optional city text
  - ZIP + Radius: 5-digit ZIP code + radius selector (5 / 10 / 25 / 50 / 100 miles)
- **Lead type toggle:** All Leads / Business Directory / Intent Leads

**Results panel (left ⅔):**
- Total match count + avg price per lead
- **Free sample card** (shown above preview table): enter email → receive a 5-lead CSV download instantly, no payment required. Rate-limited to one sample per email per industry/state combination. Collapses to a success state after download.
- 10-row sample table with columns: Business Name, City (+ address subtitle), Phone, Website, Email (hidden until purchase), Type badge, Quality badge, Unit price
- Quality Score Legend panel explaining the 0–100 scoring formula
- "Sample of X of Y leads" disclosure

**Price Calculator (right ⅓ — sticky):**
- Quantity slider + numeric input (1 to available count, max 10,000)
- Live bulk discount tiers display (highlights active tier)
- Price breakdown: avg price, subtotal, bulk discount, promo/credit discount, total
- **Promo code field:** enter a store credit code (e.g. `CRED-A3F12B9E`) → validated live against backend → discount reflected in total before checkout
- "Buy N Leads — $X.XX" → Stripe Checkout redirect

### 2.3 Consumer Service Request Portal (`/request-service`)
Marketed to homeowners as "Get Free Quotes from Local Contractors."

**Form fields:**
- Full Name, Email, Phone
- ZIP Code, City, State
- Service Needed (dropdown — 35 home service categories)
- Project Description (textarea)
- Timeline (ASAP / 1–3 months / 3–6 months / Planning)
- Property Type (Residential / Commercial)

On submit: lead is saved to the database as `lead_type='consumer'` and immediately available for purchase in the shop. The submitter sees a confirmation card.

**Duplicate guard:** email + industry combination is checked; duplicate submissions are rejected with a friendly message.

### 2.4 Checkout Success (`/success?session_id=...`)
After Stripe payment is confirmed:
- Page polls the download endpoint until the file is ready (up to 30 seconds with progress bar)
- Once fulfilled, shows a download button for the CSV file
- CSV is streamed directly; `times_sold` is incremented per delivered lead
- **"Report bad leads" section** (collapsible, below download button): buyer can describe the issue (e.g. disconnected numbers, wrong industry, closed businesses), submit the form, and immediately receive a store credit code. Credit is 10% of the purchase amount, minimum $0.50. Code is displayed in a copyable green banner.

---

## 3. Store Credit System

### How It Works
1. After downloading a CSV, the buyer sees a "Found bad leads? Report them → get store credit" link
2. Buyer describes the problem and clicks "Submit & Get Credit"
3. Backend validates: purchase must exist, be fulfilled, and not already have a credit issued
4. A unique code is generated (format: `CRED-XXXXXXXX`) and stored in the `lead_credits` table
5. Code is displayed on screen with the dollar amount (e.g. "You've earned $4.50 in store credit")
6. Buyer copies the code and enters it in the Price Calculator promo code field on their next order
7. Discount is subtracted from the Stripe checkout amount before payment

### Key Properties
- **One credit per purchase** — prevents abuse
- **10% of purchase amount** (min $0.50)
- **Single-use** — code is marked `used=True` the moment a new Stripe session is created with it
- **Never expires**
- **Transparent** — buyer sees exact dollar value before applying

### Business Impact
Buyers who receive a credit come back for a second purchase. The 10% credit costs less than customer acquisition cost for a new buyer, making it a net-positive retention mechanism.

---

## 4. Lead Data & Quality

### 4.1 Fields Stored Per Lead

| Field | Description |
|---|---|
| `business_name` | Company or person name |
| `industry` | Normalized industry category |
| `city`, `state` | Location |
| `zip_code` | 5-digit ZIP (where available from source) |
| `full_address` | Street address + city + state + ZIP |
| `phone` | Normalized to `(XXX) XXX-XXXX` format |
| `email` | Email address (hidden in preview, included in CSV) |
| `website` | Domain URL |
| `contact_name` | Named contact (when extractable) |
| `quality_score` | 0–100 integer (see formula below) |
| `lead_type` | `business` or `consumer` |
| `source` | `yellowpages`, `superpages`, `manta`, `bbb`, `consumer_form` |
| `scraped_date` | Last time this lead was seen/refreshed |
| `times_sold` | How many times this lead has been sold (max 5) |
| `source_url` | Original listing page URL (used for dedup) |

### 4.2 Quality Score Formula (0–100)

```
+30  Phone number present and valid (normalized to US format)
+25  Email address present
+20  Website URL present
+15  Full address and/or ZIP code present
+10  Contact name present
─────
100  Maximum (all 5 data points present)
```

**Color bands shown in the shop:**
- **Green (80–100):** Premium — 4–5 data points confirmed
- **Yellow (50–79):** Good — core contact info present (phone + email or phone + website)
- **Red (0–49):** Basic — limited contact data

### 4.3 Freshness Policy
Leads must have been scraped or refreshed within the last **180 days** to appear in shop results, checkout, or CSV downloads. This is enforced at the database query level — expired leads are invisible to buyers.

When a scraper re-encounters a lead already in the database (matched by source URL or business name + phone/website fingerprint), the `scraped_date` is updated to now, keeping active businesses perpetually fresh without creating duplicates.

---

## 5. Data Sources & Scraping

### 5.1 Scraper Sources (4-way rotation)

| Source | Type | Strengths |
|---|---|---|
| YellowPages.com | B2B directory | Broad coverage, phone + website, category structure |
| Superpages.com | B2B directory | Street address + ZIP, different business coverage |
| Manta.com | B2B directory | Business-focused, contact names on many listings |
| BBB.org | B2B directory | High-trust verified businesses, accreditation status |

Each scraper run picks 20 targets (industry × city combinations) and rotates through sources evenly. If YellowPages is source 0, Superpages is 1, Manta is 2, BBB is 3 — then target 4 wraps back to YellowPages, etc.

### 5.2 Industry Coverage
**85+ industries** across 8 categories:
- Home Exterior (roofing, siding, gutters, windows, painting, masonry, paving, fencing, concrete, pressure washing)
- Home Interior (remodeling, flooring, drywall, insulation, waterproofing, cabinets, countertops, blinds, closet, carpet cleaning, air duct cleaning, chimney)
- Mechanical/Utilities (plumbing, HVAC, electrician, solar, generator, EV charger, septic, well pump, garage door)
- Landscaping/Outdoor (landscaping, tree service, pool, irrigation, deck/patio, outdoor lighting, snow removal)
- Professional Services (law firm, accountant, insurance, real estate, financial advisor, mortgage, chiropractor, physical therapy, veterinary, staffing)
- Healthcare (dentist, optometry, urgent care, dermatology, plastic surgery)
- Automotive (auto repair, auto body, auto detailing, towing, windshield repair)
- Business Services (IT services, digital marketing, web design, photography, security systems, commercial cleaning, commercial HVAC, commercial plumbing)

### 5.3 Geographic Coverage
**All 50 US states** with 4–15 major cities per state (~400 cities, ~34,000 industry × location combinations).

### 5.4 Target Selection Algorithm (Industry Diversity)
The scraper uses a history file to track when each industry × city combination was last scraped. Each run:
1. Groups all combinations by industry
2. Shuffles the industry order (random each run — prevents one industry dominating)
3. Round-robins across industries, picking the **oldest-scraped** city within each industry
4. Result: every run covers ~20 different industries before repeating any single one

This ensures roofing, siding, HVAC, plumbing, solar, etc. all get equal coverage instead of roofing being scraped in all 400 cities before any other industry gets a turn.

---

## 6. Lead Pricing Engine

Every lead has a dynamically calculated unit price. The formula:

```
Price = base × quality_mult × location_mult × freshness_mult × resale_mult × type_mult
```

Capped at **$0.05 minimum** and **$5.00 maximum**.

### 6.1 Base Price by Industry

| Industry | Base |
|---|---|
| Law firm | $0.90 |
| Insurance | $0.70 |
| Medical | $0.75 |
| Dentist | $0.65 |
| Solar | $0.60 |
| Roofing | $0.55 |
| HVAC | $0.50 |
| Plumbing, Electrician | $0.45 |
| Real estate | $0.40 |
| Construction, Pest control | $0.40 |
| Landscaping | $0.35 |
| Marketing agency | $0.30 |
| Restaurant, Retail | $0.10–0.12 |
| All other industries | $0.25 (default) |

### 6.2 Quality Multiplier
`1.0 + (quality_score / 100)` → range **1.0× (score=0) to 2.0× (score=100)**

A lead with phone + email + website + address + name (score=100) is priced at **2× base**.
A bare-minimum lead with only a phone (score=30) is priced at **1.3× base**.

### 6.3 Location Multiplier

| Market | Multiplier |
|---|---|
| Tier 1 metros (NYC, LA, SF, Chicago, Dallas, Austin, Miami, Seattle) | 1.40× |
| Large metros (Houston, Phoenix, Atlanta, Denver, Nashville, etc.) | 1.25× |
| All other cities | 1.10× |

### 6.4 Freshness Multiplier

| Age | Multiplier |
|---|---|
| ≤ 30 days | 1.30× |
| 31–90 days | 1.15× |
| 91–180 days | 1.05× |
| 181–365 days | 1.00× |
| > 365 days | 0.80× (rarely reached — freshness filter keeps these out of shop) |

### 6.5 Resale Multiplier
Each lead can be sold up to **5 times** total. Each prior sale discounts the price by 10%:
`max(0.60, 1.0 − times_sold × 0.10)`

A never-sold lead = 1.0×. A 4× sold lead = 0.60×. After 5 sales, the lead is hidden from the shop.

### 6.6 Lead Type Multiplier
- Business directory lead: **1.0×**
- Consumer intent lead: **1.5×** (they actively requested the service — dramatically higher conversion rate)

### 6.7 Bulk Purchase Discounts

| Quantity | Discount |
|---|---|
| 10,000+ | 45% off |
| 5,000+ | 35% off |
| 1,000+ | 25% off |
| 500+ | 18% off |
| 100+ | 10% off |
| 1–99 | No discount |

### 6.8 Worked Price Examples

**Example A — Premium roofing intent lead in Austin, TX (fresh):**
- Base: $0.55 · Quality (score=85): ×1.85 · Location (Austin, Tier 1): ×1.40 · Freshness (15 days): ×1.30 · Resale (0): ×1.0 · Type (consumer): ×1.5
- = $0.55 × 1.85 × 1.40 × 1.30 × 1.0 × 1.5 = **~$3.30/lead**

**Example B — Standard HVAC business lead in a mid-size city (60 days old):**
- Base: $0.50 · Quality (score=55): ×1.55 · Location (mid-size): ×1.10 · Freshness (60 days): ×1.15 · Resale (1): ×0.90 · Type (business): ×1.0
- = $0.50 × 1.55 × 1.10 × 1.15 × 0.90 × 1.0 = **~$0.88/lead**

**Example C — 1,000 landscaping leads in Florida (bulk discount applied):**
- Avg price ~$0.45 · Subtotal: $450.00 · 25% bulk discount: −$112.50
- **Total: $337.50** ($0.3375/lead effective)

---

## 7. Consumer Intent Lead Funnel

### How Intent Leads Enter the System
1. Homeowner visits `/request-service` (marketed via Google as "Get Free Quotes")
2. Fills out the service request form (name, contact info, ZIP, service type, timeline, property type)
3. Backend validates, normalizes phone, checks for duplicate submissions
4. Lead saved to database with `lead_type='consumer'`, `source='consumer_form'`
5. Quality score calculated (consumer leads with complete info typically score 65–100)
6. Lead is immediately searchable in the shop under "Intent Leads" filter

### Why They're More Valuable
- The homeowner **actively asked** for the service — no cold outreach needed
- They provided a timeline (ASAP, 1–3 months, etc.) allowing contractors to prioritize
- They provided property type (residential/commercial) for fit assessment
- They are sold at **1.5× the price** of equivalent business directory leads

### Growth Mechanism
Consumer intent lead volume grows through:
- SEO on `/request-service` (targeting "get roofing quotes", "find local plumbers", etc.)
- Referrals from contractors who've seen intent lead conversion rates
- The homepage CTA and shop-page banner driving homeowner awareness

---

## 8. Payment & Delivery

### Checkout Flow
1. User configures quantity and optional promo code in the price calculator
2. Backend validates promo code (if provided): must exist and be unused; discount subtracted from total
3. Backend creates a Stripe Checkout Session (hosted payment page) with the exact dollar amount
4. Stripe metadata stores: industry, state, city, quantity, lead_type, zip_code, radius_miles
5. User is redirected to Stripe's hosted checkout page
6. User enters card details and pays
7. Stripe fires a webhook (`checkout.session.completed`) to the backend
8. Backend marks the Purchase record as `fulfilled=True` and captures the buyer's email from Stripe
9. User is redirected to `/success?session_id=...` and downloads the CSV

### Buyer Email Capture
The Stripe webhook captures the buyer's email (`session.customer_details.email`) and stores it on the Purchase record. This enables future marketing without requiring a separate account registration step.

### CSV Download
The downloaded CSV includes all fields:
`business_name, contact_name, city, state, zip_code, full_address, email, phone, website, lead_type, quality_score`

Email and phone (full, unmasked) are included in the download but not shown in the shop preview — this prevents lead harvesting without purchase.

### Resale Tracking
After a successful download, `times_sold` is incremented for every delivered lead. Once a lead reaches `times_sold = 5`, it is permanently removed from the available pool.

---

## 9. Technical Infrastructure

| Component | Technology | Role |
|---|---|---|
| Frontend | Next.js 14 App Router, TypeScript, Tailwind CSS | UI, SEO, static generation |
| Backend API | FastAPI (Python 3.12), async SQLAlchemy 2.0 | REST API, business logic |
| Database | PostgreSQL 16 | Lead storage, purchase records, credits |
| Scraper | Python 3.12, BeautifulSoup, Requests | Automated lead acquisition |
| Payments | Stripe Checkout + Webhooks | Secure payment processing |
| Geocoding | uszipcode (bundled SQLite — no API key needed) | ZIP radius search |
| Deployment | Docker Compose (4 containers) | Local/VPS deployment |

### Database Tables
- `leads` — all lead records
- `purchases` — Stripe session records (includes buyer email, zip_code, radius_miles)
- `lead_credits` — store credit codes (code, discount_cents, session_id, used)
- `sample_requests` — free sample dedup log (email, industry, state)
- `alembic_version` — migration state tracker

### Database Indexes
- `lead.industry` — for industry search
- `lead.state` — for state filtering
- `lead.lead_type` — for business/consumer filtering
- `lead.quality_score` — for quality-based sorting
- `lead.source_url` — unique index for dedup
- `purchase.stripe_session_id` — for webhook/download lookups
- `lead_credits.code` — unique index for promo code lookups
- `sample_requests.(email, industry, state)` — unique constraint for dedup

---

## 10. Revenue Model Analysis

### Revenue Per Transaction

At current pricing, a typical transaction:

| Scenario | Qty | Avg Price | Total |
|---|---|---|---|
| Small purchase (no discount) | 50 | $0.45 | $22.50 |
| Mid-tier purchase (10% off) | 100 | $0.50 | $45.00 |
| Business package (25% off) | 1,000 | $0.55 | $412.50 |
| Enterprise (45% off) | 10,000 | $0.60 | $3,300.00 |

### Revenue Per Lead (Lifetime)
Each lead can be sold up to 5 times, at declining resale prices:
- Sale 1: 1.0× price
- Sale 2: 0.90× price
- Sale 3: 0.80× price
- Sale 4: 0.70× price
- Sale 5: 0.60× price

**Lifetime revenue per lead ≈ 4.0× the first-sale price** (sum of multipliers: 1.0 + 0.9 + 0.8 + 0.7 + 0.6 = 4.0).

A roofing lead in Austin with a quality score of 80, sold 5 times:
- First sale: ~$2.20 · Times 4.0 total = **~$8.80 lifetime revenue per lead**

### Cost Structure
- **Variable cost per lead: ~$0** — scraped automatically, consumer leads submitted for free
- **Scraper infrastructure:** minimal (VPS or existing server)
- **Stripe fees:** 2.9% + $0.30 per transaction
- **Store credit liability:** up to 10% of revenue for buyers who report bad leads — this is intentional; a satisfied repeat buyer is worth more than 10%
- **API / hosting costs:** Low (PostgreSQL + FastAPI + Next.js on any $10–20/month VPS)

### Gross Margin
Near 100% on revenue once infrastructure is paid — the leads cost nothing to acquire beyond compute time and hosting. Primary costs are:
1. Server hosting (~$20–50/month depending on traffic)
2. Stripe payment processing (2.9% + $0.30/transaction)
3. Store credits issued (up to 10% of revenue — capped, predictable)
4. Potential proxies or CAPTCHA bypass services if needed for scrapers (~$30–100/month)

### Key Growth Lever: Consumer Intent Leads
Intent leads are the highest-value product:
- **1.5× higher price** than equivalent directory leads
- **Zero acquisition cost** (homeowners submit themselves)
- **Higher buyer repeat rate** — contractors who buy intent leads and convert them become loyal repeat customers

Growing the consumer intent funnel (SEO, ad campaigns for homeowner acquisition) is the single highest-ROI investment for this business.

### Retention Economics
The bad lead guarantee + store credit system is a deliberate retention investment:
- Cost: up to 10% of one order (~$4.50 on a $45 order)
- Benefit: buyer returns for a second order (recovering cost on order 2)
- Industry benchmark: customer acquisition cost for a new B2B buyer is typically $30–100+
- The credit is only redeemable on a future purchase — it has zero cash value unless the buyer returns

---

## 11. Competitive Differentiation

| Feature | LeadGen | Typical Competitors |
|---|---|---|
| Self-serve, instant download | ✅ No sales call needed | ❌ Most require a call or demo |
| Free sample before buying | ✅ 5 real leads, no card required | ❌ Pay to see any data |
| ZIP + radius search | ✅ 5/10/25/50/100 mile radius | ❌ Usually city/state only |
| Quality score transparency | ✅ Visible to buyer before purchase | ❌ Hidden or unavailable |
| Consumer intent leads in same shop | ✅ Toggle filter | ❌ Separate products/platforms |
| Freshness guarantee (180-day) | ✅ Enforced at query level | ❌ Often sell stale data |
| Resale capping (max 5 sales) | ✅ Enforced in database, marketed | ❌ Often unlimited, rarely disclosed |
| Bad lead store credit | ✅ Automatic credit code, up to 10% back | ❌ No recourse offered |
| Bulk discount tiers | ✅ Up to 45% off | ✅ Common |
| Multiple scraper sources | ✅ YP + Superpages + Manta + BBB | ❌ Usually 1 source |
| No monthly contract | ✅ Pay per download | ❌ Usually required |

---

## 12. Suggested Improvements (Roadmap Ideas)

1. **Email marketing to past buyers** — buyer emails are now captured from Stripe; send re-engagement emails with new lead availability in their purchased industry/state
2. **Buyer accounts & purchase history** — allow repeat customers to log in and re-download past orders
3. **Subscription model** — monthly "lead pack" subscriptions for high-volume buyers; predictable recurring revenue
4. **API access** — charge a premium for programmatic lead access (CRM integrations, Zapier)
5. **Verified badge** — manually verified leads (phone confirmed, business still active) at 2× premium
6. **Lead alerts** — "notify me when new roofing leads in Austin are available" email opt-in
7. **Ad-supported homeowner portal** — contractor ads on the `/request-service` confirmation page
8. **Contractor directory** — free listing for contractors who buy leads, driving organic homeowner traffic
9. **Review/rating system** — buyers rate lead quality; high-rated lead sources get prioritized in scraper
10. **Geographic expansion** — Canada (provinces), UK postcodes

---

*This document reflects the platform as of March 2026. All pricing, multipliers, and feature details can be verified directly in the codebase at `backend/app/services/pricing.py`, `backend/app/routers/`, and `frontend/src/`.*
