"""LeetCode contest ranking ingestion.

This module pulls the public contest leaderboard via the undocumented
`/contest/api/ranking/<slug>/` endpoint.  LeetCode requires the requester
 to be *logged-in* when hitting that endpoint.  For headless pipelines we
 allow the caller to supply their cookies through environment variables:

    LEETCODE_SESSION   – value of the `LEETCODE_SESSION` cookie
    LEETCODE_CSRF      – value of the `csrftoken` cookie (optional)

Without those cookies LeetCode replies with HTTP 403.  In that case this
 function will log a warning and return an empty list instead of raising
 so the overall pipeline can still succeed.

Usage
-----
>>> from ingest.leetcode import fetch_contest_ranking
>>> users = fetch_contest_ranking("biweekly-contest-112", limit=100)

Each returned dict has the common keys used by the rest of the ETL stack
(name, handle, rating, rank, country, source) and a `score` field that
captures the raw contest score.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from typing import Dict, List, Optional
from datetime import datetime

import cloudscraper
import time
from playwright.sync_api import sync_playwright
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import cache

# Optional progress bar
try:
    from tqdm import tqdm  # type: ignore
except ImportError:  # pragma: no cover – tqdm not installed
    def tqdm(iterable=None, **kwargs):  # type: ignore
        if iterable is None:
            class _DummyPB:
                def __enter__(self):
                    return self
                def __exit__(self, *exc):
                    return False
                def update(self, n=1):
                    pass
            return _DummyPB()
        return iterable

logger = logging.getLogger(__name__)

_API_URL = "https://leetcode.com/contest/api/ranking/{slug}/"
_MAX_PER_PAGE = 25  # LeetCode always returns 25 ranks per page
_GRAPHQL_ENDPOINT = "https://leetcode.com/graphql"
_MAX_WORKERS = 10  # cap concurrent requests to stay within urllib3 default pool size

# Single scraper instance (handles Cloudflare automatically)
scraper = cloudscraper.create_scraper()

# Cache for user join dates to avoid duplicate GraphQL calls
_JOIN_DATE_CACHE: dict[str, Optional[str]] = {}


def _get_join_date(username: str) -> Optional[str]:
    """Return account creation date (ISO) for *username* using LeetCode GraphQL."""

    if username in _JOIN_DATE_CACHE:
        return _JOIN_DATE_CACHE[username]

    query = (
        "query($username:String!){ matchedUser(username:$username){ user { joinDate } } }"
    )

    try:
        resp = requests.post(
            _GRAPHQL_ENDPOINT,
            json={"query": query, "variables": {"username": username}},
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            join_ts = (
                data.get("data", {})
                .get("matchedUser", {})
                .get("user", {})
                .get("joinDate")
            )
            if join_ts:
                iso_date = datetime.utcfromtimestamp(int(join_ts)).date().isoformat()
                _JOIN_DATE_CACHE[username] = iso_date
                return iso_date
    except Exception:
        logger.debug("Failed GraphQL joinDate for %s", username)

    # --- Fallback: undocumented REST endpoint `/api/users/<username>/` ---
    try:
        rest_url = f"https://leetcode.com/api/users/{username}/"
        r = scraper.get(rest_url, timeout=10)  # reuse cloudscraper to bypass CF
        if r.status_code == 200:
            jd = r.json().get("joinDate")
            if jd:
                iso_date = datetime.utcfromtimestamp(int(jd)).date().isoformat()
                _JOIN_DATE_CACHE[username] = iso_date
                return iso_date
    except Exception:
        logger.debug("Failed to fetch joinDate for %s", username)

    _JOIN_DATE_CACHE[username] = None
    return None


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _fetch_page(slug: str, page: int, out: List[Dict], lock: threading.Lock) -> None:
    """Worker that fetches a single pagination page and extends *out*."""

    url = _API_URL.format(slug=slug)
    params = {"pagination": page, "region": "global"}

    try:
        resp = scraper.get(url, params=params, timeout=20)
        if resp.status_code != 200:
            logger.warning("LeetCode page %d for %s returned %s", page, slug, resp.status_code)
            return
        data = resp.json()
    except Exception:  # pragma: no cover – network issues, invalid JSON, etc.
        logger.exception("Failed to fetch LeetCode page %d for %s", page, slug)
        return

    ranks = data.get("total_rank", [])
    rows: List[Dict] = []
    for user in ranks:
        rows.append({
            "name": user["username"],
            "handle": user["username"],
            "country": user.get("country_code"),
            "rating": user.get("rating", user.get("score", 0)),
            "rank": user["rank"],
            "score": user.get("score"),
            "source": "leetcode",
            "platform_first_seen": _get_join_date(user["username"]),
        })

    with lock:
        out.extend(rows)


def _get_latest_slug() -> Optional[str]:
    """Return titleSlug of the most recent past or upcoming contest."""

    query = """query { allContests { titleSlug startTime } }"""
    try:
        resp = requests.post(
            _GRAPHQL_ENDPOINT,
            json={"query": query},
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            timeout=20,
        )
        if resp.status_code != 200:
            return None
        contests = resp.json()["data"]["allContests"]
        # Sort descending by startTime (epoch seconds)
        contests.sort(key=lambda c: c["startTime"], reverse=True)
        return contests[3]["titleSlug"] if contests else None
    except Exception as e:
        logger.exception("Failed to fetch LeetCode latest contest slug: %s", e)
        return None


def _get_cf_cookie() -> Optional[dict[str, str]]:
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        context = browser.new_context(storage_state=None)
        page = context.new_page()
        page.goto(f"https://leetcode.com/contest/{slug}/ranking", timeout=60000)
        page.wait_for_selector("table")       # ranking table loaded
        cookies = { c["name"]: c["value"] for c in context.cookies() }
        browser.close()
        return cookies


# ---------------------------------------------------------------------------
# Optional Playwright clearance (rarely needed because cloudscraper usually succeeds).
# ---------------------------------------------------------------------------

try:
    from playwright.sync_api import sync_playwright  # type: ignore

    def _solve_cloudflare(slug: str) -> Optional[dict[str, str]]:  # pragma: no cover
        """Launch a headless Firefox instance, load the ranking page once and
        return the resulting cookies (includes cf_clearance).  Requires
        Playwright with browsers installed (`playwright install firefox`)."""

        logger.info("Playwright: launching browser to satisfy Cloudflare challenge …")
        try:
            with sync_playwright() as p:
                browser = p.firefox.launch(headless=True)
                ctx = browser.new_context()
                page = ctx.new_page()
                page.goto(f"https://leetcode.com/contest/{slug}/ranking", timeout=60000)

                # Poll cookies for up to 30 s until Cloudflare sets cf_clearance
                ck: dict[str, str] = {}
                for _ in range(30):
                    all_cookies = {c["name"]: c["value"] for c in ctx.cookies()}
                    if "cf_clearance" in all_cookies:
                        ck["cf_clearance"] = all_cookies["cf_clearance"]
                        break
                    page.wait_for_timeout(1000)  # 1 s
                # optional small extra wait to ensure challenge finished
                browser.close()
                if ck:
                    logger.info("Playwright: obtained cf_clearance cookie")
                else:
                    logger.warning("Playwright: cf_clearance cookie not found after page load")
                return ck or None
        except Exception:
            logger.exception("Playwright failed to solve Cloudflare challenge")
            return None

except ImportError:  # Playwright not installed

    def _solve_cloudflare(slug: str) -> None:  # type: ignore
        return None


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

def fetch_contest_ranking(slug: Optional[str] = None, limit: int = 300) -> List[Dict]:
    """Return *limit* ranked users for the specified LeetCode contest *slug*.

    Parameters
    ----------
    slug : str
        Contest identifier as it appears in the URL, e.g. ``"weekly-contest-400"``.
    limit : int, optional
        Maximum number of users to return (default 1 000).
    """

    if not slug or slug.lower() == "latest":
        slug = _get_latest_slug()
        if not slug:
            logger.warning("Could not resolve latest LeetCode contest slug – skipping")
            return []

    logger.info("Fetching LeetCode rankings for %s (limit=%d)…", slug, limit)

    cache_key = f"leetcode:{slug}"
    cached = cache.get_cached(cache_key)
    if cached is not None:
        logger.info("Using cached LeetCode data for %s (%d entries)", slug, len(cached))
        return cached[:limit]

    # First page – to discover total user count
    url = _API_URL.format(slug=slug)
    try:
        first = scraper.get(url, params={"pagination": 1, "region": "global"}, timeout=20)
        if first.status_code != 200:
            logger.warning("LeetCode initial request failed with status %s", first.status_code)
            return []
        pdata = first.json()
    except Exception:  # pragma: no cover
        logger.exception("Failed to fetch initial LeetCode page for %s", slug)
        return []

    user_total = int(pdata.get("user_num", 0))
    max_page = math.ceil(user_total / _MAX_PER_PAGE)

    results: List[Dict] = []
    lock = threading.Lock()

    # Page-1 results have already been downloaded – process them immediately
    for u in pdata.get("total_rank", []):
        results.append({
            "name": u["username"],
            "handle": u["username"],
            "country": u.get("country_code"),
            "rating": u.get("rating", u.get("score", 0)),
            "rank": u["rank"],
            "score": u.get("score"),
            "source": "leetcode",
            "platform_first_seen": _get_join_date(u["username"]),
        })
        if len(results) >= limit:
            cache.set_cached(cache_key, results)
            return results[:limit]

    # Determine how many additional pages we actually need to reach *limit*
    pages_needed = min(max_page, math.ceil(limit / _MAX_PER_PAGE))

    remaining_pages = list(range(2, pages_needed + 1))

    # Use a bounded thread-pool to avoid urllib3 "connection pool is full" warnings
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        with tqdm(total=len(remaining_pages), desc="LeetCode pages", unit="page") as pbar:
            futures = {pool.submit(_fetch_page, slug, page, results, lock): page for page in remaining_pages}

            # Early-exit once we have enough results – additional futures will complete
            for fut in as_completed(futures):
                pbar.update(1)
                if len(results) >= limit:
                    break

    # Sort by rank (threads may have appended out-of-order)
    results.sort(key=lambda x: x["rank"])

    cache.set_cached(cache_key, results)
    return results[:limit]


__all__ = ["fetch_contest_ranking"] 