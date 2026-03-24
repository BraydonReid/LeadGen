"""
Manta.com scraper.

No API key required. Free B2B business directory.
URL: https://www.manta.com/search?search_source=nav&term={industry}&location={city}%2C+{state}
Manta focuses on small business listings and often includes address + phone.
"""

import random
import re
import time
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from sources.base import BaseScraper, ScrapedLead
from utils import looks_like_address

MANTA_BASE = "https://www.manta.com"

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
        "Referer": "https://www.manta.com/",
    }


class MantaScraper(BaseScraper):
    def scrape(self, industry: str, city: str, state: str, max_results: int = 100) -> list[ScrapedLead]:
        leads = []
        page = 1

        with httpx.Client(
            headers=_make_headers(),
            follow_redirects=True,
            timeout=20,
        ) as client:
            try:
                client.get(MANTA_BASE, timeout=10)
                time.sleep(random.uniform(1.5, 3.0))
            except Exception:
                pass

            while len(leads) < max_results:
                params = {
                    "search_source": "nav",
                    "term": industry,
                    "location": f"{city}, {state}",
                }
                if page > 1:
                    params["pg"] = page

                url = f"{MANTA_BASE}/search?" + urllib.parse.urlencode(params)
                client.headers.update({"User-Agent": random.choice(USER_AGENTS)})

                try:
                    resp = client.get(url)
                    if resp.status_code == 429:
                        wait = random.uniform(50, 100)
                        print(f"[manta] Rate limited (429), waiting {wait:.0f}s...")
                        time.sleep(wait)
                        resp = client.get(url)
                    if resp.status_code == 404:
                        print(f"[manta] 404 on page {page} — done")
                        break
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    print(f"[manta] HTTP {e.response.status_code} at page {page} — stopping")
                    break
                except httpx.HTTPError as e:
                    print(f"[manta] Request error at page {page}: {e}")
                    break

                page_leads = _parse_page(resp.text, industry, city, state)
                if not page_leads:
                    print(f"[manta] No results on page {page} — done")
                    break

                leads.extend(page_leads)
                print(f"[manta]   Page {page}: {len(page_leads)} leads (total so far: {len(leads)})")
                page += 1

                time.sleep(random.uniform(3.0, 6.0))

        return leads[:max_results]


def _parse_page(html: str, industry: str, search_city: str, state: str) -> list[ScrapedLead]:
    soup = BeautifulSoup(html, "lxml")
    leads = []

    # Manta uses article tags or div containers for each listing
    cards = soup.select(
        "article.search-result, div.search-result-item, "
        "div[class*='CompanyResult'], li[class*='result']"
    )
    if not cards:
        # Fallback: find any block with a business name link
        cards = soup.select("div.company-info, article[data-company]")

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
        "a[class*='company-name'], h2 a, h3 a, "
        "[class*='name'] a, a[data-event-name]"
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
        source_url = MANTA_BASE + href if href.startswith("/") else href

    # Phone
    phone = None
    phone_el = card.select_one(
        "[class*='phone'], a[href^='tel:'], span[itemprop='telephone'], "
        "[data-tracking*='phone']"
    )
    if phone_el:
        raw = phone_el.get_text(strip=True)
        if not raw and phone_el.get("href", "").startswith("tel:"):
            raw = phone_el["href"].replace("tel:", "")
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 11 and digits[0] == "1":
            digits = digits[1:]
        if len(digits) == 10:
            phone = digits

    # Address components
    city = search_city
    zip_code = None
    street = None
    full_address = None

    address_el = card.select_one(
        "[class*='address'], address, [itemprop='address'], "
        "span[class*='location'], div[class*='location']"
    )
    if address_el:
        addr_text = address_el.get_text(separator=", ", strip=True)

        # Try to extract street
        street_el = address_el.select_one(
            "[itemprop='streetAddress'], [class*='street']"
        )
        if street_el:
            street = street_el.get_text(strip=True)

        # Extract city
        city_el = address_el.select_one(
            "[itemprop='addressLocality'], [class*='city']"
        )
        if city_el:
            parsed_city = city_el.get_text(strip=True)
            if parsed_city:
                city = parsed_city

        # Extract zip
        zip_match = re.search(r'\b(\d{5})\b', addr_text)
        if zip_match:
            zip_code = zip_match.group(1)

        if street and city:
            full_address = f"{street}, {city}, {state}"
            if zip_code:
                full_address += f" {zip_code}"

    # Website
    website = None
    website_el = card.select_one(
        "a[class*='website'], a[href*='http'][class*='url'], "
        "a[data-tracking*='website']"
    )
    if website_el and website_el.get("href"):
        href = website_el["href"]
        if href.startswith("http") and MANTA_BASE not in href:
            website = href

    # Contact name — Manta cards sometimes show owner/principal info
    contact_name = None
    for el in card.select("p, span, div, li"):
        text = el.get_text(" ", strip=True)
        low = text.lower()
        if ("owner" in low or "principal" in low or "contact:" in low) and len(text) < 120:
            name_part = re.sub(r"(?i)(owner|principal|contact)\s*[:\-]?\s*", "", text).strip()
            if (
                2 < len(name_part) < 60
                and not looks_like_address(name_part)
                and not any(kw in name_part.lower() for kw in ["owner", "principal", "contact", "http"])
            ):
                contact_name = name_part
                break

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
        contact_name=contact_name,
        source="manta",
        lead_type="business",
    )
