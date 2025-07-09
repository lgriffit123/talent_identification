"""Report module: writes Markdown reports summarising results."""

from typing import List, Dict, Union
from pathlib import Path


def write_markdown_report(entities: List[Dict], output_path: Union[str, Path] = "report.md") -> None:
    """Write a Markdown report summarising the ranked entities.

    Parameters
    ----------
    entities : List[Dict]
        Entities, ideally sorted by interestingness.
    output_path : Union[str, Path], optional
        Destination file path, by default "report.md".
    """
    lines: List[str] = ["# Talent Identification Report", "\n"]

    # Disclaimer about country completeness
    total = len(entities)
    missing_country = sum(1 for e in entities if not e.get("country"))
    leet_missing = sum(1 for e in entities if e.get("source") == "leetcode" and not e.get("country"))
    kag_missing = sum(1 for e in entities if e.get("source") == "kaggle" and not e.get("country"))

    lines.append(
        f"> Note: country metadata is sparse — overall {missing_country}/{total} profiles lack a country code. "
        f"Kaggle missing: {kag_missing}, LeetCode missing: {leet_missing}."
    )
    lines.append("\n")

    for rank, entity in enumerate(entities, start=1):
        name = entity.get("name", "Unknown")
        score = entity.get("score", "N/A")
        reason = entity.get("reason", "")
        # main handle: prefer Codeforces then AtCoder
        handles = entity.get("handles", {entity.get("source", ""): entity.get("handle", "")})
        handle_display = handles.get("codeforces") or handles.get("atcoder") or next(iter(handles.values()), "")

        line = f"## {rank}. {name} ({handle_display}) — {score}"
        if reason:
            line += f"\n> {reason}"

        lines.append(line)

    Path(output_path).write_text("\n".join(lines))

__all__ = ["write_markdown_report"] 