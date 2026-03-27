"""
Lead scraper entry point.

Run once:
    python main.py

Run with scheduler (every 6 hours):
    python main.py --schedule

Multi-instance mode (east/west split via env var):
    SCRAPER_INSTANCE=east python main.py --schedule
    SCRAPER_INSTANCE=west python main.py --schedule

Each run selects TARGETS_PER_RUN combinations from a large pool of
industries × locations, always prioritizing the least-recently-scraped
combos so new territory is covered before repeating old ones.
Demand weighting ensures hot-selling industry × state combos get
scraped more often.
"""

import argparse
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy.exc import IntegrityError

from utils import looks_like_address, smart_title

from database import SessionLocal
from dedup import already_exists
from models import Lead
from sources.base import ScrapedLead
from sources.arcgis_permits import ArcGISPermitScraper
from sources.bbb import BBBScraper
from sources.building_permits import BuildingPermitScraper
from sources.city_open_data import CityOpenDataScraper
from sources.ckan_permits import CKANPermitScraper
from sources.code_violations import CodeViolationScraper
from sources.deed_transfers import DeedTransferScraper
from sources.manta import MantaScraper
from sources.superpages import SuperpagesScraper
from sources.tdlr import TDLRScraper
from sources.texas_sos_new_filings import TexasSOSScraper
from sources.yellowpages import YellowPagesScraper

# New intent scrapers — Texas-specific standalone scripts.
# Run these daily in addition to the main scraper loop:
#   python sources/texas_sos_new_filings.py --days 7
#   python sources/code_violations.py --days 30
#   python sources/deed_transfers.py --days 60
# They are also included in the scraper pool below (low weight — Texas cities only).

# Optional API sources — loaded only if keys are present
_yelp_scraper = None
_fsq_scraper = None

if os.environ.get("YELP_API_KEY"):
    try:
        from sources.yelp import YelpScraper
        from yelp_budget import should_use_yelp, record_calls, get_status as yelp_status
        _yelp_scraper = YelpScraper()
        print("[scraper] Yelp API source enabled (budget-managed)")
    except Exception as e:
        print(f"[scraper] Yelp source unavailable: {e}")
        def should_use_yelp(i, c): return False
        def record_calls(n): pass
        def yelp_status(): return {}
else:
    def should_use_yelp(i, c): return False
    def record_calls(n): pass
    def yelp_status(): return {}

if os.environ.get("FOURSQUARE_API_KEY"):
    try:
        from sources.foursquare import FoursquareScraper
        _fsq_scraper = FoursquareScraper()
        print("[scraper] Foursquare API source enabled")
    except Exception as e:
        print(f"[scraper] Foursquare source unavailable: {e}")

# Each instance gets its own history file so east/west don't clobber each other
_instance = os.environ.get("SCRAPER_INSTANCE", "all")
HISTORY_FILE = Path(f"/app/history/scrape_history_{_instance}.json")
TARGETS_PER_RUN = 100

# Multi-instance state split — set SCRAPER_INSTANCE=east or =west in env
# Each instance handles half the states, eliminating duplicate work
SCRAPER_INSTANCE = os.environ.get("SCRAPER_INSTANCE", "all").lower()
EAST_STATES = {
    "AL", "AR", "CT", "DE", "FL", "GA", "IL", "IN", "IA", "KY",
    "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "NH", "NJ",
    "NY", "NC", "ND", "OH", "PA", "RI", "SC", "SD", "TN", "VT",
    "VA", "WV", "WI",
}
WEST_STATES = {
    "AK", "AZ", "CA", "CO", "HI", "ID", "KS", "MT", "NE", "NV",
    "NM", "OK", "OR", "TX", "UT", "WA", "WY",
}


