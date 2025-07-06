"""Main orchestrator script.

This script can be scheduled (e.g., cron or CI) or run ad-hoc to perform the
full pipeline: ingest data, resolve entities, score them, and generate a
report.
"""

import os, logging
from ingest import codeforces, kaggle, atcoder
from etl import entity_resolution, scoring, report


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

    # Build per-source max rating for normalization
    max_rating: dict[str, int] = {}
    for ent in combined_raw:
        src = ent["source"]
        r = ent.get("rating", 0)
        if r and r > max_rating.get(src, 0):
            max_rating[src] = r

    # Fallback to rank-based scale if rating missing for a source
    max_rank: dict[str, int] = {}
    for ent in combined_raw:
        src = ent["source"]
        rank_val = ent.get("rank")
        if isinstance(rank_val, (int, float)):
            rank_int = int(rank_val)
            max_rank[src] = max(rank_int, max_rank.get(src, 0))

    for ent in combined_raw:
        src = ent["source"]
        if max_rating.get(src, 0) > 0 and ent.get("rating"):
            ent["norm"] = ent["rating"] / max_rating[src]
        elif src in max_rank and isinstance(ent.get("rank"), (int, float)):
            ent["norm"] = (max_rank[src] - int(ent["rank"]) + 1) / max_rank[src]
        else:
            ent["norm"] = 0.0

    logger.info("Resolving entities (%d total raw)", len(combined_raw))
    # Resolve entities
    entities = entity_resolution.resolve_entities(combined_raw)

    # Score
    for entity in entities:
        score, reason = scoring.interestingness_score(entity)
        entity["score"] = score
        entity["reason"] = reason

    logger.info("Scoring and ranking %d entities", len(entities))
    # Sort by score desc
    ranked_entities = sorted(entities, key=lambda e: e["score"], reverse=True)

    logger.info("Writing report for top %d entities", len(ranked_entities))
    # Report
    report.write_markdown_report(ranked_entities)
    logger.info("Pipeline complete → report.md")


if __name__ == "__main__":
    orchestrate() 