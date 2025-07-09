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
            # Save soup results to a text file for debugging
            with open(f"atcoder_page_{page}.txt", "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            # AtCoder's HTML occasionally changes class names; grab the first data table on the page.
            table = soup.find("table")
            if table is None:
                break

            start_count = len(users)
            for row in table.find_all("tr"):
                # Skip header rows that use <th>
                if row.find("th") is not None:
                    continue
                cols = row.find_all("td")
                if len(cols) < 4:
                    continue
                user_td = cols[1]
                username_link = user_td.find("a", class_="username")
                if username_link is None:
                    continue

                # Country from the flag anchor's query param (e.g., f.Country=BY)
                country = None
                flag_anchor = user_td.find("a", href=re.compile(r"f\.Country="))
                if flag_anchor and flag_anchor.get("href"):
                    m_flag = re.search(r"f\.Country=([A-Za-z]{2})", flag_anchor["href"])
                    if m_flag:
                        country = m_flag.group(1).upper()

                # Rank (numeric). Some rows may include "-" for unrated users – skip them.
                rank_text = cols[0].get_text(strip=True)
                m = re.search(r"\d+", rank_text)
                if not m:
                    continue
                rank_val = int(m.group())

                handle = username_link.get_text(strip=True)

                try:
                    rating = int(cols[3].get_text(strip=True))
                except ValueError:
                    rating = 0

                users.append({
                    "name": handle,  # AtCoder usually has no real name separate from handle
                    "handle": handle,
                    "country": country,
                    "rating": rating,
                    "rank": rank_val,
                    "source": "atcoder",
                })
                if len(users) >= limit:
                    break

            # If this page added no new users, assume we've reached the end.
            if len(users) == start_count:
                break
            page += 1
            if page % 5 == 0:
                logger.debug("AtCoder scraping progress: %d users …", len(users))
        cache.set_cached("atcoder", users)
        logger.info("Fetched %d AtCoder users", len(users))
        return users[:limit]
    except Exception:  # noqa: BLE001
        logger.exception("AtCoder fetch failed")
        return []


__all__ = ["fetch_ratings"] 