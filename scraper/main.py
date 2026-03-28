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

# ── Location pool — every Texas city/town with meaningful business activity ─────
# Covers all major metros, suburbs, regional cities, and smaller towns statewide.
# Both scraper instances cover all of Texas; their separate history files
# ensure they naturally diversify across different city × industry combos.
LOCATIONS: dict[str, list[str]] = {
    "TX": [
        # ── Major metros ──────────────────────────────────────────────────────
        "Houston", "San Antonio", "Dallas", "Austin", "Fort Worth", "El Paso",

        # ── DFW Metroplex ─────────────────────────────────────────────────────
        "Arlington", "Plano", "Irving", "Garland", "Frisco", "McKinney",
        "Grand Prairie", "Mesquite", "Carrollton", "Denton", "Richardson",
        "Lewisville", "Allen", "Flower Mound", "North Richland Hills",
        "Mansfield", "Euless", "Bedford", "Haltom City", "Grapevine",
        "Cedar Hill", "Rowlett", "DeSoto", "Duncanville", "Burleson",
        "Waxahachie", "Wylie", "Sachse", "Murphy", "Coppell", "Keller",
        "Southlake", "Colleyville", "Rockwall", "Prosper", "Celina",
        "Anna", "Melissa", "Princeton", "Royse City", "Fate", "Forney",
        "Seagoville", "Balch Springs", "Farmers Branch", "Addison",
        "University Park", "Highland Park", "Roanoke", "Trophy Club",
        "Azle", "Lake Worth", "White Settlement", "Forest Hill",
        "Everman", "Crowley", "Midlothian", "Alvarado", "Cleburne",
        "Joshua", "Granbury", "Weatherford", "Mineral Wells",
        "Stephenville", "Hillsboro", "Ennis", "Corsicana",
        "Terrell", "Kaufman", "Canton", "Gunter", "Denison",
        "Sherman", "Gainesville", "Decatur", "Greenville", "Sulphur Springs",
        "Mount Pleasant", "Paris", "Bonham",

        # ── Houston Metro ─────────────────────────────────────────────────────
        "Pasadena", "Pearland", "League City", "Sugar Land", "Baytown",
        "Missouri City", "Conroe", "Spring", "The Woodlands", "Katy",
        "Humble", "Atascocita", "Cypress", "Friendswood", "Stafford",
        "Rosenberg", "Galveston", "Texas City", "La Porte", "Deer Park",
        "Channelview", "Kingwood", "Tomball", "Porter", "Magnolia",
        "Montgomery", "Alvin", "Angleton", "Lake Jackson", "Clute",
        "Freeport", "El Campo", "Wharton", "Bay City", "Brenham",
        "Navasota", "Huntsville", "Livingston", "Cleveland", "Dayton",
        "Liberty", "La Marque", "South Houston", "Galena Park",

        # ── Austin Metro ──────────────────────────────────────────────────────
        "Round Rock", "Cedar Park", "Pflugerville", "Georgetown",
        "San Marcos", "Kyle", "Buda", "Leander", "Hutto", "Lakeway",
        "Bastrop", "Lockhart", "Taylor", "Elgin", "Marble Falls",
        "Burnet", "Wimberley", "Dripping Springs", "Bee Cave",
        "Luling", "Seguin",

        # ── San Antonio Metro ─────────────────────────────────────────────────
        "New Braunfels", "Schertz", "Converse", "Universal City",
        "Live Oak", "Leon Valley", "Helotes", "Boerne", "Bulverde",
        "Pleasanton", "Floresville", "Hondo", "Castroville",
        "Fredericksburg", "Kerrville", "Comfort", "Pearsall",

        # ── Corpus Christi / Coastal Bend ────────────────────────────────────
        "Corpus Christi", "Portland", "Aransas Pass", "Rockport",
        "Sinton", "Robstown", "Calallen",

        # ── Rio Grande Valley ─────────────────────────────────────────────────
        "McAllen", "Edinburg", "Mission", "Pharr", "Harlingen",
        "Brownsville", "Weslaco", "San Benito", "Donna", "Alton",
        "Palmview", "San Juan", "Hidalgo", "Mercedes", "La Feria",
        "Rio Grande City", "Roma", "Zapata",

        # ── Laredo / South Texas ──────────────────────────────────────────────
        "Laredo", "Eagle Pass", "Del Rio", "Uvalde", "Cotulla",
        "Crystal City", "Carrizo Springs", "Dilley",

        # ── Coastal / Victoria area ───────────────────────────────────────────
        "Victoria", "Port Lavaca", "Cuero", "Yoakum", "Gonzales",
        "Beeville", "Alice", "Kingsville",

        # ── Central Texas ─────────────────────────────────────────────────────
        "Waco", "Temple", "Killeen", "Bryan", "College Station",
        "Belton", "Copperas Cove", "Harker Heights", "Lampasas",
        "Gatesville", "Mexia", "Palestine", "Athens",
        "Jacksonville",
        "Brownwood", "Cisco", "Breckenridge",

        # ── East Texas ────────────────────────────────────────────────────────
        "Tyler", "Longview", "Texarkana", "Marshall", "Kilgore",
        "Gladewater", "Henderson", "Carthage", "Center",
        "Nacogdoches", "Lufkin", "Jasper", "Woodville",
        "Diboll", "Rusk", "Crockett",
        "Orange", "Port Arthur", "Beaumont",
        "Lumberton", "Nederland", "Port Neches", "Groves", "Vidor",
        "Silsbee",

        # ── North Texas ───────────────────────────────────────────────────────
        "Wichita Falls", "Vernon", "Graham", "Jacksboro",
        "Bowie", "Henrietta", "Burkburnett",

        # ── West Texas ────────────────────────────────────────────────────────
        "Midland", "Odessa", "San Angelo", "Abilene", "Big Spring",
        "Snyder", "Colorado City", "Sweetwater",
        "Monahans", "Pecos", "Fort Stockton", "Alpine", "Marfa",
        "Van Horn", "Ozona", "Sonora", "Junction",
        "Llano", "Mason", "Andrews", "Seminole", "Kermit",
        "Lamesa", "Plainview",

        # ── Panhandle / South Plains ──────────────────────────────────────────
        "Amarillo", "Canyon", "Hereford", "Pampa", "Borger",
        "Lubbock", "Levelland", "Brownfield", "Post",
        "Floydada", "Lockney", "Littlefield", "Muleshoe",
        "Dumas", "Dalhart", "Stratford", "Perryton",
        "Spearman", "Canadian", "Clarendon", "Childress",
        "Memphis", "Wellington", "Shamrock", "Tulia",
    ],

    # ── Alabama ───────────────────────────────────────────────────────────────
    "AL": [
        "Birmingham", "Montgomery", "Huntsville", "Mobile", "Tuscaloosa",
        "Hoover", "Dothan", "Auburn", "Decatur", "Madison", "Florence",
        "Gadsden", "Vestavia Hills", "Prattville", "Phenix City", "Alabaster",
        "Bessemer", "Enterprise", "Opelika", "Homewood", "Northport",
        "Anniston", "Prichard", "Athens", "Daphne", "Pelham", "Oxford",
        "Albertville", "Selma", "Mountain Brook", "Trussville", "Talladega",
        "Cullman", "Fairhope", "Jasper", "Foley", "Muscle Shoals",
        "Sheffield", "Scottsboro", "Fort Payne", "Helena", "Saraland",
        "Hartselle", "Millbrook", "Irondale", "Ozark", "Brewton",
        "Demopolis", "Sylacauga", "Wetumpka", "Childersburg", "Pell City",
        "Gardendale", "Hueytown", "Center Point", "Fultondale",
    ],

    # ── Alaska ────────────────────────────────────────────────────────────────
    "AK": [
        "Anchorage", "Fairbanks", "Juneau", "Sitka", "Ketchikan",
        "Wasilla", "Kenai", "Kodiak", "Palmer", "Homer", "Soldotna",
        "Valdez", "Bethel",
    ],

    # ── Arizona ───────────────────────────────────────────────────────────────
    "AZ": [
        "Phoenix", "Tucson", "Mesa", "Chandler", "Scottsdale", "Gilbert",
        "Glendale", "Tempe", "Peoria", "Surprise", "Yuma", "Avondale",
        "Goodyear", "Flagstaff", "Buckeye", "Maricopa", "Casa Grande",
        "Lake Havasu City", "Sierra Vista", "Prescott", "Bullhead City",
        "Prescott Valley", "Apache Junction", "El Mirage", "Kingman",
        "Queen Creek", "San Tan Valley", "Fountain Hills", "Oro Valley",
        "Sahuarita", "Florence", "Coolidge", "Douglas", "Nogales",
        "Show Low", "Sedona", "Wickenburg", "Tolleson", "Cottonwood",
        "Camp Verde", "Globe", "Payson", "Safford", "Benson", "Bisbee",
        "Winslow", "Holbrook", "Page", "Kayenta",
    ],

    # ── Arkansas ──────────────────────────────────────────────────────────────
    "AR": [
        "Little Rock", "Fort Smith", "Fayetteville", "Springdale",
        "Jonesboro", "North Little Rock", "Conway", "Rogers", "Pine Bluff",
        "Bentonville", "Hot Springs", "Benton", "Sherwood", "Jacksonville",
        "Russellville", "Bella Vista", "West Memphis", "Paragould", "Cabot",
        "Searcy", "Van Buren", "El Dorado", "Maumelle", "Siloam Springs",
        "Bryant", "Harrison", "Mountain Home", "Forrest City", "Camden",
        "Batesville", "Marion", "Hope", "Arkadelphia", "Monticello",
        "Blytheville", "Hot Springs Village", "Texarkana", "Stuttgart",
        "Magnolia", "Morrilton", "Clarksville", "Pocahontas",
    ],

    # ── California ────────────────────────────────────────────────────────────
    "CA": [
        "Los Angeles", "San Diego", "San Jose", "San Francisco", "Fresno",
        "Sacramento", "Long Beach", "Oakland", "Bakersfield", "Anaheim",
        "Santa Ana", "Riverside", "Stockton", "Irvine", "Chula Vista",
        "Fremont", "San Bernardino", "Modesto", "Fontana", "Oxnard",
        "Moreno Valley", "Glendale", "Huntington Beach", "Santa Clarita",
        "Garden Grove", "Oceanside", "Rancho Cucamonga", "Ontario",
        "Lancaster", "Elk Grove", "Corona", "Palmdale", "Salinas",
        "Pomona", "Hayward", "Escondido", "Torrance", "Sunnyvale",
        "Pasadena", "Roseville", "Orange", "Fullerton", "Visalia",
        "Thousand Oaks", "Simi Valley", "Concord", "Santa Rosa",
        "Vallejo", "Victorville", "Berkeley", "El Monte", "Downey",
        "Costa Mesa", "Inglewood", "Carlsbad", "Temecula", "Murrieta",
        "Petaluma", "Richmond", "Antioch", "West Covina", "Norwalk",
        "Burbank", "Daly City", "Rialto", "El Cajon", "San Mateo",
        "Clovis", "Compton", "Vista", "Mission Viejo", "South Gate",
        "Carson", "Santa Monica", "Westminster", "Hesperia", "Redding",
        "Santa Barbara", "Chico", "Newport Beach", "San Leandro",
        "Hawthorne", "Livermore", "Alhambra", "Tracy", "Whittier",
        "Jurupa Valley", "Lake Forest", "Vacaville", "Hemet", "Fairfield",
        "San Ramon", "Indio", "Menifee", "Citrus Heights", "Tustin",
        "Manteca", "Napa", "Folsom", "Redlands", "Rosemead", "Turlock",
        "San Marcos", "Poway", "Arcadia", "Upland", "Brea", "Pleasanton",
        "Camarillo", "Lakewood", "Perris", "Milpitas", "Redwood City",
        "Gilroy", "Yuba City", "Lodi", "Mountain View", "Ventura",
        "West Sacramento", "Chino", "Chino Hills", "Laguna Niguel",
        "Lake Elsinore", "Palo Alto", "Santa Maria", "Santa Cruz",
        "San Luis Obispo", "Monterey", "Calexico", "Merced", "Hanford",
        "Porterville", "Tulare", "Madera", "Delano",
        "Lompoc", "Santa Paula", "Woodland", "Davis", "Dixon",
        "Rocklin", "Lincoln", "Auburn", "Grass Valley", "Yucaipa",
        "Apple Valley", "Barstow", "Twentynine Palms", "Palm Springs",
        "Palm Desert", "Cathedral City", "Rancho Mirage", "Coachella",
        "San Clemente", "San Juan Capistrano", "Laguna Beach",
        "Dana Point", "Aliso Viejo", "Rancho Santa Margarita",
        "Wildomar", "Beaumont", "Banning", "San Jacinto",
    ],

    # ── Colorado ──────────────────────────────────────────────────────────────
    "CO": [
        "Denver", "Colorado Springs", "Aurora", "Fort Collins", "Lakewood",
        "Thornton", "Arvada", "Westminster", "Pueblo", "Centennial",
        "Boulder", "Highlands Ranch", "Greeley", "Longmont", "Loveland",
        "Broomfield", "Castle Rock", "Commerce City", "Parker", "Northglenn",
        "Brighton", "Littleton", "Englewood", "Wheat Ridge", "Fountain",
        "Security-Widefield", "Sterling", "Montrose", "Durango",
        "Grand Junction", "Steamboat Springs", "Glenwood Springs",
        "Pueblo West", "Canon City", "La Junta", "Fort Morgan", "Alamosa",
        "Gunnison", "Salida", "Trinidad", "Aspen", "Vail", "Breckenridge",
        "Telluride", "Frisco", "Silverthorne", "Dillon", "Avon",
        "Edwards", "Rifle", "Carbondale", "Basalt", "Woodland Park",
    ],

    # ── Connecticut ───────────────────────────────────────────────────────────
    "CT": [
        "Bridgeport", "New Haven", "Hartford", "Stamford", "Waterbury",
        "Norwalk", "Danbury", "New Britain", "West Hartford", "Greenwich",
        "Hamden", "Bristol", "Meriden", "Manchester", "West Haven",
        "Milford", "Stratford", "East Hartford", "Middletown", "Enfield",
        "Southington", "Norwich", "Fairfield", "Wallingford", "New London",
        "Shelton", "Groton", "Torrington", "Trumbull", "Naugatuck",
        "Cheshire", "Vernon", "Glastonbury", "Newington", "Windham",
        "Newtown", "New Milford", "Ridgefield", "Wilton", "Westport",
        "Wethersfield", "Rocky Hill", "Plainville", "Simsbury", "Avon",
    ],

    # ── Delaware ──────────────────────────────────────────────────────────────
    "DE": [
        "Wilmington", "Dover", "Newark", "Middletown", "Smyrna",
        "Milford", "Seaford", "Georgetown", "Elsmere", "New Castle",
        "Rehoboth Beach", "Lewes", "Millsboro", "Harrington", "Delmar",
    ],

    # ── Florida ───────────────────────────────────────────────────────────────
    "FL": [
        "Jacksonville", "Miami", "Tampa", "Orlando", "St. Petersburg",
        "Hialeah", "Port St. Lucie", "Cape Coral", "Fort Lauderdale",
        "Tallahassee", "Pembroke Pines", "Hollywood", "Miramar",
        "Gainesville", "Coral Springs", "Clearwater", "Miami Gardens",
        "Palm Bay", "Lakeland", "Pompano Beach", "West Palm Beach",
        "Davie", "Boca Raton", "Sunrise", "Plantation", "Fort Myers",
        "Deltona", "Largo", "Palm Beach Gardens", "Deerfield Beach",
        "Boynton Beach", "Melbourne", "Lauderhill", "Weston", "Kissimmee",
        "Homestead", "Daytona Beach", "Delray Beach", "Tamarac",
        "Brandon", "North Miami", "Wellington", "Jupiter", "Ocala",
        "St. Cloud", "Sanford", "Port Orange", "Margate", "Coconut Creek",
        "Pensacola", "Sarasota", "Fort Pierce", "Bradenton", "Spring Hill",
        "Palm Coast", "Coral Gables", "Doral", "Aventura",
        "Riverview", "Wesley Chapel", "Land O Lakes",
        "Altamonte Springs", "Casselberry", "Winter Garden", "Apopka",
        "Clermont", "Oviedo", "Lakewood Ranch", "Venice", "Estero",
        "Bonita Springs", "Marco Island", "Naples", "Vero Beach",
        "Stuart", "Titusville", "Rockledge", "Cocoa",
        "Ormond Beach", "Palm Beach", "Lake Worth",
        "Hallandale Beach", "Opa-locka", "North Miami Beach", "Cutler Bay",
        "Key West", "Key Largo", "Leesburg", "The Villages", "Inverness",
        "Brooksville", "Zephyrhills", "Winter Haven", "Haines City",
        "Auburndale", "Panama City", "Destin", "Fort Walton Beach",
        "Niceville", "Crestview", "Milton", "Gulf Breeze",
        "Quincy", "Marianna", "Live Oak", "Lake City", "Fernandina Beach",
        "Palatka", "New Smyrna Beach", "Edgewater", "Oak Hill",
        "Sebring", "Avon Park", "Lake Placid", "Wauchula",
        "Punta Gorda", "Port Charlotte", "Englewood",
        "Tarpon Springs", "Dunedin", "Safety Harbor", "Oldsmar",
        "St. Augustine", "Palm Valley", "Ponte Vedra Beach",
        "Orange City", "DeLand",
    ],

    # ── Georgia ───────────────────────────────────────────────────────────────
    "GA": [
        "Atlanta", "Augusta", "Columbus", "Macon", "Savannah",
        "Athens", "Sandy Springs", "Roswell", "Johns Creek", "Albany",
        "Warner Robins", "Alpharetta", "Marietta", "Smyrna", "Valdosta",
        "Stonecrest", "East Point", "Peachtree City", "Dunwoody",
        "Gainesville", "Hinesville", "Rome", "Kennesaw", "Newnan",
        "Douglasville", "Lawrenceville", "Canton", "Statesboro", "Dalton",
        "Fayetteville", "Woodstock", "Griffin", "Carrollton", "LaGrange",
        "Milledgeville", "Thomasville", "Americus", "Tifton", "Brunswick",
        "Waycross", "Bainbridge", "Cordele", "Douglas", "Jesup",
        "Moultrie", "Fitzgerald", "Vidalia", "Dublin", "Conyers",
        "McDonough", "Stockbridge", "Riverdale", "Decatur", "Tucker",
        "Buford", "Cumming", "Sugar Hill", "Snellville", "Lilburn",
        "Duluth", "Norcross", "Peachtree Corners", "Suwanee", "Dacula",
        "Winder", "Monroe", "Covington", "Social Circle", "Madison",
        "Toccoa", "Cornelia", "Dawsonville", "Blue Ridge",
        "Calhoun", "Cedartown", "Cartersville", "Acworth", "Powder Springs",
        "Union City", "College Park", "Hapeville", "Forest Park", "Jonesboro",
    ],

    # ── Hawaii ────────────────────────────────────────────────────────────────
    "HI": [
        "Honolulu", "Pearl City", "Hilo", "Kailua", "Kapolei",
        "Kaneohe", "Mililani", "Kahului", "Waipahu", "Kihei",
        "Makakilo", "Halawa", "Wailuku", "Aiea", "Waianae",
        "Kailua-Kona", "Lahaina", "Lihue", "Kapaa",
    ],

    # ── Idaho ─────────────────────────────────────────────────────────────────
    "ID": [
        "Boise", "Nampa", "Meridian", "Idaho Falls", "Pocatello",
        "Caldwell", "Coeur d'Alene", "Twin Falls", "Lewiston", "Post Falls",
        "Rexburg", "Moscow", "Eagle", "Star", "Kuna", "Ammon",
        "Chubbuck", "Hayden", "Mountain Home", "Blackfoot",
        "Jerome", "Burley", "Sandpoint", "Rupert", "Hailey",
        "McCall", "Weiser", "Payette", "Ontario",
    ],

    # ── Illinois ──────────────────────────────────────────────────────────────
    "IL": [
        "Chicago", "Aurora", "Joliet", "Rockford", "Springfield",
        "Elgin", "Peoria", "Champaign", "Waukegan", "Cicero",
        "Bloomington", "Naperville", "Evanston", "Decatur", "Schaumburg",
        "Bolingbrook", "Palatine", "Skokie", "Des Plaines", "Orland Park",
        "Tinley Park", "Oak Lawn", "Berwyn", "Mount Prospect", "Normal",
        "Wheaton", "Hoffman Estates", "Oak Park", "Downers Grove",
        "Lansing", "Calumet City", "Urbana", "Gurnee", "Bartlett",
        "Arlington Heights", "Buffalo Grove", "Streamwood", "Carol Stream",
        "Algonquin", "Oswego", "Plainfield", "Romeoville", "Lockport",
        "Crystal Lake", "Quincy", "Moline", "Rock Island", "Carbondale",
        "Alton", "Galesburg", "Kankakee", "Danville", "Belleville",
        "O'Fallon", "Collinsville", "Granite City", "Edwardsville",
        "Pekin", "Freeport", "DeKalb", "North Chicago", "Zion",
        "Winthrop Harbor", "Carpentersville", "Hanover Park",
        "Glendale Heights", "Addison", "Lombard", "Villa Park",
        "Elmhurst", "Wheeling", "Northbrook", "Glenview", "Niles",
        "Park Ridge", "Harwood Heights", "Norridge", "Melrose Park",
        "Maywood", "Bellwood", "Broadview", "Westchester",
        "Lisle", "Woodridge", "Darien", "Westmont", "Clarendon Hills",
        "Hinsdale", "Oak Brook", "Burr Ridge", "Palos Hills", "Palos Park",
        "Mokena", "New Lenox", "Frankfort", "Matteson", "Olympia Fields",
        "Harvey", "Dolton", "Riverdale", "Calumet Park", "Blue Island",
    ],

    # ── Indiana ───────────────────────────────────────────────────────────────
    "IN": [
        "Indianapolis", "Fort Wayne", "Evansville", "South Bend",
        "Carmel", "Fishers", "Bloomington", "Hammond", "Gary", "Lafayette",
        "Muncie", "Terre Haute", "Kokomo", "Anderson", "Noblesville",
        "Greenwood", "Elkhart", "Mishawaka", "Lawrence", "Jeffersonville",
        "Columbus", "Portage", "New Albany", "Richmond", "Westfield",
        "Zionsville", "Avon", "Plainfield", "Valparaiso", "Michigan City",
        "East Chicago", "Merrillville", "Crown Point", "Goshen", "Marion",
        "Vincennes", "Seymour", "Shelbyville", "Franklin", "Connersville",
        "Bedford", "Logansport", "New Castle", "Warsaw", "Auburn",
        "Wabash", "Peru", "Huntington", "Bluffton", "Kendallville",
        "Angola", "LaPorte", "Chesterton", "Schererville", "Highland",
        "Munster", "Dyer", "St. John", "Lowell", "Hobart",
    ],

    # ── Iowa ──────────────────────────────────────────────────────────────────
    "IA": [
        "Des Moines", "Cedar Rapids", "Davenport", "Sioux City",
        "Iowa City", "Waterloo", "Council Bluffs", "Ames", "West Des Moines",
        "Dubuque", "Ankeny", "Urbandale", "Cedar Falls", "Marion",
        "Bettendorf", "Mason City", "Marshalltown", "Clinton", "Burlington",
        "Fort Dodge", "Ottumwa", "Muscatine", "Coralville", "Johnston",
        "North Liberty", "Waukee", "Clive", "Altoona", "Indianola",
        "Newton", "Spencer", "Carroll", "Boone", "Oskaloosa",
        "Decorah", "Storm Lake", "Denison", "Fairfield", "Keokuk",
    ],

    # ── Kansas ────────────────────────────────────────────────────────────────
    "KS": [
        "Wichita", "Overland Park", "Kansas City", "Olathe", "Topeka",
        "Lawrence", "Shawnee", "Manhattan", "Lenexa", "Salina",
        "Hutchinson", "Leavenworth", "Leawood", "Dodge City", "Garden City",
        "Liberal", "Emporia", "Hays", "Junction City", "Pittsburg",
        "Newton", "Pratt", "Great Bend", "Arkansas City", "Winfield",
        "Parsons", "Coffeyville", "Independence", "Abilene", "McPherson",
        "Chanute", "Iola", "El Dorado", "Augusta", "Derby",
        "Andover", "Mulvane", "Wellington", "Haysville", "Goddard",
    ],

    # ── Kentucky ──────────────────────────────────────────────────────────────
    "KY": [
        "Louisville", "Lexington", "Bowling Green", "Owensboro",
        "Covington", "Hopkinsville", "Richmond", "Florence", "Georgetown",
        "Henderson", "Elizabethtown", "Nicholasville", "Jeffersontown",
        "Frankfort", "Paducah", "Ashland", "Independence", "Murray",
        "Erlanger", "Danville", "Radcliff", "Shively", "Madisonville",
        "Winchester", "Campbellsville", "Somerset", "Harlan", "Corbin",
        "Pikeville", "Bardstown", "Glasgow", "Morehead", "Prestonsburg",
        "Berea", "Middlesboro", "Hazard", "Mount Sterling", "Versailles",
        "Lawrenceburg", "Shelbyville", "Taylorsville", "La Grange",
        "Shepherdsville", "Bullitt", "Fort Knox",
    ],

    # ── Louisiana ─────────────────────────────────────────────────────────────
    "LA": [
        "New Orleans", "Baton Rouge", "Shreveport", "Metairie",
        "Lafayette", "Lake Charles", "Kenner", "Bossier City", "Monroe",
        "Alexandria", "Houma", "Marrero", "New Iberia", "Laplace",
        "Slidell", "Hammond", "Prairieville", "Central", "Ruston",
        "Sulphur", "Natchitoches", "Opelousas", "Bastrop", "Minden",
        "Denham Springs", "Zachary", "West Monroe", "Covington",
        "Mandeville", "Bogalusa", "Morgan City", "Crowley", "Abbeville",
        "Thibodaux", "Gretna", "Harvey", "Chalmette", "Westwego",
        "Harahan", "Terrytown", "Avondale", "Waggaman",
        "Broussard", "Youngsville", "Scott", "Carencro", "Breaux Bridge",
        "Franklin", "Jeanerette", "Kaplan", "Jennings", "DeRidder",
        "Leesville", "Pineville", "Ville Platte", "Marksville",
    ],

    # ── Maine ─────────────────────────────────────────────────────────────────
    "ME": [
        "Portland", "Lewiston", "Bangor", "South Portland", "Auburn",
        "Biddeford", "Sanford", "Saco", "Westbrook", "Augusta",
        "Waterville", "Brewer", "Presque Isle", "Bath", "Brunswick",
        "Rockland", "Belfast", "Ellsworth", "Bar Harbor", "Caribou",
        "Old Town", "Orono", "Gardiner", "Hallowell", "Farmington",
    ],

    # ── Maryland ──────────────────────────────────────────────────────────────
    "MD": [
        "Baltimore", "Frederick", "Rockville", "Gaithersburg", "Bowie",
        "Hagerstown", "Annapolis", "College Park", "Salisbury",
        "Laurel", "Greenbelt", "Cumberland", "Westminster", "Hyattsville",
        "Takoma Park", "Silver Spring", "Bethesda", "Germantown", "Columbia",
        "Glen Burnie", "Elkridge", "Dundalk", "Catonsville", "Towson",
        "Pikesville", "Owings Mills", "Ellicott City", "Bel Air",
        "Aberdeen", "Havre de Grace", "Edgewood", "Randallstown",
        "Essex", "Parkville", "Timonium", "Reisterstown",
        "Ocean City", "Cambridge", "Easton", "Waldorf", "La Plata",
        "Prince Frederick", "Leonardtown", "Lexington Park",
        "Suitland", "District Heights", "Oxon Hill", "Largo",
        "Upper Marlboro", "Clinton", "Fort Washington",
    ],

    # ── Massachusetts ─────────────────────────────────────────────────────────
    "MA": [
        "Boston", "Worcester", "Springfield", "Lowell", "Cambridge",
        "New Bedford", "Brockton", "Quincy", "Lynn", "Fall River",
        "Newton", "Lawrence", "Somerville", "Framingham", "Haverhill",
        "Waltham", "Malden", "Brookline", "Plymouth", "Medford",
        "Taunton", "Chicopee", "Weymouth", "Revere", "Peabody",
        "Methuen", "Barnstable", "Pittsfield", "Attleboro", "Salem",
        "Westfield", "Holyoke", "Fitchburg", "Beverly", "Everett",
        "Northampton", "Leominster", "Chelsea", "Randolph", "Woburn",
        "Agawam", "Braintree", "Billerica", "Tewksbury", "Dedham",
        "Marlborough", "Chelmsford", "Dartmouth", "Hingham", "Milton",
        "Walpole", "Sharon", "Stoughton", "Canton", "Norwood",
        "Needham", "Wellesley", "Natick", "Milford", "Millis",
        "Franklin", "Hopkinton", "Hudson",
        "Southborough", "Northborough", "Westborough", "Shrewsbury",
        "Grafton", "Uxbridge", "Whitinsville", "Southbridge", "Sturbridge",
        "Auburn", "Oxford", "Webster", "Dudley", "Douglas",
        "Gloucester", "Rockport", "Newburyport", "Amesbury", "Newbury",
        "Ipswich", "Andover", "North Andover", "Dracut",
        "Acton", "Concord", "Lexington", "Bedford", "Burlington",
    ],

    # ── Michigan ──────────────────────────────────────────────────────────────
    "MI": [
        "Detroit", "Grand Rapids", "Warren", "Sterling Heights", "Ann Arbor",
        "Lansing", "Flint", "Dearborn", "Livonia", "Troy",
        "Westland", "Kalamazoo", "Southfield", "Waterford", "Rochester Hills",
        "Pontiac", "Taylor", "St. Clair Shores", "Royal Oak", "Farmington Hills",
        "Novi", "Saginaw", "Muskegon", "Wyoming", "Dearborn Heights",
        "Battle Creek", "Midland", "Bay City", "East Lansing", "Roseville",
        "Redford", "Jackson", "Holland", "Portage", "Auburn Hills",
        "Mount Pleasant", "Alpena", "Marquette", "Traverse City",
        "Owosso", "Adrian", "Monroe", "Ferndale", "Inkster",
        "Lincoln Park", "Clinton Township", "Macomb Township",
        "Canton Township", "Chesterfield Township", "Shelby Township",
        "Grand Blanc", "Flint Township", "Davison", "Flushing",
        "Sault Ste. Marie", "Escanaba", "Iron Mountain", "Ironwood",
        "Cadillac", "Big Rapids", "Reed City", "Ludington",
        "Petoskey", "Charlevoix", "Cheboygan", "Gaylord",
        "Sturgis", "Three Rivers", "Coldwater", "Marshall", "Albion",
        "Charlotte", "Ionia", "Lowell", "Rockford", "Hudsonville",
        "Zeeland", "Jenison", "Grandville", "Walker", "Kentwood",
    ],

    # ── Minnesota ─────────────────────────────────────────────────────────────
    "MN": [
        "Minneapolis", "St. Paul", "Rochester", "Duluth", "Bloomington",
        "Brooklyn Park", "Plymouth", "St. Cloud", "Woodbury", "Eagan",
        "Coon Rapids", "Eden Prairie", "Burnsville", "Apple Valley",
        "Edina", "St. Louis Park", "Mankato", "Maplewood", "Moorhead",
        "Richfield", "Shakopee", "Roseville", "Cottage Grove",
        "Inver Grove Heights", "Lakeville", "Maple Grove", "Blaine",
        "Minnetonka", "Fridley", "Prior Lake", "Stillwater", "Winona",
        "Bemidji", "Brainerd", "Faribault", "Northfield", "Red Wing",
        "Austin", "Owatonna", "Fergus Falls", "Marshall", "Willmar",
        "Hibbing", "Virginia", "Elk River", "Chaska", "Chanhassen",
        "Savage", "Hastings", "Farmington", "Rosemount",
        "New Ulm", "Worthington", "Albert Lea", "Waseca",
        "Montevideo", "Morris", "Alexandria", "Hutchinson", "Litchfield",
    ],

    # ── Mississippi ───────────────────────────────────────────────────────────
    "MS": [
        "Jackson", "Gulfport", "Southaven", "Hattiesburg", "Biloxi",
        "Meridian", "Tupelo", "Olive Branch", "Greenville", "Horn Lake",
        "Pearl", "Madison", "Brandon", "Oxford", "Starkville",
        "Flowood", "Ridgeland", "Vicksburg", "Pascagoula", "Laurel",
        "Columbus", "Natchez", "Corinth", "Hernando", "McComb",
        "Cleveland", "Clarksdale", "Canton", "Picayune", "Long Beach",
        "Pass Christian", "Bay St. Louis", "Waveland", "Ocean Springs",
        "Moss Point", "Gautier", "D'Iberville", "Diamondhead",
        "Brookhaven", "Grenada", "Greenwood", "Yazoo City",
        "Kosciusko", "Louisville", "Philadelphia", "Pontotoc",
    ],

    # ── Missouri ──────────────────────────────────────────────────────────────
    "MO": [
        "Kansas City", "St. Louis", "Springfield", "Columbia", "Independence",
        "Lee's Summit", "O'Fallon", "St. Joseph", "St. Charles", "Blue Springs",
        "Joplin", "Florissant", "Chesterfield", "Jefferson City",
        "Cape Girardeau", "St. Peters", "Wentzville", "Ballwin", "Kirkwood",
        "Clayton", "Hazelwood", "Maryland Heights", "Creve Coeur", "Wildwood",
        "Liberty", "Raytown", "Gladstone", "Grandview", "Belton",
        "Webb City", "Carthage", "Warrensburg", "Sedalia", "Rolla",
        "Poplar Bluff", "Hannibal", "Kirksville", "Branson", "Bolivar",
        "Marshall", "Nevada", "Sikeston", "Festus", "Arnold",
        "Affton", "Mehlville", "Lemay", "Oakville", "Concord",
        "Nixa", "Ozark", "Republic", "Rogersville", "Strafford",
        "Raymore", "Peculiar", "Harrisonville", "Adrian",
        "Excelsior Springs", "Kearney", "Smithville", "Platte City",
        "Park Hills", "Flat River", "De Soto", "Hillsboro",
    ],

    # ── Montana ───────────────────────────────────────────────────────────────
    "MT": [
        "Billings", "Missoula", "Great Falls", "Bozeman", "Butte",
        "Helena", "Kalispell", "Havre", "Anaconda", "Miles City",
        "Livingston", "Lewistown", "Whitefish", "Belgrade", "Laurel",
        "Glendive", "Sidney", "Wolf Point", "Glasgow", "Plentywood",
    ],

    # ── Nebraska ──────────────────────────────────────────────────────────────
    "NE": [
        "Omaha", "Lincoln", "Bellevue", "Grand Island", "Kearney",
        "Fremont", "Hastings", "North Platte", "Norfolk", "Columbus",
        "Papillion", "La Vista", "Gretna", "Scottsbluff", "Alliance",
        "McCook", "Beatrice", "Lexington", "Ogallala",
        "South Sioux City", "Blair", "Seward", "York", "Chadron",
        "Nebraska City", "Plattsmouth", "Wahoo", "Schuyler",
    ],

    # ── Nevada ────────────────────────────────────────────────────────────────
    "NV": [
        "Las Vegas", "Henderson", "Reno", "North Las Vegas", "Sparks",
        "Carson City", "Sunrise Manor", "Paradise", "Spring Valley",
        "Enterprise", "Whitney", "Winchester", "Summerlin South",
        "Boulder City", "Mesquite", "Elko", "Fernley", "Fallon",
        "Winnemucca", "Pahrump", "Laughlin", "Sun Valley",
        "Gardnerville", "Minden", "Dayton", "Yerington",
    ],

    # ── New Hampshire ─────────────────────────────────────────────────────────
    "NH": [
        "Manchester", "Nashua", "Concord", "Derry", "Dover",
        "Rochester", "Salem", "Merrimack", "Londonderry", "Hudson",
        "Keene", "Portsmouth", "Laconia", "Amherst", "Windham",
        "Goffstown", "Gilford", "Somersworth", "Claremont", "Lebanon",
        "Berlin", "Conway", "Durham", "Exeter", "Hampton",
    ],

    # ── New Jersey ────────────────────────────────────────────────────────────
    "NJ": [
        "Newark", "Jersey City", "Paterson", "Elizabeth", "Edison",
        "Woodbridge", "Lakewood", "Toms River", "Hamilton", "Trenton",
        "Clifton", "Camden", "Brick", "Cherry Hill", "Passaic",
        "Union City", "Franklin", "Gloucester", "Old Bridge", "East Orange",
        "North Bergen", "Bayonne", "Piscataway", "Parsippany", "Hoboken",
        "Vineland", "New Brunswick", "Perth Amboy", "Union", "Irvington",
        "Plainfield", "West New York", "Hackensack", "Sayreville", "Kearny",
        "Linden", "Atlantic City", "Orange", "Long Branch", "Asbury Park",
        "Evesham", "Mount Laurel", "Marlboro", "Middletown", "Howell",
        "Jackson", "Monroe", "Berkeley", "Manchester", "Freehold",
        "Manalapan", "Raritan", "Somerville", "Morristown", "Montclair",
        "Bloomfield", "Belleville", "Nutley", "Caldwell", "West Caldwell",
        "Livingston", "Millburn", "Short Hills", "Summit", "Chatham",
        "Madison", "Florham Park", "Hanover", "Whippany", "Rockaway",
        "Dover", "Wharton", "Mine Hill", "Mount Olive", "Flanders",
        "Randolph", "Roxbury", "Washington", "Hackettstown", "Flemington",
        "Bridgewater", "Bound Brook", "North Plainfield", "Dunellen",
        "Metuchen", "South Amboy", "South Brunswick", "East Brunswick",
        "North Brunswick", "Highland Park",
        "Moorestown", "Voorhees", "Berlin", "Medford", "Marlton",
        "Sicklerville", "Turnersville", "Blackwood", "Glassboro",
        "Deptford", "Woodbury", "Paulsboro", "Pennsville", "Salem",
        "Millville", "Bridgeton", "Wildwood", "Cape May", "Ocean City",
        "Egg Harbor Township", "Galloway", "Absecon", "Pleasantville",
    ],

    # ── New Mexico ────────────────────────────────────────────────────────────
    "NM": [
        "Albuquerque", "Las Cruces", "Rio Rancho", "Santa Fe", "Roswell",
        "Farmington", "Clovis", "Hobbs", "Carlsbad", "Alamogordo",
        "Gallup", "Silver City", "Lovington", "Artesia", "Los Lunas",
        "Deming", "Belen", "Taos", "Portales", "Los Alamos",
        "Grants", "Tucumcari", "Socorro", "Truth or Consequences",
        "Espanola", "Ruidoso", "Aztec", "Bloomfield",
    ],

    # ── New York ──────────────────────────────────────────────────────────────
    "NY": [
        "New York City", "Buffalo", "Rochester", "Yonkers", "Syracuse",
        "Albany", "New Rochelle", "Mount Vernon", "Schenectady", "Utica",
        "White Plains", "Troy", "Niagara Falls", "Binghamton", "Freeport",
        "Valley Stream", "Long Beach", "Spring Valley", "Hempstead",
        "Levittown", "Rome", "Ithaca", "Poughkeepsie", "North Tonawanda",
        "Jamestown", "Elmira", "Newburgh", "Middletown", "Watertown",
        "Lockport", "Plattsburgh", "Brooklyn", "Queens", "Bronx",
        "Staten Island", "Manhattan",
        "Garden City", "Huntington", "Babylon", "Islip", "Brookhaven",
        "Smithtown", "Oyster Bay", "North Hempstead", "Greenburgh",
        "Ramapo", "Clarkstown", "Mount Pleasant", "Peekskill",
        "Beacon", "Kingston", "Saratoga Springs", "Amsterdam",
        "Glens Falls", "Oneonta", "Cortland", "Oswego", "Fulton",
        "Ogdensburg", "Massena", "Dunkirk", "Salamanca",
        "Cheektowaga", "Amherst", "Tonawanda", "West Seneca", "Orchard Park",
        "Lackawanna", "Hamburg", "Lancaster", "Depew",
        "Irondequoit", "Greece", "Gates", "Penfield", "Fairport",
        "Webster", "Victor", "Canandaigua", "Geneva", "Seneca Falls",
        "Auburn", "Baldwinsville",
        "East Syracuse", "Camillus", "Liverpool", "Clay",
        "Cicero", "Manlius", "Fayetteville",
        "Vestal", "Johnson City", "Endicott", "Endwell",
        "Horseheads", "Corning", "Bath", "Hornell",
        "Queensbury", "Lake George",
        "Clifton Park", "Halfmoon", "Mechanicville",
    ],

    # ── North Carolina ────────────────────────────────────────────────────────
    "NC": [
        "Charlotte", "Raleigh", "Greensboro", "Durham", "Winston-Salem",
        "Fayetteville", "Cary", "Wilmington", "High Point", "Concord",
        "Gastonia", "Greenville", "Asheville", "Jacksonville", "Chapel Hill",
        "Rocky Mount", "Burlington", "Huntersville", "Wilson", "Kannapolis",
        "Apex", "Hickory", "Mooresville", "Wake Forest", "Indian Trail",
        "Salisbury", "Monroe", "Matthews", "New Bern", "Sanford",
        "Holly Springs", "Fuquay-Varina", "Cornelius", "Statesville",
        "Lumberton", "Kinston", "Goldsboro", "Asheboro", "Elizabeth City",
        "Garner", "Hendersonville", "Morganton", "Mint Hill", "Thomasville",
        "Lenoir", "Shelby", "Albemarle", "Boone", "Oxford",
        "Henderson", "Laurinburg", "Roanoke Rapids", "Kings Mountain",
        "Kernersville", "Mebane", "Graham", "Elon",
        "Pittsboro", "Siler City", "Reidsville", "Eden", "Madison",
        "Mount Airy", "Elkin", "North Wilkesboro", "Wilkesboro",
        "Mocksville", "Lexington", "Randleman", "Archdale", "Trinity",
        "Conover", "Newton", "Claremont", "Catawba",
        "Waxhaw", "Stallings", "Marvin", "Ballantyne",
        "Pinehurst", "Southern Pines", "Lillington",
        "Dunn", "Clinton", "Wallace", "Whiteville", "Shallotte",
        "Southport", "Morehead City", "Beaufort", "Havelock",
        "Swansboro", "Surf City",
    ],

    # ── North Dakota ──────────────────────────────────────────────────────────
    "ND": [
        "Fargo", "Bismarck", "Grand Forks", "Minot", "West Fargo",
        "Williston", "Dickinson", "Mandan", "Watford City", "Jamestown",
        "Devils Lake", "Valley City", "Wahpeton", "Grafton",
    ],

    # ── Ohio ──────────────────────────────────────────────────────────────────
    "OH": [
        "Columbus", "Cleveland", "Cincinnati", "Toledo", "Akron",
        "Dayton", "Parma", "Canton", "Youngstown", "Lorain",
        "Hamilton", "Springfield", "Kettering", "Elyria", "Lakewood",
        "Cuyahoga Falls", "Euclid", "Middletown", "Newark", "Cleveland Heights",
        "Mentor", "Beavercreek", "Strongsville", "Fairfield", "Dublin",
        "Findlay", "Warren", "Lancaster", "Lima", "Huber Heights",
        "Westerville", "Mansfield", "Delaware", "Marion", "Reynoldsburg",
        "Gahanna", "Grove City", "Stow", "Medina", "Brunswick",
        "Avon Lake", "Sandusky", "Portsmouth", "Chillicothe",
        "Zanesville", "Fremont", "Ashland", "Massillon", "Alliance",
        "Barberton", "Troy", "Piqua", "Tiffin", "Bowling Green",
        "Defiance", "Wooster", "Ashtabula",
        "Fairborn", "Xenia", "Centerville", "Miamisburg", "Vandalia",
        "Englewood", "Trotwood", "Riverside", "Norwood",
        "Blue Ash", "Sharonville", "Mason", "Monroe", "Trenton",
        "Oxford", "Celina", "Wapakoneta", "Ada",
        "Urbana", "Marysville", "Plain City", "Hilliard", "Upper Arlington",
        "Worthington", "New Albany", "Pickerington", "Pataskala",
        "Heath", "Granville", "Mount Vernon", "Gambier",
        "Galion", "Bucyrus", "Crestline", "Shelby",
        "Willoughby", "Wickliffe", "Willowick", "Eastlake", "Painesville",
        "Chardon", "Twinsburg", "Solon", "Beachwood", "South Euclid",
    ],

    # ── Oklahoma ──────────────────────────────────────────────────────────────
    "OK": [
        "Oklahoma City", "Tulsa", "Norman", "Broken Arrow", "Lawton",
        "Edmond", "Moore", "Midwest City", "Enid", "Stillwater",
        "Muskogee", "Bartlesville", "Owasso", "Shawnee", "Yukon",
        "Bixby", "Jenks", "Sapulpa", "Mustang", "Ardmore",
        "Ponca City", "Duncan", "McAlester", "Claremore", "Sand Springs",
        "Bethany", "Altus", "Ada", "El Reno", "Durant",
        "Chickasha", "Miami", "Tahlequah", "Guthrie", "Del City",
        "Choctaw", "Tuttle", "Blanchard", "Newcastle", "Piedmont",
        "Weatherford", "Elk City", "Clinton", "Woodward",
        "Alva", "Watonga",
        "Pryor Creek", "Wagoner", "Sallisaw", "Poteau",
        "Hugo", "Atoka", "Tishomingo", "Sulphur",
    ],

    # ── Oregon ────────────────────────────────────────────────────────────────
    "OR": [
        "Portland", "Eugene", "Salem", "Gresham", "Hillsboro",
        "Beaverton", "Bend", "Medford", "Springfield", "Corvallis",
        "Albany", "Tigard", "Lake Oswego", "Keizer", "Grants Pass",
        "Oregon City", "McMinnville", "Redmond", "Tualatin", "West Linn",
        "Woodburn", "Forest Grove", "Newberg", "Roseburg", "Ashland",
        "Klamath Falls", "Coos Bay", "The Dalles", "Pendleton", "Canby",
        "Sherwood", "Wilsonville", "Happy Valley", "Milwaukie",
        "Troutdale", "Fairview", "Wood Village",
        "Molalla", "Sandy", "Estacada", "Dallas", "Monmouth",
        "Independence", "Lincoln City", "Newport", "Florence",
        "Coquille", "North Bend", "Brookings",
        "Astoria", "Seaside", "Cannon Beach", "Tillamook",
        "Hood River", "Hermiston", "Umatilla",
        "La Grande", "Baker City", "Ontario", "Burns",
    ],

    # ── Pennsylvania ──────────────────────────────────────────────────────────
    "PA": [
        "Philadelphia", "Pittsburgh", "Allentown", "Erie", "Reading",
        "Scranton", "Bethlehem", "Lancaster", "Harrisburg", "Altoona",
        "York", "Wilkes-Barre", "Chester", "Norristown", "State College",
        "Easton", "Lebanon", "Hazleton", "New Castle", "McKeesport",
        "Pottsville", "Johnstown", "Lower Merion", "Abington", "Upper Darby",
        "Bensalem", "Bristol", "Levittown", "Millcreek", "Bethel Park",
        "Plum", "Murrysville", "McCandless", "Mt. Lebanon", "Hampton",
        "Ross", "Cranberry Township", "Monroeville", "Penn Hills",
        "Chambersburg", "Carlisle", "Mechanicsburg", "Gettysburg",
        "King of Prussia", "Malvern", "Coatesville", "West Chester",
        "Media", "Phoenixville", "Pottstown", "Lansdale",
        "Doylestown", "Quakertown", "Souderton", "Sellersville",
        "Stroudsburg", "East Stroudsburg",
        "Bloomsburg", "Williamsport", "Lock Haven", "Sunbury", "Lewisburg",
        "Danville", "Shamokin", "Tamaqua", "Mahanoy City",
        "Northampton", "Whitehall",
        "Emmaus", "Macungie", "Coopersburg",
        "Greensburg", "Jeannette", "Latrobe", "Connellsville",
        "Uniontown", "Washington", "Canonsburg", "McMurray",
        "New Kensington", "Arnold", "Tarentum", "Natrona Heights",
        "Kittanning", "Butler", "Mars",
        "Indiana", "Punxsutawney", "DuBois", "Clearfield",
        "Meadville", "Oil City", "Franklin", "Titusville",
        "Sharon", "Hermitage", "Farrell", "Grove City",
    ],

    # ── Rhode Island ──────────────────────────────────────────────────────────
    "RI": [
        "Providence", "Cranston", "Warwick", "Pawtucket", "East Providence",
        "Woonsocket", "Coventry", "Cumberland", "North Providence",
        "South Kingstown", "West Warwick", "Johnston", "North Kingstown",
        "Newport", "Bristol", "Middletown", "Portsmouth", "Tiverton",
    ],

    # ── South Carolina ────────────────────────────────────────────────────────
    "SC": [
        "Columbia", "Charleston", "North Charleston", "Mount Pleasant",
        "Rock Hill", "Greenville", "Summerville", "Goose Creek",
        "Hilton Head Island", "Sumter", "Florence", "Spartanburg",
        "Myrtle Beach", "Anderson", "Aiken", "Mauldin", "Greer",
        "Conway", "Simpsonville", "Lexington", "Hanahan", "Socastee",
        "Bluffton", "Taylors", "Greenwood", "Irmo", "Cayce",
        "Orangeburg", "Newberry", "Easley", "Seneca", "Gaffney",
        "Lancaster", "Beaufort", "Georgetown", "Fort Mill", "Indian Land",
        "Clover", "Lake Wylie", "Tega Cay", "York", "Chester",
        "Union", "Laurens", "Clinton", "Abbeville",
        "Walterboro", "Edisto Island", "Pawleys Island",
        "Surfside Beach", "Murrells Inlet", "Garden City",
        "Hartsville", "Darlington", "Manning", "Santee",
        "Bishopville", "Camden", "Kershaw",
    ],

    # ── South Dakota ──────────────────────────────────────────────────────────
    "SD": [
        "Sioux Falls", "Rapid City", "Aberdeen", "Brookings", "Watertown",
        "Mitchell", "Yankton", "Pierre", "Huron", "Spearfish",
        "Vermillion", "Brandon", "Box Elder", "Sturgis", "Belle Fourche",
    ],

    # ── Tennessee ─────────────────────────────────────────────────────────────
    "TN": [
        "Nashville", "Memphis", "Knoxville", "Chattanooga", "Clarksville",
        "Murfreesboro", "Franklin", "Jackson", "Johnson City", "Bartlett",
        "Hendersonville", "Kingsport", "Collierville", "Smyrna", "Cleveland",
        "Brentwood", "Germantown", "Columbia", "La Vergne", "Cookeville",
        "Morristown", "Gallatin", "Oak Ridge", "Maryville", "Bristol",
        "Spring Hill", "Shelbyville", "Mount Juliet", "Tullahoma",
        "Dyersburg", "Greeneville", "Athens", "Sevierville", "Lewisburg",
        "Dickson", "Lebanon", "Paris", "Elizabethton", "Crossville",
        "Union City", "Covington", "Henderson", "Springfield",
        "Portland", "Goodlettsville", "Millington", "Lakeland",
        "Munford", "Oakland", "Atoka",
        "Alcoa", "Lenoir City", "Loudon", "Kingston",
        "Harriman", "Rockwood", "Dayton", "Dunlap",
        "Jasper", "South Pittsburg", "Kimball", "Monteagle",
        "Manchester", "McMinnville", "Sparta",
        "Pulaski", "Lawrenceburg", "Savannah", "Selmer",
        "Humboldt", "Milan", "Trenton",
        "Brownsville", "Bolivar", "Ripley",
    ],

    # ── Utah ──────────────────────────────────────────────────────────────────
    "UT": [
        "Salt Lake City", "West Valley City", "Provo", "West Jordan",
        "Orem", "Sandy", "Ogden", "St. George", "Layton", "South Jordan",
        "Lehi", "Taylorsville", "Logan", "Murray", "Draper",
        "Bountiful", "Riverton", "Roy", "Spanish Fork", "American Fork",
        "Pleasant Grove", "Clearfield", "Cottonwood Heights", "Springville",
        "Tooele", "Cedar City", "Kaysville", "Midvale", "Herriman",
        "Millcreek", "Holladay", "Payson", "Eagle Mountain",
        "Syracuse", "Clinton", "Hyde Park", "North Logan", "Providence",
        "Brigham City", "Tremonton", "Vernal", "Price", "Moab",
        "Richfield", "Fillmore", "Delta",
    ],

    # ── Vermont ───────────────────────────────────────────────────────────────
    "VT": [
        "Burlington", "Essex", "South Burlington", "Colchester", "Rutland",
        "Bennington", "Brattleboro", "Montpelier", "St. Albans",
        "Winooski", "Barre", "Newport", "Middlebury", "Vergennes",
    ],

    # ── Virginia ──────────────────────────────────────────────────────────────
    "VA": [
        "Virginia Beach", "Norfolk", "Chesapeake", "Richmond", "Newport News",
        "Alexandria", "Hampton", "Roanoke", "Portsmouth", "Suffolk",
        "Lynchburg", "Harrisonburg", "Charlottesville", "Danville",
        "Manassas", "Fredericksburg", "Winchester", "Staunton",
        "Williamsburg", "Bristol", "Blacksburg", "Waynesboro",
        "Leesburg", "Ashburn", "Centreville", "Reston", "Sterling",
        "Herndon", "McLean", "Falls Church", "Arlington", "Annandale",
        "Dale City", "Lake Ridge", "Woodbridge", "Dumfries",
        "Fairfax", "Burke", "Springfield", "Chantilly",
        "Hopewell", "Petersburg", "Colonial Heights", "Martinsville",
        "Galax", "Radford", "Salem", "Vinton",
        "Christiansburg", "Pulaski", "Wytheville", "Abingdon",
        "Big Stone Gap", "Norton", "Wise", "Grundy",
        "Culpeper", "Warrenton", "Front Royal", "Strasburg",
        "Luray", "Elkton",
        "Covington", "Clifton Forge", "Warm Springs",
        "Lexington", "Buena Vista", "Glasgow",
        "South Boston", "Halifax", "Emporia", "Clarksville",
        "South Hill", "Kenbridge", "Victoria",
        "Farmville", "Appomattox",
        "Bedford", "Rocky Mount", "Bassett",
        "Stuart",
        "Poquoson", "Yorktown", "Gloucester", "Mathews",
        "Tappahannock", "Warsaw", "Kilmarnock",
    ],

    # ── Washington ────────────────────────────────────────────────────────────
    "WA": [
        "Seattle", "Spokane", "Tacoma", "Vancouver", "Bellevue",
        "Kent", "Everett", "Renton", "Spokane Valley", "Kirkland",
        "Bellingham", "Federal Way", "Kennewick", "Yakima", "Redmond",
        "Marysville", "Pasco", "Richland", "Sammamish", "Shoreline",
        "Burien", "Lacey", "Olympia", "Lakewood", "Bremerton",
        "Bothell", "Mount Vernon", "Walla Walla", "Kenmore",
        "Des Moines", "Auburn", "Puyallup", "Edmonds", "Lynnwood",
        "Issaquah", "Wenatchee", "Moses Lake", "Pullman", "Longview",
        "Mukilteo", "Mercer Island", "University Place", "Tukwila",
        "Maple Valley", "Covington", "Tumwater", "Port Angeles",
        "Oak Harbor", "Anacortes", "Burlington", "Monroe", "Snohomish",
        "Lake Stevens", "Stanwood", "Arlington", "Granite Falls",
        "Sedro-Woolley", "Ferndale", "Blaine", "Lynden",
        "Sumas", "Everson", "Nooksack",
        "Chehalis", "Centralia", "Kelso", "Castle Rock",
        "Shelton", "Aberdeen", "Hoquiam", "Elma",
        "Sequim", "Port Townsend", "Port Orchard",
        "Poulsbo", "Gig Harbor", "Bonney Lake", "Orting",
        "Buckley", "Enumclaw", "Black Diamond",
        "SeaTac",
        "Ellensburg", "Selah", "Sunnyside", "Grandview", "Prosser",
        "Wapato", "Toppenish", "Union Gap", "Tieton",
        "East Wenatchee", "Cashmere", "Leavenworth",
        "Quincy", "Ephrata", "Soap Lake", "Coulee Dam",
        "Cheney", "Medical Lake", "Deer Park", "Colville",
        "Newport", "Chewelah", "Kettle Falls",
        "Clarkston", "Asotin",
    ],

    # ── West Virginia ─────────────────────────────────────────────────────────
    "WV": [
        "Charleston", "Huntington", "Morgantown", "Parkersburg", "Wheeling",
        "Martinsburg", "Fairmont", "Beckley", "Clarksburg", "South Charleston",
        "St. Albans", "Vienna", "Bluefield", "Moundsville", "Elkins",
        "Weirton", "Logan", "Oak Hill", "Nitro", "Dunbar",
        "Bridgeport", "Buckhannon", "Summersville", "Lewisburg",
        "White Sulphur Springs", "Princeton", "Welch", "Williamson",
    ],

    # ── Wisconsin ─────────────────────────────────────────────────────────────
    "WI": [
        "Milwaukee", "Madison", "Green Bay", "Kenosha", "Racine",
        "Appleton", "Waukesha", "Oshkosh", "Eau Claire", "Janesville",
        "West Allis", "La Crosse", "Sheboygan", "Wauwatosa", "Fond du Lac",
        "Brookfield", "New Berlin", "Wausau", "Beloit", "Greenfield",
        "Franklin", "Oak Creek", "Manitowoc", "West Bend", "Sun Prairie",
        "Superior", "Fitchburg", "Menomonee Falls", "De Pere", "Marshfield",
        "Muskego", "Mequon", "Mukwonago", "Pewaukee", "Hartland",
        "Oconomowoc", "Watertown", "Beaver Dam", "Rhinelander",
        "Ashland", "Marinette", "Stevens Point", "Plover", "Portage",
        "Baraboo", "Wisconsin Dells", "Tomah", "Sparta", "Onalaska",
        "Holmen", "Caledonia", "Mount Pleasant", "Sturtevant",
        "Pleasant Prairie", "Somers", "Salem",
        "Rib Mountain", "Rothschild", "Schofield",
        "Howard", "Suamico", "Allouez", "Bellevue",
        "Ashwaubenon", "Wrightstown",
        "Sheboygan Falls", "Plymouth", "Kohler",
        "Two Rivers", "Chilton", "Kiel",
        "Neenah", "Kaukauna", "Little Chute",
        "Kimberly", "Combined Locks", "Hortonville",
        "Grand Chute", "Greenville",
        "Green Lake", "Ripon", "Berlin", "Princeton",
        "Waupun", "Mayville", "Campbellsport",
        "Shawano", "New London", "Clintonville", "Iola",
        "Antigo", "Merrill", "Tomahawk",
        "Medford", "Phillips", "Park Falls", "Ladysmith",
        "Rice Lake", "Cumberland", "Barron", "Chetek",
        "Altoona", "Chippewa Falls", "Menomonie",
        "River Falls", "Hudson", "New Richmond", "Baldwin",
        "Osceola", "St. Croix Falls",
    ],

    # ── Wyoming ───────────────────────────────────────────────────────────────
    "WY": [
        "Cheyenne", "Casper", "Laramie", "Gillette", "Rock Springs",
        "Sheridan", "Green River", "Evanston", "Riverton", "Jackson",
        "Cody", "Lander", "Torrington", "Douglas", "Powell",
        "Worland", "Thermopolis", "Rawlins", "Kemmerer",
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


def _load_locations() -> dict[str, list[str]]:
    """Load city list from locations.json if available (generated by fetch_us_cities.py),
    otherwise fall back to the hardcoded LOCATIONS dict above.

    To get full 10,000-18,000 city coverage run once on the server:
        python fetch_us_cities.py
    """
    locations_file = Path(__file__).parent / "locations.json"
    if locations_file.exists():
        try:
            data = json.loads(locations_file.read_text())
            total = sum(len(v) for v in data.values())
            print(f"[scraper] Loaded {total:,} cities across {len(data)} states from locations.json")
            return data
        except Exception as e:
            print(f"[scraper] Failed to load locations.json ({e}), using hardcoded list")
    return LOCATIONS


_LOCATIONS = _load_locations()


def _get_active_locations() -> dict[str, list[str]]:
    return _LOCATIONS


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
