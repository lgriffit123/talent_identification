"""Simple JSON cache for raw ingestion outputs.

Store fetched data per source once per day so repeated runs on the same day
reuse the cached payload and make the pipeline idempotent.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional


CATALOG_PATH = Path(__file__).parent / "catalog.json"


# Set TI_SKIP_CACHE=1 to ignore cached files (useful for debugging or force-refresh)
SKIP_CACHE = os.getenv("TI_SKIP_CACHE", "0").lower() in {"1", "true", "yes"}


def _load_catalog() -> Dict[str, Any]:
    """Return the full JSON catalog ({} if missing or corrupted)."""

    if CATALOG_PATH.exists():
        try:
            return json.loads(CATALOG_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _save_catalog(catalog: Dict[str, Any]) -> None:
    """Write *catalog* back to disk (pretty-printed for readability)."""

    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2))


def get_cached(source: str) -> Optional[List[Dict]]:
    """Return today's cached data for *source* (or *None* if absent/disabled)."""

    if SKIP_CACHE:
        return None

    today_iso = date.today().isoformat()
    catalog = _load_catalog()
    return catalog.get(today_iso, {}).get(source)


def set_cached(source: str, data: List[Dict]) -> None:
    """Append today's *data* for *source* to ``catalog.json``.

    The catalog structure becomes:

    {
        "YYYY-MM-DD": {
            "codeforces": [...],
            "leetcode": [...],
            ...
        },
        "YYYY-MM-DD": { ... }
    }
    """

    if SKIP_CACHE:
        return

    today_iso = date.today().isoformat()
    catalog = _load_catalog()

    catalog.setdefault(today_iso, {})[source] = data

    _save_catalog(catalog)


__all__ = [
    "get_cached",
    "set_cached",
] 