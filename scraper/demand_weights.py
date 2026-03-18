"""
Demand weight loader for the scraper.

Reads the industry_demand table (populated by the backend webhook on each purchase)
and returns weights that the _select_targets() function uses to prioritize
high-revenue industry × state combinations.

Weight range: 1.0 (no sales ever) to 5.0 (highest-selling combo).
Falls back to empty dict gracefully if DB is unreachable or table is empty.
"""
import os

from sqlalchemy import create_engine, text

_DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_demand_weights() -> dict[tuple[str, str], float]:
    """
    Returns {(industry_lower, state_upper): weight} where weight is 1.0–5.0.
    High-demand combos get higher weights so they're scraped more often.
    """
    if not _DATABASE_URL:
        return {}

    try:
        engine = create_engine(_DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            rows = conn.execute(
                text("SELECT industry, state, leads_sold FROM industry_demand ORDER BY leads_sold DESC")
            ).fetchall()

        if not rows:
            return {}

        max_sold = max(r.leads_sold for r in rows) or 1
        return {
            (r.industry.lower().strip(), r.state.upper().strip()): 1.0 + (r.leads_sold / max_sold) * 4.0
            for r in rows
            if r.industry and r.state
        }
    except Exception as e:
        print(f"[demand_weights] Could not load weights: {e}")
        return {}
