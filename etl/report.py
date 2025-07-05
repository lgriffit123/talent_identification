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