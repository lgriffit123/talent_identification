"""
Module for pulling Codeforces ratings and normalising them.
"""

from typing import List, Dict, Optional
import requests
import logging
from datetime import datetime
from functools import lru_cache

from . import cache

logger = logging.getLogger(__name__)

# Base URL for Codeforces API
CODEFORCES_API_URL = "https://codeforces.com/api"

# Cached registration date lookup

@lru_cache(maxsize=None)
def _get_reg_date(handle: str) -> Optional[str]:
    """Return Codeforces registration date (ISO) for *handle*."""
    try:
        resp = requests.get(f"{CODEFORCES_API_URL}/user.info?handles={handle}", timeout=10)
        if resp.status_code == 200 and resp.json().get("status") == "OK":
            info = resp.json()["result"][0]
            ts = info.get("registrationTimeSeconds")
            if ts:
                return datetime.utcfromtimestamp(ts).date().isoformat()
    except Exception:
        pass
    return None

# Fetch top rated Codeforces users (active only) – limited for performance
# Docs: https://codeforces.com/apiHelp/methods#user.ratedList

def fetch_ratings(limit: int = 1000) -> List[Dict]:
    """Fetch ratings for the highest-rated Codeforces users.

    Parameters
    ----------
    limit : int, optional
        Number of users to return, by default 1000.

    Returns
    -------
    List[Dict]
        Normalised ratings dicts with keys: name, handle, country, rating, rank, source.
    """
    logger.info("Fetching Codeforces ratings (limit=%d)…", limit)
    # Check cache first
    cached = cache.get_cached("codeforces")
    if cached is not None:
        logger.info("Using cached Codeforces data (%d entries)", len(cached))
        return cached[:limit]

    endpoint = f"{CODEFORCES_API_URL}/user.ratedList?activeOnly=true&includeRetired=false"

    try:
        logger.debug("Requesting %s", endpoint)
        resp = requests.get(endpoint, timeout=15)
        logger.debug("Codeforces response status %s", resp.status_code)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK":
            raise ValueError("Unexpected API status")
        users = data.get("result", [])[:limit]

        normalised: List[Dict] = []

        for u in tqdm(users, desc="Codeforces reg-date", unit="user"):
            name_parts = []
            if u.get("firstName"):
                name_parts.append(u["firstName"].strip())
            if u.get("lastName"):
                name_parts.append(u["lastName"].strip())
            name = " ".join(name_parts) if name_parts else u["handle"]

            first_seen = _get_reg_date(u["handle"])  # may be None

            normalised.append(
                {
                    "name": name,
                    "handle": u["handle"],
                    "country": u.get("country"),
                    "rating": u.get("rating", 0),
                    "rank": u.get("rank"),
                    "source": "codeforces",
                    "platform_first_seen": first_seen,
                }
            )

        # Cache full list for today
        cache.set_cached("codeforces", normalised)
        logger.info("Fetched %d Codeforces users", len(normalised))
        return normalised[:limit]
    except Exception:  # noqa: BLE001
        # Network failure or API error – return empty list to keep pipeline idempotent.
        logger.exception("Codeforces fetch failed")
        return []

def normalise_ratings(raw_ratings: List[Dict]) -> List[Dict]:
    """Normalise Codeforces rating structures.

    Parameters
    ----------
    raw_ratings : List[Dict]
        Raw ratings as fetched from Codeforces.

    Returns
    -------
    List[Dict]
        Normalised rating dictionaries with well-defined keys.
    """
    # TODO: Implement normalisation logic
    return raw_ratings

__all__ = ["fetch_ratings", "normalise_ratings"] 