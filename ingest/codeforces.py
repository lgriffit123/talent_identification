"""
Module for pulling Codeforces ratings and normalising them.
"""

from typing import List, Dict
import requests

# Base URL for Codeforces API
CODEFORCES_API_URL = "https://codeforces.com/api"

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
    endpoint = f"{CODEFORCES_API_URL}/user.ratedList?activeOnly=true&includeRetired=false"

    try:
        resp = requests.get(endpoint, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK":
            raise ValueError("Unexpected API status")
        users = data.get("result", [])[:limit]

        normalised: List[Dict] = []
        for u in users:
            name_parts = []
            if u.get("firstName"):
                name_parts.append(u["firstName"].strip())
            if u.get("lastName"):
                name_parts.append(u["lastName"].strip())
            name = " ".join(name_parts) if name_parts else u["handle"]

            normalised.append(
                {
                    "name": name,
                    "handle": u["handle"],
                    "country": u.get("country"),
                    "rating": u.get("rating", 0),
                    "rank": u.get("rank"),
                    "source": "codeforces",
                }
            )

        return normalised
    except Exception:  # noqa: BLE001
        # Network failure or API error – return empty list to keep pipeline idempotent.
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