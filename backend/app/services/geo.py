"""
ZIP code geocoding and radius lookup.
Uses uszipcode (bundled SQLite data — no external API needed).
"""
from __future__ import annotations


def get_zip_info(zip_code: str) -> dict | None:
    """
    Return {'lat': float, 'lng': float, 'city': str, 'state': str} for a ZIP,
    or None if not found.
    """
    try:
        from uszipcode import SearchEngine
        with SearchEngine(simple_zipcode=True) as search:
            z = search.by_zipcode(zip_code.strip())
            if z and z.lat and z.lng:
                return {
                    "lat": float(z.lat),
                    "lng": float(z.lng),
                    "city": z.major_city or "",
                    "state": z.state or "",
                }
    except Exception:
        pass
    return None


def get_cities_in_radius(
    zip_code: str,
    radius_miles: float,
) -> tuple[list[str], str | None]:
    """
    Return (list_of_cities, state_abbr) for all ZIP centroids within
    `radius_miles` of `zip_code`.  Cities are title-cased.
    Returns ([], None) on any error.
    """
    try:
        from uszipcode import SearchEngine
        with SearchEngine(simple_zipcode=True) as search:
            center = search.by_zipcode(zip_code.strip())
            if not center or not center.lat:
                return [], None
            nearby = search.by_coordinates(
                center.lat,
                center.lng,
                radius=radius_miles,
                returns=500,
            )
            cities = list({r.major_city.title() for r in nearby if r.major_city})
            return cities, center.state
    except Exception:
        return [], None
