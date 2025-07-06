"""Module for pulling AtCoder rankings and normalising them."""

from __future__ import annotations

from typing import List, Dict

import requests
import logging
import re
from bs4 import BeautifulSoup

from . import cache


ATCODER_RANKING_URL = "https://atcoder.jp/ranking/all?lang=en&contest_type=algo&page=1"

logger = logging.getLogger(__name__)


def fetch_ratings(limit: int = 1000) -> List[Dict]:
    """Fetch ratings for top AtCoder users by scraping the ranking page.

    Parameters
    ----------
    limit : int, optional
        Maximum number of users to return, by default 1000.

    Returns
    -------
    List[Dict]
        List of normalised user dictionaries with name, handle, rating, country, source.
    """
    logger.info("Fetching AtCoder rankings (limit=%d)…", limit)
    # Check cache first
    cached = cache.get_cached("atcoder")
    if cached is not None:
        logger.debug("Using cached AtCoder data (%d entries)", len(cached))
        return cached[:limit]

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; TalentIdentificationBot/0.1)"}
        logger.debug("Requesting %s", ATCODER_RANKING_URL)
        resp = requests.get(ATCODER_RANKING_URL, timeout=15, headers=headers)
        logger.debug("AtCoder response status %s", resp.status_code)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", class_="table")
        if table is None:
            return []
        users: List[Dict] = []
        for row in table.tbody.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) < 4:
                continue
            # Col 1: rank, Col 2: username, Col 4: rating (index 3)
            username_link = cols[1].find("a")
            if username_link is None:
                continue

            # Parse rank by first integer substring to avoid "(1) 1" etc.
            rank_text = cols[0].text.strip()
            m = re.search(r"\d+", rank_text)
            if m:
                rank_val = int(m.group())
            else:
                continue  # skip if rank missing

            handle = username_link.text.strip()
            name = handle  # AtCoder doesn't expose separate display name
            try:
                rating = int(cols[3].text.strip())
            except ValueError:
                rating = 0
            users.append(
                {
                    "name": name,
                    "handle": handle,
                    "country": None,  # Not provided by AtCoder ranking
                    "rating": rating,
                    "rank": rank_val,
                    "source": "atcoder",
                }
            )
            if len(users) >= limit:
                break
        cache.set_cached("atcoder", users)
        logger.info("Fetched %d AtCoder users", len(users))
        return users[:limit]
    except Exception:  # noqa: BLE001
        logger.exception("AtCoder fetch failed")
        return []


__all__ = ["fetch_ratings"] 