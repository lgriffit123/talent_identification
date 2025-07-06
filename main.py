"""Main orchestrator script.

This script can be scheduled (e.g., cron or CI) or run ad-hoc to perform the
full pipeline: ingest data, resolve entities, score them, and generate a
report.
"""

import os, logging, math, json
from ingest import codeforces, kaggle, atcoder, cache
from etl import entity_resolution, scoring, report
from collections import defaultdict


# ---------------------------------------------------------------------------
# Logging setup (controlled by TI_LOGLEVEL, default INFO)
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("TI_LOGLEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


def orchestrate() -> None:
    """Run the full talent identification pipeline."""
    logger.info("Starting ingestion phase")

    cf_raw = codeforces.fetch_ratings()
    ac_raw = atcoder.fetch_ratings()
    kg_raw = kaggle.fetch_leaderboard()

    logger.info(
        "Fetched counts — Codeforces: %d, AtCoder: %d, Kaggle: %d",
        len(cf_raw), len(ac_raw), len(kg_raw),
    )

    combined_raw = cf_raw + ac_raw + kg_raw

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

    for ent in combined_raw:
        src = ent["source"]
        ent["norm"] = percentile_map[src].get(ent.get("rating", 0.0), 0.0)
        ent["src_weight"] = 1.0  # uniform weight now
        ent["total_in_src"] = total_in_src.get(src, 0)

    # Load yesterday ratings for momentum
    prev_ratings: dict[str, dict[str, float]] = defaultdict(dict)
    try:
        catalog = cache._load_catalog()
        from datetime import date, timedelta
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
    # Resolve entities
    entities = entity_resolution.resolve_entities(combined_raw)

    # Compute per-source mean and std for z-score
    source_stats: dict[str, dict[str, float]] = {}
    for src, group in ((s, [e for e in combined_raw if e["source"] == s and e.get("rating")]) for s in set(e["source"] for e in combined_raw)):
        ratings = [e["rating"] for e in group if e.get("rating")]
        if ratings:
            mean = sum(ratings) / len(ratings)
            var = sum((r - mean) ** 2 for r in ratings) / len(ratings)
            source_stats[src] = {"mean": mean, "std": math.sqrt(var) or 1.0}

    for ent in combined_raw:
        src = ent["source"]
        stats = source_stats.get(src)
        if stats and ent.get("rating"):
            ent["zscore"] = (ent["rating"] - stats["mean"]) / stats["std"]
        else:
            ent["zscore"] = 0.0

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
    logger.info("Pipeline complete → report.md")

    # Compute versatility count
    for e in entities:
        e["versatility"] = len(e.get("handles", {}))


if __name__ == "__main__":
    orchestrate() 