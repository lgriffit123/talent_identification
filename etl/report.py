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
        lines.append(f"## {rank}. {name} — {score}")

    Path(output_path).write_text("\n".join(lines))

__all__ = ["write_markdown_report"] 