# ── Industry pool ─────────────────────────────────────────────────────────────
INDUSTRIES: dict[str, list[str]] = {
    # Home Exterior
    "roofing":              ["roofing", "roofing contractor", "roofer", "roof repair", "roof installation"],
    "siding":               ["siding contractor", "siding installation", "vinyl siding", "siding repair", "fiber cement siding"],
    "gutters":              ["gutter installation", "gutter cleaning", "gutter repair", "gutter guard installation"],
    "windows":              ["window installation", "window replacement", "window contractor", "window repair"],
    "painting":             ["painting contractor", "house painter", "exterior painting", "interior painting", "residential painter"],
    "pressure washing":     ["pressure washing", "power washing", "exterior cleaning", "house washing"],
    "masonry":              ["masonry contractor", "brick repair", "stone masonry", "brick laying", "tuckpointing"],
    "paving":               ["paving contractor", "asphalt paving", "driveway paving", "asphalt repair", "driveway resurfacing"],
    "fencing":              ["fence contractor", "fence installation", "fencing company", "wood fence", "vinyl fence installation"],
    "concrete":             ["concrete contractor", "concrete driveway", "concrete patio", "stamped concrete", "concrete repair"],

    # Home Interior
    "remodeling":           ["home remodeling", "kitchen remodeling", "bathroom remodeling", "general contractor", "home renovation"],
    "flooring":             ["flooring contractor", "hardwood flooring", "carpet installation", "tile installation", "laminate flooring"],
    "drywall":              ["drywall contractor", "drywall repair", "drywall installation", "drywall finishing"],
    "insulation":           ["insulation contractor", "spray foam insulation", "attic insulation", "blown-in insulation"],
    "waterproofing":        ["waterproofing contractor", "basement waterproofing", "crawl space waterproofing", "foundation waterproofing"],
    "cabinet installation": ["cabinet installation", "cabinet refacing", "kitchen cabinets", "custom cabinets"],
    "countertops":          ["countertop installation", "granite countertops", "quartz countertops", "countertop replacement"],
    "blinds and shutters":  ["blind installation", "shutter installation", "window treatments", "plantation shutters"],
    "closet organization":  ["closet organizer", "custom closet", "closet installation", "closet design"],
    "carpet cleaning":      ["carpet cleaning", "upholstery cleaning", "rug cleaning", "steam cleaning"],
    "air duct cleaning":    ["air duct cleaning", "dryer vent cleaning", "duct cleaning service", "HVAC duct cleaning"],
    "chimney":              ["chimney sweep", "chimney repair", "fireplace cleaning", "chimney inspection"],

    # Mechanical / Utilities
    "plumbing":             ["plumber", "plumbing contractor", "drain cleaning", "pipe repair", "emergency plumber"],
    "hvac":                 ["HVAC", "air conditioning repair", "heating and cooling", "AC repair", "furnace repair", "AC installation"],
    "electrician":          ["electrician", "electrical contractor", "electrical repair", "electrical service", "residential electrician"],
    "solar":                ["solar panels", "solar installation", "solar contractor", "solar energy", "residential solar"],
    "generator":            ["generator installation", "generator repair", "standby generator", "whole house generator"],
    "ev charger":           ["EV charger installation", "electric vehicle charger", "level 2 charger installation"],
    "septic":               ["septic service", "septic tank cleaning", "septic installation", "septic repair"],
    "well pump":            ["well pump repair", "well pump installation", "water well service", "well drilling"],
    "garage door":          ["garage door repair", "garage door installation", "garage door service", "garage door opener"],

    # Landscaping / Outdoor
    "landscaping":          ["landscaping", "lawn care", "lawn service", "landscape contractor", "lawn maintenance"],
    "tree service":         ["tree service", "tree removal", "tree trimming", "tree care", "stump grinding"],
    "irrigation":           ["irrigation contractor", "sprinkler installation", "sprinkler repair", "irrigation system"],
    "pool service":         ["pool service", "pool cleaning", "pool repair", "swimming pool contractor", "pool maintenance"],
    "pool installation":    ["pool installation", "inground pool contractor", "swimming pool installation"],
    "decking":              ["deck contractor", "deck installation", "deck repair", "wood deck", "composite deck"],
    "outdoor lighting":     ["outdoor lighting installation", "landscape lighting", "pathway lighting"],

    # Cleaning & Maintenance
    "cleaning":             ["cleaning service", "house cleaning", "maid service", "residential cleaning", "home cleaning"],
    "junk removal":         ["junk removal", "junk hauling", "debris removal", "trash removal", "estate cleanout"],
    "handyman":             ["handyman", "handyman service", "home repair", "property maintenance"],
    "mold remediation":     ["mold remediation", "mold removal", "mold testing", "black mold removal"],
    "restoration":          ["water damage restoration", "fire damage restoration", "flood restoration", "disaster restoration"],
    "foundation repair":    ["foundation repair", "foundation contractor", "structural repair", "pier and beam repair"],
    "demolition":           ["demolition contractor", "interior demolition", "structure demolition"],
    "excavation":           ["excavation contractor", "grading contractor", "land clearing", "site preparation"],

    # Pest & Animal
    "pest control":         ["pest control", "exterminator", "termite control", "rodent control", "bed bug treatment"],
    "wildlife removal":     ["wildlife removal", "animal control", "squirrel removal", "raccoon removal"],

    # Moving & Storage
    "moving":               ["moving company", "movers", "residential moving", "local movers", "long distance movers"],
    "storage":              ["self storage", "moving and storage", "portable storage"],

    # Security & Tech
    "security":             ["security system installation", "home security", "alarm system", "smart home security"],
    "it support":           ["IT support", "computer repair", "network setup", "tech support", "small business IT"],
    "smart home":           ["smart home installation", "home automation", "smart thermostat installation"],

    # Automotive
    "auto repair":          ["auto repair", "car repair", "mechanic", "auto mechanic", "car mechanic"],
    "auto detailing":       ["auto detailing", "car detailing", "mobile car detailing", "car wash detailing"],
    "towing":               ["towing service", "tow truck", "roadside assistance", "car towing"],
    "windshield repair":    ["windshield repair", "auto glass repair", "windshield replacement", "car glass repair"],

    # Health & Wellness
    "dentist":              ["dentist", "dental office", "family dentist", "cosmetic dentist"],
    "chiropractor":         ["chiropractor", "chiropractic", "back pain doctor", "spinal adjustment"],
    "physical therapy":     ["physical therapy", "physical therapist", "PT clinic", "sports rehabilitation"],
    "optometrist":          ["optometrist", "eye doctor", "vision care", "eye exam"],
    "massage therapy":      ["massage therapy", "massage therapist", "therapeutic massage", "deep tissue massage"],

    # Beauty & Personal Care
    "hair salon":           ["hair salon", "hair stylist", "barber shop", "hairdresser"],
    "nail salon":           ["nail salon", "nail technician", "manicure pedicure", "gel nails"],
    "spa":                  ["day spa", "beauty spa", "skin care spa", "facial spa"],

    # Pet Services
    "dog grooming":         ["dog grooming", "pet grooming", "mobile pet grooming", "dog groomer"],
    "dog training":         ["dog training", "dog trainer", "puppy training", "obedience training"],
    "pet sitting":          ["pet sitting", "dog walking", "pet boarding", "in-home pet care"],
    "veterinarian":         ["veterinarian", "vet clinic", "animal hospital", "pet clinic"],

    # Professional Services
    "real estate":          ["real estate agent", "realtor", "home buying agent", "listing agent"],
    "mortgage":             ["mortgage broker", "mortgage lender", "home loan", "refinancing"],
    "insurance":            ["insurance agent", "home insurance", "auto insurance broker", "insurance broker"],
    "accounting":           ["accountant", "bookkeeper", "bookkeeping service", "CPA", "small business accountant"],
    "tax preparation":      ["tax preparation", "tax preparer", "income tax service", "tax filing service"],
    "financial advisor":    ["financial advisor", "wealth management", "financial planner", "investment advisor"],
    "attorney":             ["attorney", "lawyer", "personal injury lawyer", "family law attorney", "estate planning attorney"],

    # Events & Hospitality
    "catering":             ["catering", "catering company", "catering service", "event catering"],
    "event planning":       ["event planner", "event planning", "wedding planner", "party planning"],
    "photography":          ["photographer", "photography studio", "wedding photographer", "portrait photographer"],
    "videography":          ["videographer", "video production", "wedding videographer", "corporate video"],
    "DJ":                   ["DJ service", "wedding DJ", "event DJ", "mobile DJ"],
    "printing":             ["printing service", "print shop", "business printing", "sign printing", "banner printing"],

    # Education & Tutoring
    "tutoring":             ["tutoring", "tutor", "academic tutoring", "math tutor", "reading tutor"],
    "music lessons":        ["music lessons", "guitar lessons", "piano lessons", "music teacher"],
    "driving school":       ["driving school", "driving lessons", "defensive driving", "driver education"],

    # Specialty Trades
    "locksmith":            ["locksmith", "lock repair", "emergency locksmith", "lock installation", "rekeying"],
    "appliance repair":     ["appliance repair", "refrigerator repair", "washer dryer repair", "dishwasher repair"],
    "glass repair":         ["glass repair", "glass installation", "shower door installation", "mirror installation"],
    "tile and grout":       ["tile installation", "tile repair", "grout cleaning", "bathroom tile", "backsplash tile"],
    "asbestos removal":     ["asbestos removal", "asbestos abatement", "asbestos testing"],
    "radon mitigation":     ["radon mitigation", "radon testing", "radon abatement"],
    "home inspection":      ["home inspector", "home inspection", "property inspection", "pre-listing inspection"],
    "surveying":            ["land surveyor", "property surveying", "boundary survey", "topographic survey"],
}

