"""
Superpages (superpages.com) scraper.

No API key required. Public business directory.
URL: https://www.superpages.com/search?search_terms={industry}&geo_location_terms={city}+{state}
Superpages tends to include street address and zip more reliably than YellowPages.
"""

import random
import re
import time
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from sources.base import BaseScraper, ScrapedLead

SP_BASE = "https://www.superpages.com"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]


def _make_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }


class SuperpagesScraper(BaseScraper):
    def scrape(self, industry: str, city: str, state: str, max_results: int = 100) -> list[ScrapedLead]:
        leads = []
        page = 1

        with httpx.Client(
            headers=_make_headers(),
            follow_redirects=True,
            timeout=20,
        ) as client:
            # Warm up with a homepage visit to get cookies
            try:
                client.get(SP_BASE, timeout=10)
                time.sleep(random.uniform(1.0, 2.5))
            except Exception:
                pass

            while len(leads) < max_results:
                url = (
                    f"{SP_BASE}/search?"
                    + urllib.parse.urlencode({
                        "search_terms": industry,
                        "geo_location_terms": f"{city}, {state}",
                        "pg": page,
                    })
                )

                client.headers.update({"User-Agent": random.choice(USER_AGENTS)})

                try:
                    resp = client.get(url)
                    if resp.status_code == 429:
                        wait = random.uniform(50, 100)
                        print(f"[sp] Rate limited (429), waiting {wait:.0f}s...")
                        time.sleep(wait)
                        resp = client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    print(f"[sp] HTTP {e.response.status_code} at page {page} — stopping")
                    break
                except httpx.HTTPError as e:
                    print(f"[sp] Request error at page {page}: {e}")
                    break

                page_leads = _parse_page(resp.text, industry, city, state)
                if not page_leads:
                    print(f"[sp] No results on page {page} — done")
                    break

                leads.extend(page_leads)
                print(f"[sp]   Page {page}: {len(page_leads)} leads (total so far: {len(leads)})")
                page += 1

                time.sleep(random.uniform(3.0, 6.0))

        return leads[:max_results]


def _parse_page(html: str, industry: str, search_city: str, state: str) -> list[ScrapedLead]:
    soup = BeautifulSoup(html, "lxml")
    leads = []

    # Superpages uses several container patterns
    cards = soup.select("div.listing-container, div.search-result, div[class*='listing']")
    if not cards:
        # Fallback — find any article or section with a business name link
        cards = soup.select("article.v-card, div.result")

    for card in cards:
        try:
            lead = _parse_card(card, industry, search_city, state)
            if lead:
                leads.append(lead)
        except Exception:
            continue

    return leads


def _parse_card(card, industry: str, search_city: str, state: str) -> ScrapedLead | None:
    # Business name
    name_el = card.select_one(
        "a.business-name, .business-name a, h3.listing-name a, "
        "h2.business-name, [class*='business-name'] a, span.business-name"
    )
    if not name_el:
        return None
    business_name = name_el.get_text(strip=True)
    if not business_name:
        return None

    # Source URL
    source_url = None
    href = name_el.get("href", "")
    if href:
        source_url = SP_BASE + href if href.startswith("/") else href

    # Phone
    phone = None
    phone_el = card.select_one(
        ".phone-number, [class*='phone'], a[href^='tel:'], .primary-phone"
    )
    if phone_el:
        raw_phone = phone_el.get_text(strip=True)
        if not raw_phone and phone_el.get("href", "").startswith("tel:"):
            raw_phone = phone_el["href"].replace("tel:", "")
        digits = re.sub(r"\D", "", raw_phone)
        if len(digits) == 11 and digits[0] == "1":
            digits = digits[1:]
        if len(digits) == 10:
            phone = digits

    # Street address
    street = None
    street_el = card.select_one(".street-address, [class*='street'], .address-line1")
    if street_el:
        street = street_el.get_text(strip=True)

    # City / state / zip
    city = search_city
    zip_code = None
    locality_el = card.select_one(
        ".city-state-zip, [class*='locality'], .address-city-state, "
        ".address-line2, [class*='city']"
    )
    if locality_el:
        raw = locality_el.get_text(strip=True)
        # Format: "Houston, TX 77001" or "Houston, TX"
        m = re.match(r'^(.+?),\s*[A-Z]{2}\s*(\d{5})?', raw.strip())
        if m:
            parsed_city = m.group(1).strip()
            if parsed_city:
                city = parsed_city
            zip_code = m.group(2)  # may be None

    # Full address
    full_address = None
    if street and city:
        full_address = f"{street}, {city}, {state}"
        if zip_code:
            full_address += f" {zip_code}"
    elif zip_code:
        full_address = f"{city}, {state} {zip_code}"

    # Website
    website = None
    website_el = card.select_one(
        "a.website-link, a[data-action='website'], a[class*='website'], "
        "a[href*='http'][class*='track']"
    )
    if website_el and website_el.get("href"):
        href = website_el["href"]
        if href.startswith("http") and SP_BASE not in href:
            website = href

    return ScrapedLead(
        business_name=business_name,
        industry=industry.lower(),
        city=city,
        state=state.upper(),
        website=website,
        phone=phone,
        source_url=source_url,
        zip_code=zip_code,
        full_address=full_address,
        source="superpages",
        lead_type="business",
    )
