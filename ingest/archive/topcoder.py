"""Module for pulling Topcoder Algorithm rankings and normalising them."""

from __future__ import annotations

from typing import List, Dict

import logging
import re
import requests
from bs4 import BeautifulSoup

from . import cache

logger = logging.getLogger(__name__)

RANKING_URL = "https://www.topcoder.com/tc?module=AlgoRank&sc=1&sd=desc"


def fetch_ratings(limit: int = 1000) -> List[Dict]:
    """Fetch ratings for top Topcoder Algorithm competitors by scraping the AlgoRank page.

    Parameters
    ----------
    limit : int, optional
        Maximum number of users to return, by default 1000.

    Returns
    -------
    List[Dict]
        Normalised user dictionaries with keys: name, handle, rating, rank, country, source.
    """

    logger.info("Fetching Topcoder rankings (limit=%d)…", limit)
    cached = cache.get_cached("topcoder")
    if cached is not None:
        logger.info("Using cached Topcoder data (%d entries)", len(cached))
        return cached[:limit]

    headers = {"User-Agent": "Mozilla/5.0 (compatible; TalentIdentificationBot/0.1)"}

    try:
        resp = requests.get(RANKING_URL, headers=headers, timeout=20)
        resp.raise_for_status()
    except Exception:
        logger.exception("Topcoder fetch failed")
        return []

    soup = BeautifulSoup(resp.text, "lxml")

    # Find table that contains a header cell with the text "Handle"
    ranking_table = None
    for tbl in soup.find_all("table"):
        header = tbl.find("th")
        if header and "Handle" in header.get_text():
            ranking_table = tbl
            break
    if ranking_table is None:
        logger.error("Topcoder ranking table not found")
        return []

    users: List[Dict] = []
    for row in ranking_table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue  # skip header or malformed
        rank_text = cols[0].get_text(strip=True)
        if not rank_text or not rank_text.isdigit():
            continue
        rank_val = int(rank_text)

        handle = cols[1].get_text(strip=True)
        rating_text = cols[2].get_text(strip=True)
        try:
            rating = int(re.sub(r"[^0-9]", "", rating_text))
        except ValueError:
            rating = 0

        users.append({
            "name": handle,
            "handle": handle,
            "country": None,  # Topcoder AlgoRank does not expose country directly
            "rating": rating,
            "rank": rank_val,
            "source": "topcoder",
        })
        if len(users) >= limit:
            break

    cache.set_cached("topcoder", users)
    logger.info("Fetched %d Topcoder users", len(users))
    return users[:limit]


__all__ = ["fetch_ratings"] 