# ── Location pool — Texas-focused for maximum lead density and SEO ─────────────
# Every Texas city/CDP with 25,000+ population + key suburbs.
# Both scraper instances cover all of Texas; their separate history files
# ensure they naturally diversify across different city × industry combos.
LOCATIONS: dict[str, list[str]] = {
    "TX": [
        # Major metros
        "Houston", "San Antonio", "Dallas", "Austin", "Fort Worth", "El Paso",
        # DFW Metroplex
        "Arlington", "Plano", "Irving", "Garland", "Frisco", "McKinney",
        "Grand Prairie", "Mesquite", "Carrollton", "Denton", "Richardson",
        "Lewisville", "Allen", "Flower Mound", "North Richland Hills",
        "Mansfield", "Euless", "Bedford", "Haltom City", "Grapevine",
        "Cedar Hill", "Rowlett", "DeSoto", "Duncanville", "Burleson",
        "Waxahachie", "Wylie", "Sachse", "Murphy", "Coppell", "Keller",
        "Southlake", "Colleyville", "Lewisville", "Denton", "Rockwall",
        # Houston Metro
        "Pasadena", "Pearland", "League City", "Sugar Land", "Baytown",
        "Missouri City", "Conroe", "Spring", "The Woodlands", "Katy",
        "Humble", "Atascocita", "Cypress", "Friendswood", "Stafford",
        "Rosenberg", "Galveston", "Texas City", "La Porte", "Deer Park",
        "Channelview", "Kingwood", "Tomball", "Porter",
        # Austin Metro
        "Round Rock", "Cedar Park", "Pflugerville", "Georgetown",
        "San Marcos", "Kyle", "Buda", "Leander", "Hutto", "Lakeway",
        "Cedar Park", "Bastrop", "Lockhart",
        # San Antonio Metro
        "New Braunfels", "Schertz", "Converse", "Universal City",
        "Live Oak", "Leon Valley", "Helotes",
        # Other major Texas cities
        "Corpus Christi", "Lubbock", "Laredo", "Amarillo", "Brownsville",
        "Killeen", "McAllen", "Waco", "Midland", "Odessa", "Abilene",
        "Beaumont", "Tyler", "Edinburg", "College Station", "San Angelo",
        "Wichita Falls", "Longview", "Harlingen", "Temple", "Bryan",
        "Mission", "Pharr", "Port Arthur", "Victoria", "Texarkana",
        "Abilene", "Lufkin", "Nacogdoches", "Sherman", "Wichita Falls",
        "Greenville", "Marshall", "Big Spring", "Kerrville", "San Marcos",
        "Del Rio", "Eagle Pass", "Laredo", "McAllen",
    ],
}


