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
        logger.info("Using cached AtCoder data (%d entries)", len(cached))
        return cached[:limit]

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; TalentIdentificationBot/0.1)"}
        users: List[Dict] = []
        page = 1
        while len(users) < limit:
            url = f"https://atcoder.jp/ranking/all?lang=en&contest_type=algo&page={page}"
            logger.debug("Requesting %s", url)
            resp = requests.get(url, timeout=15, headers=headers)
            if resp.status_code == 404:
                break  # no more pages
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            table = soup.find("table", class_="table")
            if table is None or table.tbody is None:
                break
            for row in table.tbody.find_all("tr"):
                cols = row.find_all("td")
                if len(cols) < 4:
                    continue
                username_link = cols[1].find("a")
                if username_link is None:
                    continue
                rank_text = cols[0].text.strip()
                m = re.search(r"\d+", rank_text)
                if not m:
                    continue
                rank_val = int(m.group())
                handle = username_link.text.strip()
                name = handle
                try:
                    rating = int(cols[3].text.strip())
                except ValueError:
                    rating = 0
                users.append({
                    "name": name,
                    "handle": handle,
                    "country": None,
                    "rating": rating,
                    "rank": rank_val,
                    "source": "atcoder",
                })
                if len(users) >= limit:
                    break
            if table is None or len(table.tbody.find_all("tr")) == 0:
                break
            page += 1
        cache.set_cached("atcoder", users)
        logger.info("Fetched %d AtCoder users", len(users))
        return users[:limit]
    except Exception:  # noqa: BLE001
        logger.exception("AtCoder fetch failed")
        return []


__all__ = ["fetch_ratings"] 