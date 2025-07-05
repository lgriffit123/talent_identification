"""Scoring module: computes an 'interestingness' metric for each entity."""

from typing import Dict, Tuple


def interestingness_score(profile: Dict) -> Tuple[float, str]:
    """Compute the interestingness score and reason for a profile.

    Current heuristic:
    - Base score = rating.
    - Bonus (10%) if the user comes from multiple sources (demonstrates versatility).
    - The reason string explains the contributors.
    """

    rating = profile.get("rating", 0)
    base_score: float = float(rating)

    multi_source_bonus = 0.1 * base_score if len(profile.get("handles", {})) > 1 else 0.0

    score = base_score + multi_source_bonus

    source = profile.get("source", "unknown")
    reason = f"Rating {rating} on {source}"
    if multi_source_bonus:
        reason += ", active on multiple platforms"

    return score, reason


__all__ = ["interestingness_score"] 