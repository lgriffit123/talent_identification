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


# If this env var is set to any truthy value, caching is bypassed (useful for
# debugging or forcing fresh pulls):
SKIP_CACHE = os.getenv("TI_SKIP_CACHE", "0").lower() in {"1", "true", "yes"}


def _load_catalog() -> Dict[str, Any]:
    if CATALOG_PATH.exists():
        try:
            return json.loads(CATALOG_PATH.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_catalog(catalog: Dict[str, Any]) -> None:
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False, indent=2))


def get_cached(source: str) -> Optional[List[Dict]]:
    """Return cached data for *source* if it was fetched today."""

    if SKIP_CACHE:
        return None

    today_iso = date.today().isoformat()
    catalog = _load_catalog()
    entry = catalog.get(source)
    if entry and entry.get("fetched_at") == today_iso:
        return entry.get("data", [])
    return None


def set_cached(source: str, data: List[Dict]) -> None:
    """Persist *data* under *source* with today's date."""

    if SKIP_CACHE:
        return

    catalog = _load_catalog()
    catalog[source] = {
        "fetched_at": date.today().isoformat(),
        "data": data,
    }
    _save_catalog(catalog)


__all__ = [
    "get_cached",
    "set_cached",
] 