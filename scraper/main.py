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

from database import SessionLocal
from dedup import already_exists
from models import Lead
from sources.base import ScrapedLead
from sources.bbb import BBBScraper
from sources.building_permits import BuildingPermitScraper
from sources.city_open_data import CityOpenDataScraper
from sources.manta import MantaScraper
from sources.superpages import SuperpagesScraper
from sources.yellowpages import YellowPagesScraper

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
TARGETS_PER_RUN = 50  # doubled from 20

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

# ── Location pool — all 50 states with expanded city coverage ─────────────────
# Cities represent all US municipalities 25,000+ population
LOCATIONS: dict[str, list[str]] = {
    "AL": ["Birmingham", "Montgomery", "Huntsville", "Mobile", "Tuscaloosa", "Hoover", "Dothan", "Auburn", "Decatur", "Madison", "Florence", "Gadsden", "Vestavia Hills", "Prattville", "Phenix City"],
    "AK": ["Anchorage", "Fairbanks", "Juneau", "Sitka", "Ketchikan", "Wasilla", "Kenai", "Kodiak"],
    "AZ": ["Phoenix", "Tucson", "Mesa", "Chandler", "Scottsdale", "Glendale", "Gilbert", "Tempe", "Peoria", "Surprise", "Yuma", "Avondale", "Goodyear", "Flagstaff", "Buckeye", "Lake Havasu City", "Casa Grande", "Sierra Vista", "Maricopa", "Oro Valley"],
    "AR": ["Little Rock", "Fort Smith", "Fayetteville", "Springdale", "Jonesboro", "Conway", "Rogers", "Bentonville", "Pine Bluff", "Hot Springs", "Benton", "Texarkana", "Sherwood", "Jacksonville"],
    "CA": ["Los Angeles", "San Diego", "San Jose", "San Francisco", "Fresno", "Sacramento", "Long Beach", "Oakland", "Bakersfield", "Anaheim", "Riverside", "Stockton", "Irvine", "Chula Vista", "Fremont", "San Bernardino", "Modesto", "Fontana", "Moreno Valley", "Glendale", "Huntington Beach", "Santa Ana", "Santa Clarita", "Garden Grove", "Oceanside", "Rancho Cucamonga", "Ontario", "Lancaster", "Elk Grove", "Corona", "Palmdale", "Salinas", "Pomona", "Hayward", "Escondido", "Torrance", "Sunnyvale", "Pasadena", "Orange", "Fullerton", "Thousand Oaks", "Visalia", "Simi Valley", "Concord", "Roseville", "Santa Rosa", "Vallejo", "Victorville", "El Monte", "Berkeley"],
    "CO": ["Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood", "Thornton", "Arvada", "Westminster", "Pueblo", "Boulder", "Highlands Ranch", "Centennial", "Castle Rock", "Loveland", "Broomfield", "Greeley", "Longmont", "Lone Tree", "Northglenn", "Commerce City"],
    "CT": ["Bridgeport", "New Haven", "Hartford", "Stamford", "Waterbury", "Norwalk", "Danbury", "New Britain", "West Hartford", "Greenwich", "Hamden", "Meriden", "Milford", "Stratford", "Middletown"],
    "DE": ["Wilmington", "Dover", "Newark", "Middletown", "Smyrna", "Milford", "Seaford", "Georgetown", "Elsmere"],
    "FL": ["Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg", "Hialeah", "Tallahassee", "Fort Lauderdale", "Cape Coral", "Pembroke Pines", "Hollywood", "Gainesville", "Miramar", "Palm Bay", "Clearwater", "Port St. Lucie", "Coral Springs", "West Palm Beach", "Lakeland", "Pompano Beach", "Davie", "Miami Gardens", "Boca Raton", "Deltona", "Sunrise", "Plantation", "Fort Myers", "Palm Coast", "Deerfield Beach", "Melbourne", "Largo", "Boynton Beach", "Miami Beach", "Brandon", "Spring Hill", "Kissimmee", "Daytona Beach", "Ocala", "Pensacola", "Sarasota"],
    "GA": ["Atlanta", "Augusta", "Columbus", "Macon", "Savannah", "Athens", "Sandy Springs", "Roswell", "Albany", "Warner Robins", "Alpharetta", "Marietta", "Smyrna", "Johns Creek", "Valdosta", "Brookhaven", "South Fulton", "Dunwoody", "Peachtree City", "Gainesville", "Stonecrest"],
    "HI": ["Honolulu", "Pearl City", "Hilo", "Kailua", "Waipahu", "Kaneohe", "Mililani Town", "Kahului", "Ewa Beach", "Mililani Mauka"],
    "ID": ["Boise", "Nampa", "Meridian", "Idaho Falls", "Pocatello", "Caldwell", "Coeur d'Alene", "Twin Falls", "Lewiston", "Post Falls", "Rexburg"],
    "IL": ["Chicago", "Aurora", "Rockford", "Joliet", "Naperville", "Springfield", "Peoria", "Elgin", "Waukegan", "Cicero", "Champaign", "Arlington Heights", "Evanston", "Decatur", "Schaumburg", "Bolingbrook", "Palatine", "Skokie", "Des Plaines", "Orland Park"],
    "IN": ["Indianapolis", "Fort Wayne", "Evansville", "South Bend", "Carmel", "Fishers", "Bloomington", "Hammond", "Gary", "Lafayette", "Muncie", "Terre Haute", "Noblesville", "Kokomo", "Anderson"],
    "IA": ["Des Moines", "Cedar Rapids", "Davenport", "Sioux City", "Iowa City", "Waterloo", "Ames", "Council Bluffs", "Dubuque", "West Des Moines", "Ankeny", "Waukee"],
    "KS": ["Wichita", "Overland Park", "Kansas City", "Topeka", "Olathe", "Lawrence", "Shawnee", "Manhattan", "Lenexa", "Salina", "Hutchinson"],
    "KY": ["Louisville", "Lexington", "Bowling Green", "Owensboro", "Covington", "Hopkinsville", "Richmond", "Florence", "Georgetown", "Henderson", "Elizabethtown"],
    "LA": ["New Orleans", "Baton Rouge", "Shreveport", "Lafayette", "Lake Charles", "Kenner", "Bossier City", "Monroe", "Alexandria", "Metairie", "Sulphur", "New Iberia"],
    "ME": ["Portland", "Lewiston", "Bangor", "South Portland", "Auburn", "Biddeford", "Augusta", "Saco"],
    "MD": ["Baltimore", "Frederick", "Rockville", "Gaithersburg", "Bowie", "Hagerstown", "Annapolis", "College Park", "Salisbury", "Columbia", "Germantown", "Silver Spring", "Waldorf", "Glen Burnie"],
    "MA": ["Boston", "Worcester", "Springfield", "Lowell", "Cambridge", "New Bedford", "Brockton", "Quincy", "Lynn", "Fall River", "Newton", "Lawrence", "Somerville", "Framingham", "Haverhill", "Waltham", "Malden", "Brookline", "Plymouth", "Medford"],
    "MI": ["Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor", "Lansing", "Flint", "Dearborn", "Livonia", "Westland", "Troy", "Farmington Hills", "Kalamazoo", "Wyoming", "Southfield", "Rochester Hills", "Taylor", "Pontiac", "St. Clair Shores", "Royal Oak"],
    "MN": ["Minneapolis", "Saint Paul", "Rochester", "Duluth", "Bloomington", "Brooklyn Park", "Plymouth", "Maple Grove", "Coon Rapids", "Burnsville", "Eden Prairie", "Edina", "Blaine", "Lakeville", "Minnetonka", "Apple Valley", "St. Cloud"],
    "MS": ["Jackson", "Gulfport", "Southaven", "Hattiesburg", "Biloxi", "Meridian", "Tupelo", "Olive Branch", "Greenville", "Horn Lake"],
    "MO": ["Kansas City", "Saint Louis", "Springfield", "Columbia", "Independence", "Lee's Summit", "O'Fallon", "Saint Joseph", "St. Peters", "Blue Springs", "Florissant", "Joplin", "Chesterfield", "Jefferson City"],
    "MT": ["Billings", "Missoula", "Great Falls", "Bozeman", "Butte", "Helena", "Kalispell"],
    "NE": ["Omaha", "Lincoln", "Bellevue", "Grand Island", "Kearney", "Fremont", "Hastings", "Norfolk"],
    "NV": ["Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks", "Carson City", "Enterprise", "Sunrise Manor", "Paradise", "Spring Valley"],
    "NH": ["Manchester", "Nashua", "Concord", "Derry", "Dover", "Rochester", "Salem", "Merrimack", "Londonderry"],
    "NJ": ["Newark", "Jersey City", "Paterson", "Elizabeth", "Trenton", "Clifton", "Camden", "Passaic", "Union City", "Bayonne", "East Orange", "Woodbridge", "Toms River", "Hamilton", "Edison"],
    "NM": ["Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe", "Roswell", "Farmington", "Clovis", "Hobbs", "Alamogordo"],
    "NY": ["New York City", "Buffalo", "Rochester", "Yonkers", "Syracuse", "Albany", "New Rochelle", "Mount Vernon", "Schenectady", "Utica", "White Plains", "Hempstead", "Troy", "Binghamton", "Freeport", "Valley Stream"],
    "NC": ["Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem", "Fayetteville", "Cary", "Wilmington", "High Point", "Concord", "Gastonia", "Jacksonville", "Asheville", "Chapel Hill", "Rocky Mount", "Burlington", "Huntersville", "Greenville", "Apex"],
    "ND": ["Fargo", "Bismarck", "Grand Forks", "Minot", "West Fargo", "Mandan", "Dickinson"],
    "OH": ["Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron", "Dayton", "Parma", "Canton", "Youngstown", "Lorain", "Hamilton", "Springfield", "Kettering", "Elyria", "Lakewood", "Cuyahoga Falls", "Euclid", "Middletown", "Newark", "Mentor"],
    "OK": ["Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Lawton", "Edmond", "Moore", "Midwest City", "Enid", "Stillwater", "Muskogee", "Owasso", "Bartlesville", "Shawnee"],
    "OR": ["Portland", "Salem", "Eugene", "Gresham", "Hillsboro", "Beaverton", "Bend", "Medford", "Springfield", "Corvallis", "Albany", "Tigard", "Lake Oswego", "Keizer"],
    "PA": ["Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading", "Scranton", "Bethlehem", "Lancaster", "Harrisburg", "Altoona", "York", "Wilkes-Barre", "Chester", "Easton", "State College"],
    "RI": ["Providence", "Cranston", "Warwick", "Pawtucket", "East Providence", "Woonsocket", "Newport", "Central Falls"],
    "SC": ["Columbia", "Charleston", "North Charleston", "Mount Pleasant", "Rock Hill", "Greenville", "Summerville", "Goose Creek", "Hilton Head Island", "Florence", "Spartanburg", "Myrtle Beach", "Sumter", "Anderson"],
    "SD": ["Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown", "Mitchell", "Yankton"],
    "TN": ["Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville", "Murfreesboro", "Jackson", "Franklin", "Johnson City", "Bartlett", "Hendersonville", "Kingsport", "Collierville", "Cleveland", "Smyrna", "Germantown"],
    "TX": ["Houston", "San Antonio", "Dallas", "Austin", "Fort Worth", "El Paso", "Arlington", "Corpus Christi", "Plano", "Lubbock", "Laredo", "Irving", "Garland", "Frisco", "McKinney", "Amarillo", "Grand Prairie", "Brownsville", "Pasadena", "Mesquite", "Killeen", "McAllen", "Carrollton", "Waco", "Denton", "Midland", "Odessa", "Abilene", "Beaumont", "Round Rock", "Richardson", "Tyler", "League City", "Allen", "Sugar Land", "Edinburg", "College Station", "Pearland", "Lewisville", "San Angelo"],
    "UT": ["Salt Lake City", "West Valley City", "Provo", "West Jordan", "Orem", "Sandy", "Ogden", "St. George", "Layton", "Millcreek", "Taylorsville", "Murray", "Logan", "Lehi", "South Jordan"],
    "VT": ["Burlington", "South Burlington", "Rutland", "Barre", "Montpelier", "Winooski", "St. Albans"],
    "VA": ["Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Newport News", "Alexandria", "Hampton", "Roanoke", "Portsmouth", "Suffolk", "Lynchburg", "Harrisonburg", "Charlottesville", "Danville", "Manassas", "Fredericksburg"],
    "WA": ["Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue", "Kent", "Everett", "Renton", "Kirkland", "Bellingham", "Kennewick", "Yakima", "Marysville", "Shoreline", "Richland", "Lakewood", "Redmond", "Pasco", "Federal Way", "Sammamish"],
    "WV": ["Charleston", "Huntington", "Parkersburg", "Morgantown", "Wheeling", "Weirton", "Fairmont"],
    "WI": ["Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine", "Appleton", "Waukesha", "Oshkosh", "Eau Claire", "Janesville", "West Allis", "La Crosse", "Sheboygan", "Wauwatosa", "Fond du Lac"],
    "WY": ["Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs", "Sheridan", "Green River"],
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
    """Filter LOCATIONS based on SCRAPER_INSTANCE env var."""
    if SCRAPER_INSTANCE == "east":
        return {s: cities for s, cities in LOCATIONS.items() if s in EAST_STATES}
    elif SCRAPER_INSTANCE == "west":
        return {s: cities for s, cities in LOCATIONS.items() if s in WEST_STATES}
    return LOCATIONS  # "all" — default single instance


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


def _build_scraper_pool() -> list[tuple]:
    """Build list of (scraper_instance, source_name) to rotate through."""
    pool = [
        (YellowPagesScraper(), "yellowpages"),
        (SuperpagesScraper(), "superpages"),
        (MantaScraper(), "manta"),
        (BBBScraper(), "bbb"),
        (CityOpenDataScraper(), "city_open_data"),
        # Building permits — consumer intent leads (homeowners actively in-market)
        # Rotates in every ~7th slot so ~14% of targets get permit data
        (BuildingPermitScraper(), "building_permits"),
        (BuildingPermitScraper(), "building_permits"),  # double weight for consumer intent
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

    try:
        for i, (canonical_industry, search_term, city, state) in enumerate(targets):
            scraper_obj, source_name = scrapers[i % len(scrapers)]
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
                )
                session.add(lead)
                new_count += 1

            try:
                session.commit()
            except IntegrityError:
                # Rare race condition with duplicate source_url across instances
                session.rollback()
                new_count = 0

            print(f"[scraper{instance_label}]   -> {new_count} new leads added")
            total_new += new_count

            key = f"{canonical_industry}|{city}|{state}"
            history[key] = datetime.now(timezone.utc).isoformat()
            _save_history(history)

            pause = random.uniform(20, 40)
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
        scheduler.add_job(run_scrape, "interval", hours=6)
        instance_label = f" [{SCRAPER_INSTANCE}]" if SCRAPER_INSTANCE != "all" else ""
        print(f"[scraper{instance_label}] Scheduler started — running every 6 hours.")
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
