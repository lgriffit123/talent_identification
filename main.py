"""Main orchestrator script.

This script can be scheduled (e.g., cron or CI) or run ad-hoc to perform the
full pipeline: ingest data, resolve entities, score them, and generate a
report.
"""

from ingest import codeforces, kaggle
from etl import entity_resolution, scoring, report


def orchestrate() -> None:
    """Run the full talent identification pipeline."""
    # Ingest
    cf_raw = codeforces.fetch_ratings()
    kg_raw = kaggle.fetch_leaderboard()

    combined_raw = cf_raw + kg_raw

    # Resolve entities
    entities = entity_resolution.resolve_entities(combined_raw)

    # Score
    for entity in entities:
        entity["score"] = scoring.interestingness_score(entity)

    # Sort by score desc
    ranked_entities = sorted(entities, key=lambda e: e["score"], reverse=True)

    # Report
    report.write_markdown_report(ranked_entities)


if __name__ == "__main__":
    orchestrate() 