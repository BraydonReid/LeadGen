"""
Better Business Bureau (bbb.org) scraper.

No API key required. Public directory of accredited and rated businesses.
BBB listings include address, phone, accreditation status — high quality data.
URL: https://www.bbb.org/search?find_country=USA&find_text={industry}&find_loc={city}%2C+{state}
"""

import random
import re
import time
import urllib.parse

import httpx
from bs4 import BeautifulSoup

from sources.base import BaseScraper, ScrapedLead
from utils import looks_like_address

BBB_BASE = "https://www.bbb.org"

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
    }


class BBBScraper(BaseScraper):
    def scrape(self, industry: str, city: str, state: str, max_results: int = 100) -> list[ScrapedLead]:
        leads = []
        page = 1

        with httpx.Client(
            headers=_make_headers(),
            follow_redirects=True,
            timeout=25,
        ) as client:
            try:
                client.get(BBB_BASE, timeout=10)
                time.sleep(random.uniform(2.0, 4.0))
            except Exception:
                pass

            while len(leads) < max_results:
                params = {
                    "find_country": "USA",
                    "find_text": industry,
                    "find_loc": f"{city}, {state}",
                    "page": page,
                }
                url = f"{BBB_BASE}/search?" + urllib.parse.urlencode(params)
                client.headers.update({"User-Agent": random.choice(USER_AGENTS)})

                try:
                    resp = client.get(url)
                    if resp.status_code == 429:
                        wait = random.uniform(60, 120)
                        print(f"[bbb] Rate limited (429), waiting {wait:.0f}s...")
                        time.sleep(wait)
                        resp = client.get(url)
                    if resp.status_code in (404, 403):
                        print(f"[bbb] HTTP {resp.status_code} at page {page} — stopping")
                        break
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    print(f"[bbb] HTTP {e.response.status_code} at page {page} — stopping")
                    break
                except httpx.HTTPError as e:
                    print(f"[bbb] Request error at page {page}: {e}")
                    break

                page_leads = _parse_page(resp.text, industry, city, state)
                if not page_leads:
                    print(f"[bbb] No results on page {page} — done")
                    break

                leads.extend(page_leads)
                print(f"[bbb]   Page {page}: {len(page_leads)} leads (total so far: {len(leads)})")
                page += 1

                time.sleep(random.uniform(4.0, 8.0))

        return leads[:max_results]


def _parse_page(html: str, industry: str, search_city: str, state: str) -> list[ScrapedLead]:
    soup = BeautifulSoup(html, "lxml")
    leads = []

    # BBB search results are wrapped in various container elements
    cards = soup.select(
        "div[class*='SearchResult'], article[class*='result'], "
        "div[class*='search-result'], li[class*='result-item']"
    )
    if not cards:
        # Broader fallback
        cards = soup.select("div[data-businessid], div[data-testid*='search-result']")

    for card in cards:
        try:
            lead = _parse_card(card, industry, search_city, state)
            if lead:
                leads.append(lead)
        except Exception:
            continue

    return leads


def _parse_card(card, industry: str, search_city: str, state: str) -> ScrapedLead | None:
    # Business name — BBB uses h3 or h4 links in result cards
    name_el = card.select_one(
        "h3 a, h4 a, a[class*='business-name'], "
        "[class*='BusinessName'] a, a[class*='biz-name']"
    )
    if not name_el:
        return None
    business_name = name_el.get_text(strip=True)
    if not business_name:
        return None

    # Source URL — BBB profile pages have full data
    source_url = None
    href = name_el.get("href", "")
    if href:
        source_url = BBB_BASE + href if href.startswith("/") else href

    # Phone
    phone = None
    phone_el = card.select_one(
        "a[href^='tel:'], [class*='phone'], "
        "span[class*='Phone'], p[class*='phone']"
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

    # Address
    city = search_city
    zip_code = None
    street = None
    full_address = None

    addr_el = card.select_one(
        "address, [class*='Address'], [class*='address'], "
        "[class*='location'], p[class*='addr']"
    )
    if addr_el:
        addr_text = addr_el.get_text(separator=" ", strip=True)

        # Street
        street_el = addr_el.select_one(
            "[class*='street'], [class*='Street'], span:first-child"
        )
        if street_el:
            street = street_el.get_text(strip=True)

        # City from "City, ST ZIP" pattern
        locality_match = re.search(r'([A-Za-z\s]+),\s*([A-Z]{2})\s+(\d{5})?', addr_text)
        if locality_match:
            parsed_city = locality_match.group(1).strip()
            if parsed_city and len(parsed_city) > 1:
                city = parsed_city
            zip_code = locality_match.group(3)

        if street and city:
            full_address = f"{street}, {city}, {state}"
            if zip_code:
                full_address += f" {zip_code}"
        elif not street:
            zip_match = re.search(r'\b(\d{5})\b', addr_text)
            if zip_match:
                zip_code = zip_match.group(1)

    # Website — BBB profile cards sometimes show the business URL
    website = None
    website_el = card.select_one(
        "a[class*='website'], a[class*='Website'], "
        "a[href*='http'][class*='external']"
    )
    if website_el and website_el.get("href"):
        href = website_el["href"]
        if href.startswith("http") and BBB_BASE not in href:
            website = href

    # Contact name — BBB cards sometimes show a "Principal" or "Contact" label
    contact_name = None
    for el in card.select("p, span, div, li"):
        text = el.get_text(" ", strip=True)
        low = text.lower()
        if ("principal" in low or "contact:" in low or "owner:" in low) and len(text) < 120:
            name_part = re.sub(r"(?i)(principal|contact|owner)\s*[:\-]?\s*", "", text).strip()
            # Discard if it still contains a label word or looks like an address
            if (
                2 < len(name_part) < 60
                and not looks_like_address(name_part)
                and not any(kw in name_part.lower() for kw in ["principal", "contact", "owner", "http"])
            ):
                contact_name = name_part
                break

    # BBB Rating grade (A+, A, A-, B+, B, etc.)
    bbb_rating = None
    rating_el = card.select_one(
        "[class*='Rating'] [class*='grade'], [class*='rating-grade'], "
        "[class*='RatingLetter'], span[class*='grade'], [data-testid*='rating']"
    )
    if rating_el:
        raw_rating = rating_el.get_text(strip=True)
        if re.match(r"^[A-F][+-]?$", raw_rating):
            bbb_rating = raw_rating

    # BBB Accreditation badge
    bbb_accredited = None
    accredited_el = card.select_one(
        "[class*='accredited' i], [class*='Accredited'], "
        "img[alt*='Accredited' i], [data-testid*='accredited' i]"
    )
    if accredited_el:
        bbb_accredited = True

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
        source="bbb",
        lead_type="business",
        bbb_rating=bbb_rating,
        bbb_accredited=bbb_accredited,
    )
