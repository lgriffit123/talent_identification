"""Main orchestrator script.

This script can be scheduled (e.g., cron or CI) or run ad-hoc to perform the
full pipeline: ingest data, resolve entities, score them, and generate a
report.
"""

import os, logging, math, json
from pathlib import Path
from datetime import date, timedelta
from collections import defaultdict, Counter

from ingest import codeforces, kaggle, leetcode, cache
from etl import entity_resolution, scoring, report
from etl.utils import erfinv
from dotenv import load_dotenv

# Load environment variables from .env if present (safe-no-op if file missing)
load_dotenv()

# want to highlight not just the top scores, but maybe top score in a certain area, or highest relative position to peers. 
# ---------------------------------------------------------------------------
# Logging setup (controlled by TI_LOGLEVEL, default INFO)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("TI_LOGLEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)

# Optional env var TI_ONLY="leetcode" or "codeforces,leetcode" to limit sources fetched
TI_ONLY = {s.strip().lower() for s in os.getenv("TI_ONLY", "codeforces,leetcode,kaggle").split(",") if s.strip()}

# Persistent record of when a handle was first observed
FIRST_SEEN_FILE = Path("meta") / "first_seen.json"

def orchestrate() -> None:
    """Run the full talent identification pipeline."""
    logger.info("Starting ingestion phase")

    cf_raw = codeforces.fetch_ratings() if "codeforces" in TI_ONLY else []
    lc_raw = leetcode.fetch_contest_ranking(None) if "leetcode" in TI_ONLY else []
    kg_raw = kaggle.fetch_leaderboard() if "kaggle" in TI_ONLY else []

    logger.info(
        "Fetched counts — Codeforces: %d, LeetCode: %d, Kaggle: %d",
        len(cf_raw), len(lc_raw), len(kg_raw),
    )

    combined_raw = cf_raw + lc_raw + kg_raw

    # -------------------------------------------------------------------
    # Track first-seen date per handle to distinguish fresh vs veteran
    # -------------------------------------------------------------------
    today_iso = date.today().isoformat()
    try:
        first_seen_map: dict[str, str] = json.loads(FIRST_SEEN_FILE.read_text()) if FIRST_SEEN_FILE.exists() else {}
    except Exception:
        first_seen_map = {}

    for ent in combined_raw:
        # Prefer platform-provided creation date
        platform_date = ent.get("platform_first_seen")
        if platform_date:
            first_date = platform_date
            first_src_tag = ent.get("source")  # e.g. leetcode, codeforces
        else:
            handle_key = ent.get("handle") or ent.get("name")
            first_date = first_seen_map.get(handle_key, today_iso)
            first_src_tag = "local"
            first_seen_map.setdefault(handle_key, first_date)

        ent["first_seen"] = first_date
        ent["first_seen_source"] = first_src_tag
        ent["days_active"] = (date.fromisoformat(today_iso) - date.fromisoformat(first_date)).days
        ent["fresh"] = ent["days_active"] < 365

        logger.debug("First seen for %s determined as %s (%s)", ent.get("handle"), first_date, first_src_tag)

    # Compute percentile-normalised score within each source (fair comparison)
    ratings_by_src: dict[str, list[float]] = defaultdict(list)
    for ent in combined_raw:
        ratings_by_src[ent["source"]].append(ent.get("rating", 0.0))

    percentile_map: dict[str, dict[float, float]] = {}
    for src, values in ratings_by_src.items():
        sorted_vals = sorted(values, reverse=True)
        total = len(sorted_vals)
        mapping: dict[float, float] = {}
        for idx, val in enumerate(sorted_vals):
            # Highest rating gets percentile 1.0
            mapping[val] = max(mapping.get(val, 0), 1 - idx / (total - 1) if total > 1 else 1.0)
        percentile_map[src] = mapping

    total_in_src = {src: len(vals) for src, vals in ratings_by_src.items()}

    # -------------------------------------------------------------------
    # Geo-percentile computation (source + country buckets)
    # -------------------------------------------------------------------
    ratings_by_geo: dict[tuple[str, str], list[float]] = defaultdict(list)
    for ent in combined_raw:
        if ent.get("country"):
            ratings_by_geo[(ent["source"], ent["country"])].append(ent.get("rating", 0.0))

    geo_percentile_map: dict[tuple[str, str], dict[float, float]] = {}
    for key, values in ratings_by_geo.items():
        sorted_vals = sorted(values, reverse=True)
        total = len(sorted_vals)
        mapping: dict[float, float] = {}
        for idx, val in enumerate(sorted_vals):
            mapping[val] = max(mapping.get(val, 0.0), 1 - idx / (total - 1) if total > 1 else 1.0)
        geo_percentile_map[key] = mapping

    # Per-source mean & std for later momentum/z-score calc
    source_stats: dict[str, dict[str, float]] = {}
    for src, values in ratings_by_src.items():
        if values:
            mean = sum(values) / len(values)
            var = sum((v - mean) ** 2 for v in values) / len(values)
            source_stats[src] = {"mean": mean, "std": math.sqrt(var) or 1.0}

    for ent in combined_raw:
        src = ent["source"]
        ent["norm"] = percentile_map[src].get(ent.get("rating", 0.0), 0.0)
        # Geo percentile within same country
        country = ent.get("country")
        if country:
            ent["geo_norm"] = geo_percentile_map.get((src, country), {}).get(ent.get("rating", 0.0), 0.0)
        else:
            ent["geo_norm"] = 0.0
        ent["src_weight"] = 1.0  # uniform weight now
        ent["total_in_src"] = total_in_src.get(src, 0)

        # Standardise across platforms: convert percentile → standard-normal z
        p = ent["norm"]
        # Clamp to avoid infinities at 0 or 1
        p = min(max(p, 1e-12), 1 - 1e-12)
        ent["unified_z"] = math.sqrt(2) * erfinv(2 * p - 1)

    # Load yesterday ratings for momentum
    prev_ratings: dict[str, dict[str, float]] = defaultdict(dict)
    try:
        catalog = cache._load_catalog()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        for src, entry in catalog.items():
            if entry.get("fetched_at") == yesterday:
                for u in entry.get("data", []):
                    prev_ratings[src][u.get("handle")] = u.get("rating", 0)
    except Exception:
        pass

    for ent in combined_raw:
        prev = prev_ratings.get(ent["source"], {}).get(ent["handle"])
        if prev is not None and source_stats.get(ent["source"]):
            std = source_stats[ent["source"]]["std"]
            if std:
                ent["delta_sigma"] = (ent.get("rating", 0) - prev) / std
        else:
            ent["delta_sigma"] = 0.0

    logger.info("Resolving entities (%d total raw)", len(combined_raw))
    # Resolve entities and compute versatility BEFORE scoring
    entities = entity_resolution.resolve_entities(combined_raw)

    for e in entities:
        e["versatility"] = len(e.get("handles", {}))

    # Compute rating-based z-score for each resolved entity (avoids percentile saturation)
    for ent in entities:
        src = ent["source"]
        stats = source_stats.get(src)
        if stats and ent.get("rating"):
            ent["rating_z"] = (ent["rating"] - stats["mean"]) / stats["std"]
        else:
            ent["rating_z"] = 0.0

    # Score
    for entity in entities:
        score, reason = scoring.interestingness_score(entity)
        entity["score"] = score
        entity["reason"] = reason

    logger.info("Scoring and ranking %d entities", len(entities))
    # Sort by score desc
    ranked_entities = sorted(entities, key=lambda e: e["score"], reverse=True)[:25]

    logger.info("Writing report for top %d entities", len(ranked_entities))
    # Report top 25
    report.write_markdown_report(ranked_entities)

    # -------------------------------------------------------------------
    # Append country-specific leaderboards (top 5 countries, 5 users each)
    # -------------------------------------------------------------------
    country_counts = Counter([e.get("country") for e in entities if e.get("country")])
    top_countries = [c for c, _ in country_counts.most_common(5)]

    with open("report.md", "a", encoding="utf-8") as fh:
        for country in top_countries:
            top_users = sorted([
                e for e in entities if e.get("country") == country
            ], key=lambda x: x["score"], reverse=True)[:5]
            if not top_users:
                continue
            fh.write(f"\n\n## Top talent in {country}\n")
            for idx, ent in enumerate(top_users, start=1):
                handles = ent.get("handles", {ent.get("source", ""): ent.get("handle", "")})
                handle_display = handles.get("codeforces") or handles.get("atcoder") or next(iter(handles.values()), "")
                fh.write(f"{idx}. {ent['name']} ({handle_display}) — {int(ent['score'])}\n")

    logger.info("Pipeline complete → report.md")

    # Persist updated first-seen map
    try:
        FIRST_SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        FIRST_SEEN_FILE.write_text(json.dumps(first_seen_map, indent=2))
    except Exception as exc:
        logger.warning("Could not save first_seen mapping: %s", exc)

if __name__ == "__main__":
    orchestrate() 