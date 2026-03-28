"""
Fetch comprehensive US city list from GeoNames and save to locations.json.

Run once on the server before starting the scraper:
    python fetch_us_cities.py

Options:
    --min-pop   Minimum population to include (default: 500)
    --output    Output file path (default: locations.json)

GeoNames is free and covers every incorporated place + CDP in the US.
At min_population=500 you get roughly 15,000-18,000 cities.
At min_population=1000 you get roughly 10,000-13,000 cities.
"""

import argparse
import io
import json
import zipfile
import urllib.request
from collections import defaultdict
from pathlib import Path

# Valid US state + DC FIPS codes (excludes territories like PR, GU, VI, AS, MP)
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

# GeoNames admin1 code → state abbreviation mapping
# GeoNames uses numeric FIPS codes for US states in admin1_code
FIPS_TO_STATE = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA",
    "08": "CO", "09": "CT", "10": "DE", "11": "DC", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN",
    "19": "IA", "20": "KS", "21": "KY", "22": "LA", "23": "ME",
    "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS",
    "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND",
    "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
    "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI",
    "56": "WY",
}

GEONAMES_URL = "https://download.geonames.org/export/dump/US.zip"


def fetch_us_cities(min_population: int = 500) -> dict[str, list[str]]:
    print(f"Downloading GeoNames US dataset (this may take 30-60 seconds)...")
    req = urllib.request.Request(
        GEONAMES_URL,
        headers={"User-Agent": "LeadGenScraper/1.0 (city-list-builder)"},
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        data = response.read()
    print(f"Downloaded {len(data) / 1_000_000:.1f} MB. Parsing...")

    cities_by_state: dict[str, set[str]] = defaultdict(set)

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        with zf.open("US.txt") as f:
            for raw_line in f:
                parts = raw_line.decode("utf-8").strip().split("\t")
                if len(parts) < 15:
                    continue

                # GeoNames tab-separated fields:
                # 0  geonameid
                # 1  name (UTF-8)
                # 2  asciiname
                # 6  feature_class  (P = populated place)
                # 7  feature_code   (PPL, PPLA, PPLA2, PPLX, PPLC, ...)
                # 10 admin1_code    (FIPS state code for US)
                # 14 population

                feature_class = parts[6]
                feature_code = parts[7]

                # Only populated-place features; skip PPLX (section of populated place)
                # and PPLCH (historical capital) to avoid noise
                if feature_class != "P":
                    continue
                if feature_code in ("PPLX", "PPLCH", "PPLH"):
                    continue

                admin1 = parts[10]
                # GeoNames uses 2-letter state abbreviations for US admin1_code
                state = admin1 if admin1 in US_STATES else None
                if not state:
                    continue  # territory or unmapped

                try:
                    population = int(parts[14])
                except (ValueError, IndexError):
                    population = 0

                if population < min_population:
                    continue

                name = parts[2].strip()  # ASCII name — safe for scraper URLs
                if name:
                    cities_by_state[state].add(name)

    result = {
        state: sorted(cities_by_state[state])
        for state in sorted(cities_by_state)
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Build US city list from GeoNames")
    parser.add_argument("--min-pop", type=int, default=500,
                        help="Minimum population to include (default: 500)")
    parser.add_argument("--output", type=str, default="locations.json",
                        help="Output JSON file path (default: locations.json)")
    args = parser.parse_args()

    cities = fetch_us_cities(min_population=args.min_pop)

    total = sum(len(v) for v in cities.values())
    print(f"\nResults:")
    print(f"  States: {len(cities)}")
    print(f"  Total cities: {total:,}")

    top5 = sorted(cities.items(), key=lambda x: len(x[1]), reverse=True)[:5]
    for state, cs in top5:
        print(f"  {state}: {len(cs):,} cities")

    out_path = Path(args.output)
    out_path.write_text(json.dumps(cities, indent=2))
    print(f"\nSaved to {out_path.resolve()}")
    print("Restart the scraper to pick up the new city list.")


if __name__ == "__main__":
    main()
