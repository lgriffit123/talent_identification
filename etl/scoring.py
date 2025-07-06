"""Scoring module: computes an 'interestingness' metric for each entity."""

from typing import Dict, Tuple


def interestingness_score(profile: Dict) -> Tuple[float, str]:
    """Compute the interestingness score and reason for a profile.

    Current heuristic:
    - Base score = rating.
    - Bonus (10%) if the user comes from multiple sources (demonstrates versatility).
    - The reason string explains the contributors.
    """

    if "norm" in profile:
        base_score = profile["norm"] * 1000  # scale to 0-1000
    else:
        rating = profile.get("rating", 0)
        base_score = float(rating)

    multi_source_bonus = 50 if len(profile.get("handles", {})) > 1 else 0.0

    score = base_score + multi_source_bonus

    source = profile.get("source", "unknown")
    reason_components = []
    if "rating" in profile and profile["rating"]:
        reason_components.append(f"rating {profile['rating']}")
    if "rank" in profile:
        reason_components.append(f"rank {profile['rank']}")
    reason_components.append(f"on {source}")
    if multi_source_bonus:
        reason_components.append("active on multiple platforms")

    reason = ", ".join(reason_components)

    return score, reason


__all__ = ["interestingness_score"] 