def normalize_phone(raw: str | None) -> str | None:
    """Normalize to (XXX) XXX-XXXX. Returns None if not a valid 10-digit US number."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def _clean_lead(s: ScrapedLead) -> ScrapedLead:
    """
    Sanitize all text fields before saving:
    - Clear contact_name if it contains a street address or a business entity suffix
    - Clear business_name if it's a street address on a business-type lead
    - Normalize whitespace throughout
    """
    # --- contact_name ---
    if s.contact_name:
        cn = s.contact_name.strip()
        # Wipe if it looks like a street address
        if looks_like_address(cn):
            cn = None
        # Wipe if it's clearly a company name, not a person
        elif any(kw in cn.lower() for kw in [" llc", " inc", " corp", " ltd", " lp", " llp", " co.", " co,"]):
            cn = None
        # Normalize whitespace
        s.contact_name = " ".join(cn.split()) if cn else None

    # --- business_name (business-type leads only) ---
    # Permit leads intentionally store the property address in business_name — skip cleaning those
    if s.lead_type == "business" and s.business_name:
        bn = s.business_name.strip()
        if looks_like_address(bn):
            bn = ""
        s.business_name = " ".join(bn.split()) if bn else ""

    # --- normalize whitespace on remaining fields ---
    if s.business_name:
        s.business_name = " ".join(s.business_name.split())

    return s


def calculate_quality_score(s: ScrapedLead) -> int:
    """
    Score 0–100 based on data completeness + reputation signals.
    Review data (from Yelp/Foursquare) boosts scores — established businesses
    with many positive reviews are more actionable leads.
    """
    score = 0
    # Contact completeness
    if s.phone:
        score += 25
    if s.email:
        score += 20
    if s.website:
        score += 15
    if s.full_address or s.zip_code:
        score += 10
    if s.contact_name:
        score += 5

    # Reputation signals — key differentiator vs Apollo/ZoomInfo
    if s.review_count:
        if s.review_count >= 100:
            score += 15
        elif s.review_count >= 25:
            score += 10
        elif s.review_count >= 5:
            score += 5

    if s.yelp_rating:
        if s.yelp_rating >= 4.5:
            score += 10
        elif s.yelp_rating >= 4.0:
            score += 6
        elif s.yelp_rating >= 3.5:
            score += 3

    # Years in business signal (from government/license data)
    # Note: for consumer permit leads, years_in_business = days since permit issued
    if s.lead_type == "consumer":
        # Consumer intent: freshness of permit is the key signal
        days_since_permit = s.years_in_business or 999
        if days_since_permit <= 7:
            score += 15   # red hot — permit issued this week
        elif days_since_permit <= 30:
            score += 10
        elif days_since_permit <= 60:
            score += 5
    elif s.years_in_business:
        if s.years_in_business >= 10:
            score += 5
        elif s.years_in_business >= 3:
            score += 3

    return min(100, score)


def _load_history() -> dict:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_history(history: dict):
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def _get_active_locations() -> dict[str, list[str]]:
    """Texas-focused: both instances cover all of Texas.
    The separate history files (scrape_history_east.json / scrape_history_west.json)
    ensure the two instances naturally diversify across different city × industry combos.
    """
    return LOCATIONS


def _select_targets(history: dict) -> list[tuple[str, str, str, str]]:
    """
    Build the full candidate pool (industry × city × state), then pick
    TARGETS_PER_RUN entries ensuring industry diversity AND demand weighting.
    Returns list of (canonical_industry, search_term, city, state).
    """
    # Load demand weights — falls back to {} if unavailable
    try:
        from demand_weights import get_demand_weights
        weights = get_demand_weights()
    except Exception:
        weights = {}

    if weights:
        print(f"[scraper] Demand weights loaded for {len(weights)} industry×state combos")

    active_locations = _get_active_locations()

    by_industry: dict[str, list[tuple]] = defaultdict(list)
    for canonical, terms in INDUSTRIES.items():
        for state, cities in active_locations.items():
            for city in cities:
                key = f"{canonical}|{city}|{state}"
                last_scraped = history.get(key, "1970-01-01T00:00:00")
                demand_w = weights.get((canonical.lower(), state.upper()), 1.0)
                by_industry[canonical].append((last_scraped, -demand_w, terms, city, state))

    for combos in by_industry.values():
        combos.sort(key=lambda x: (x[0], x[1]))

    industries = list(by_industry.keys())
    random.shuffle(industries)

    selected = []
    round_idx = 0
    while len(selected) < TARGETS_PER_RUN:
        made_progress = False
        for ind in industries:
            if len(selected) >= TARGETS_PER_RUN:
                break
            pool = by_industry[ind]
            if round_idx < len(pool):
                _, _demand, terms, city, state = pool[round_idx]
                search_term = random.choice(terms)
                selected.append((ind, search_term, city, state))
                made_progress = True
        if not made_progress:
            break
        round_idx += 1

    random.shuffle(selected)
    return selected


# Cities with public permit open data — building_permits scraper only works here.
# When a building_permits slot comes up but the selected city isn't in this list,
# redirect to the next permit city so every permit slot actually generates data.
PERMIT_CITIES: list[tuple[str, str]] = [
    # Texas — 4 verified live permit APIs with contact name fields
    ("Dallas", "TX"),        # Socrata   — daily updates, contractor field
    ("Austin", "TX"),        # Socrata   — contractor_full_name, current 2026 data
    ("San Antonio", "TX"),   # CKAN      — PRIMARY CONTACT field, updated Jan 2026
    ("Fort Worth", "TX"),    # ArcGIS    — Owner_Full_Name, live daily updates 2026
    ("Dallas", "TX"),        # extra weight so TX is ~35% of all permit slots
    ("Fort Worth", "TX"),    # extra weight for FW — 4th largest TX city
    # Supplemental cities with verified live data
    ("Chicago", "IL"),
    ("New York City", "NY"),
    ("Seattle", "WA"),
    ("Boston", "MA"),
    ("Pittsburgh", "PA"),
    ("Philadelphia", "PA"),
    ("Raleigh", "NC"),
    ("Minneapolis", "MN"),
    ("Nashville", "TN"),
]
_PERMIT_CITIES_LOWER = {c.lower() for c, _ in PERMIT_CITIES}

# Which scraper handles which city — used to route permit slots correctly
from sources.building_permits import PERMIT_ENDPOINTS as _SOCRATA_CFG
from sources.ckan_permits import CKAN_ENDPOINTS as _CKAN_CFG
from sources.arcgis_permits import ARCGIS_ENDPOINTS as _ARCGIS_CFG

_SOCRATA_CITIES_LOWER = {city for city, _ in _SOCRATA_CFG}
_CKAN_CITIES_LOWER = {city for city, _ in _CKAN_CFG}
_ARCGIS_CITIES_LOWER = {city for city, _ in _ARCGIS_CFG}

# Singleton instances reused across all permit routing decisions
_permit_scraper_socrata = BuildingPermitScraper()
_permit_scraper_ckan = CKANPermitScraper()
_permit_scraper_arcgis = ArcGISPermitScraper()
_code_violation_scraper = CodeViolationScraper()
_deed_transfer_scraper = DeedTransferScraper()
_tx_sos_scraper = TexasSOSScraper()


def _build_scraper_pool() -> list[tuple]:
    """Build list of (scraper_instance, source_name) to rotate through."""
    pool = [
        (YellowPagesScraper(), "yellowpages"),
        (SuperpagesScraper(), "superpages"),
        (MantaScraper(), "manta"),
        (BBBScraper(), "bbb"),
        (CityOpenDataScraper(), "city_open_data"),
        # TDLR — state-licensed TX contractor businesses (electrician, well pump)
        # 12,000+ TX electrical contractors with verified address + phone
        (TDLRScraper(), "tdlr"),
        # Building permits — consumer intent (homeowners actively in-market).
        # Uses a placeholder; the actual scraper is selected in run_scrape()
        # based on which city is chosen, routing to Socrata/CKAN/ArcGIS as needed.
        (None, "building_permits"),
        (None, "building_permits"),  # double weight → ~22% of slots = consumer leads
        # New intent sources — TX only, handled via special routing block in run_scrape()
        (None, "code_violations"),   # Dallas/Houston/Austin code enforcement
        (None, "deed_transfers"),    # new homeowner deed transfers
    ]
    if _yelp_scraper:
        pool.append((_yelp_scraper, "yelp"))
    if _fsq_scraper:
        pool.append((_fsq_scraper, "foursquare"))
    return pool


def run_scrape():
    history = _load_history()
    targets = _select_targets(history)

    active_locations = _get_active_locations()
    total_combos = sum(len(cities) for cities in active_locations.values()) * len(INDUSTRIES)
    scraped_count = len(history)
    instance_label = f" [{SCRAPER_INSTANCE}]" if SCRAPER_INSTANCE != "all" else ""
    print(f"[scraper{instance_label}] Starting run — {len(targets)} targets selected")
    print(f"[scraper{instance_label}] Coverage: {scraped_count}/{total_combos} combos scraped at least once")

    scrapers = _build_scraper_pool()
    session = SessionLocal()
    total_new = 0
    _permit_city_idx = 0  # cycles through PERMIT_CITIES for building_permits fallback

    try:
        for i, (canonical_industry, search_term, city, state) in enumerate(targets):
            scraper_obj, source_name = scrapers[i % len(scrapers)]

            # For building_permits: redirect to a supported permit city if needed,
            # then route to the correct scraper (Socrata / CKAN / ArcGIS).
            if source_name == "building_permits":
                if city.lower() not in _PERMIT_CITIES_LOWER:
                    city, state = PERMIT_CITIES[_permit_city_idx % len(PERMIT_CITIES)]
                    _permit_city_idx += 1
                city_key = city.lower()
                if city_key in _SOCRATA_CITIES_LOWER:
                    scraper_obj = _permit_scraper_socrata
                elif city_key in _CKAN_CITIES_LOWER:
                    scraper_obj = _permit_scraper_ckan
                elif city_key in _ARCGIS_CITIES_LOWER:
                    scraper_obj = _permit_scraper_arcgis
                else:
                    scraper_obj = _permit_scraper_socrata  # fallback

            # New intent scrapers — redirect to a supported TX city
            _TX_INTENT_CITIES = ["Dallas", "Houston", "Austin"]
            if source_name == "code_violations":
                if state != "TX" or city not in _TX_INTENT_CITIES:
                    city, state = random.choice([("Dallas", "TX"), ("Houston", "TX"), ("Austin", "TX")])
                scraper_obj = _code_violation_scraper

            if source_name == "deed_transfers":
                if state != "TX":
                    city, state = random.choice([("Houston", "TX"), ("Dallas", "TX"), ("Austin", "TX")])
                scraper_obj = _deed_transfer_scraper

            # For Yelp: check budget and whether this combo is worth a Yelp call
            if source_name == "yelp":
                if not should_use_yelp(canonical_industry, city):
                    # Fall back to yellowpages for this target instead
                    scraper_obj, source_name = scrapers[0]

            print(f"[scraper{instance_label}] [{source_name}] '{search_term}' in {city}, {state}  (industry: {canonical_industry})", flush=True)
            try:
                if source_name == "yelp" and hasattr(scraper_obj, "scrape_with_count"):
                    scraped, calls_used = scraper_obj.scrape_with_count(search_term, city, state, max_results=100)
                    if calls_used > 0:
                        record_calls(calls_used)
                        st = yelp_status()
                        print(f"[yelp-api] {calls_used} call(s) — monthly: {st.get('monthly_used')}/{st.get('monthly_used',0)+st.get('monthly_remaining',0)} | daily: {st.get('daily_used')}/{st.get('daily_used',0)+st.get('daily_remaining',0)}")
                else:
                    scraped = scraper_obj.scrape(search_term, city, state, max_results=100)
            except Exception as e:
                print(f"[scraper{instance_label}] Error scraping {source_name}: {e}")
                continue

            new_count = 0
            for s in scraped:
                s = _clean_lead(s)
                if not s.business_name:
                    continue  # cleaning wiped the name — skip
                normalized_phone = normalize_phone(s.phone)
                if already_exists(session, s.source_url, s.business_name, normalized_phone, s.website, s.state):
                    continue

                quality = calculate_quality_score(ScrapedLead(
                    business_name=s.business_name, industry=s.industry,
                    city=s.city, state=s.state, website=s.website,
                    email=s.email, phone=normalized_phone,
                    zip_code=s.zip_code, full_address=s.full_address,
                    contact_name=s.contact_name,
                    yelp_rating=s.yelp_rating,
                    review_count=s.review_count,
                    years_in_business=s.years_in_business,
                ))

                lead = Lead(
                    business_name=s.business_name,
                    industry=canonical_industry,
                    city=s.city,
                    state=s.state,
                    website=s.website,
                    email=s.email,
                    phone=normalized_phone,
                    source_url=s.source_url,
                    zip_code=s.zip_code,
                    full_address=s.full_address,
                    contact_name=s.contact_name,
                    quality_score=quality,
                    source=s.source or source_name,
                    lead_type=s.lead_type or "business",
                    yelp_rating=s.yelp_rating,
                    review_count=s.review_count,
                    years_in_business=s.years_in_business,
                    bbb_rating=s.bbb_rating,
                    bbb_accredited=s.bbb_accredited,
                )
                session.add(lead)
                new_count += 1

            try:
                session.commit()
            except IntegrityError:
                # Rare race condition with duplicate source_url across instances
                session.rollback()
                new_count = 0
            except Exception as db_err:
                # DB connection lost mid-run (Docker network blip) — reconnect and continue
                print(f"[scraper{instance_label}] DB error, reconnecting: {db_err}")
                try:
                    session.close()
                except Exception:
                    pass
                time.sleep(5)
                session = SessionLocal()
                new_count = 0

            print(f"[scraper{instance_label}]   -> {new_count} new leads added")
            total_new += new_count

            key = f"{canonical_industry}|{city}|{state}"
            history[key] = datetime.now(timezone.utc).isoformat()
            _save_history(history)

            pause = random.uniform(10, 20)
            print(f"[scraper{instance_label}] Pausing {pause:.0f}s...")
            time.sleep(pause)

    finally:
        session.close()

    print(f"[scraper{instance_label}] Run complete. Total new leads this run: {total_new}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--schedule", action="store_true", help="Run every 6 hours continuously")
    args = parser.parse_args()

    if args.schedule:
        scheduler = BlockingScheduler()
        scheduler.add_job(run_scrape, "interval", hours=3)
        instance_label = f" [{SCRAPER_INSTANCE}]" if SCRAPER_INSTANCE != "all" else ""
        print(f"[scraper{instance_label}] Scheduler started — running every 3 hours.")
        run_scrape()
        try:
            scheduler.start()
        except KeyboardInterrupt:
            print(f"[scraper{instance_label}] Stopped.")
            sys.exit(0)
    else:
        run_scrape()


if __name__ == "__main__":
    main()
