"""
Yellow Pages (YP.com) scraper.

No API key required. Free. Public business directory.
URL: https://www.yellowpages.com/search?search_terms={industry}&geo_location_terms={city}%2C+{state}
"""

import random
import re
import time
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from sources.base import BaseScraper, ScrapedLead

YP_BASE = "https://www.yellowpages.com"

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


class YellowPagesScraper(BaseScraper):
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
                client.get(YP_BASE, timeout=10)
                time.sleep(random.uniform(1.0, 2.0))
            except Exception:
                pass

            while len(leads) < max_results:
                url = (
                    f"{YP_BASE}/search?"
                    + urllib.parse.urlencode({
                        "search_terms": industry,
                        "geo_location_terms": f"{city}, {state}",
                        "page": page,
                    })
                )

                # Rotate user agent per request
                client.headers.update({"User-Agent": random.choice(USER_AGENTS)})

                try:
                    resp = client.get(url)
                    if resp.status_code == 429:
                        wait = random.uniform(45, 90)
                        print(f"[yp] Rate limited (429), waiting {wait:.0f}s...")
                        time.sleep(wait)
                        resp = client.get(url)
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    print(f"[yp] HTTP {e.response.status_code} at page {page} — stopping")
                    break
                except httpx.HTTPError as e:
                    print(f"[yp] Request error at page {page}: {e}")
                    break

                page_leads = _parse_page(resp.text, industry, city, state)
                if not page_leads:
                    print(f"[yp] No results on page {page} — done")
                    break

                leads.extend(page_leads)
                print(f"[yp]   Page {page}: {len(page_leads)} leads (total so far: {len(leads)})")
                page += 1

                # Polite delay between pages
                time.sleep(random.uniform(3.0, 6.0))

        return leads[:max_results]


def _parse_page(html: str, industry: str, search_city: str, state: str) -> list[ScrapedLead]:
    soup = BeautifulSoup(html, "lxml")
    leads = []

    cards = soup.select("div.result.organic, div.v-card")
    if not cards:
        cards = soup.select("[class*='result ']")

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
    name_el = card.select_one(".business-name span, .business-name, h2.n a")
    if not name_el:
        return None
    business_name = name_el.get_text(strip=True)
    if not business_name:
        return None

    # Source URL for dedup
    link_el = card.select_one("a.business-name")
    source_url = None
    if link_el and link_el.get("href"):
        href = link_el["href"]
        source_url = YP_BASE + href if href.startswith("/") else href

    # Phone
    phone = None
    phone_el = card.select_one(".phones.phone.primary, .phone")
    if phone_el:
        raw = phone_el.get_text(strip=True)
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 10:
            phone = digits

    # City + zip — try to parse from locality span, fall back to search city
    city = search_city
    zip_code = None
    locality_el = card.select_one(".locality")
    if locality_el:
        raw = locality_el.get_text(strip=True)
        # Format: "Houston, TX  77001" — city before comma, zip after state abbrev
        parts = raw.split(",")
        parsed_city = parts[0].strip()
        if parsed_city:
            city = parsed_city
        if len(parts) > 1:
            zip_match = re.search(r'\b(\d{5})\b', parts[1])
            if zip_match:
                zip_code = zip_match.group(1)

    # Website
    website = None
    website_el = card.select_one("a.track-visit-website")
    if website_el and website_el.get("href"):
        website = website_el["href"]

    return ScrapedLead(
        business_name=business_name,
        industry=industry.lower(),
        city=city,
        state=state.upper(),
        website=website,
        phone=phone,
        source_url=source_url,
        zip_code=zip_code,
        source="yellowpages",
        lead_type="business",
    )
