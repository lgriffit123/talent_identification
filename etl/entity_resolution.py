"""Entity resolution module: fuzzy merge and enrichment.

Current data quirks
-------------------
• **Kaggle** – we only get the *handle* (username); display names are not included in the public Meta-Kaggle CSVs.
• **LeetCode** – profile API returns only the *display name*; the handle is embedded in the URL but often matches the name exactly.
• **Codeforces** – provides both *handle* and separate first / last name fields (when the user filled them in).

This means that when merging we usually rely on:
1. **Exact handle match** (best for Kaggle ↔ Codeforces).
2. **Fuzzy name match** using RapidFuzz (best for LeetCode ↔ Codeforces).

Future improvement ideas
------------------------
To improve recall we could enrich the dataset with LinkedIn look-ups for the Top-N candidates:
1. Search LinkedIn by `"<name>" AND "Codeforces"` etc.
2. If a LinkedIn profile is found, grab the canonical name & location.
3. Feed that back into the resolver as an authoritative identifier.

LinkedIn scraping is intentionally *not* included in this repository because it violates LinkedIn terms of service and would require headless browser automation.
"""

from typing import List, Dict

from rapidfuzz import fuzz


def _is_duplicate(name1: str, name2: str, threshold: int = 88) -> bool:
    """Return True if two names are similar enough to be considered duplicates."""

    if name1.lower() == name2.lower():
        return True
    return fuzz.token_sort_ratio(name1, name2) >= threshold


def resolve_entities(entities: List[Dict]) -> List[Dict]:
    """Deduplicate entities appearing across multiple sources.

    The function merges profiles that share the same (or very similar) names.
    Handles typos via fuzzy-matching and aggregates handles per source.
    """
    resolved: List[Dict] = []

    for ent in entities:
        match = None
        for existing in resolved:
            if _is_duplicate(ent["name"], existing["name"]):
                match = existing
                break

        if match is None:
            # Copy to avoid mutating original list
            new_ent = ent.copy()
            if ent.get("source") and ent.get("handle"):
                new_ent["handles"] = {ent["source"]: ent["handle"]}
            else:
                new_ent["handles"] = {}
            resolved.append(new_ent)
        else:
            # Merge data – prefer higher rating if conflict
            if ent["rating"] > match.get("rating", 0):
                match["rating"] = ent["rating"]
                match["source"] = ent["source"]
            # Update handles map
            if ent.get("source") and ent.get("handle"):
                handles = match.setdefault("handles", {})
                handles[ent["source"]] = ent["handle"]

    return resolved


__all__ = ["resolve_entities"] 