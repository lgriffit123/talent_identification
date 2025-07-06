"""Scoring module: computes an 'interestingness' metric for each entity."""

from typing import Dict, Tuple
import math

# Per-source tuning
SRC_BASE_MULT = {"atcoder": 1.2, "kaggle": 1.0, "codeforces": 1.0}
SRC_Z_MULT = {"atcoder": 150, "kaggle": 100, "codeforces": 100}


def interestingness_score(profile: Dict) -> Tuple[float, str]:
    """Compute the interestingness score and reason for a profile.

    Current heuristic:
    - Base score = rating.
    - Bonus (10%) if the user comes from multiple sources (demonstrates versatility).
    - The reason string explains the contributors.
    """

    # Base score scaled by 1000 then weighted by source preference
    norm = profile.get("norm", 0.0)
    base_score = norm * 1000 * SRC_BASE_MULT.get(profile.get("source"), 1.0)

    # Sigmoid z to cap extreme
    z = profile.get("zscore", 0.0)
    z_component = 1 / (1 + math.exp(-z/2))
    z_bonus = (z_component - 0.5) * 1000  # range approx -250..+250

    # Multi-platform bonus
    multi_source_bonus = 50 if len(profile.get("handles", {})) > 1 else 0.0

    # Momentum bonus (delta sigma)
    momentum = profile.get("delta_sigma", 0.0) * 50  # ±50 per std-dev

    # Versatility factor
    versatility_factor = 1 + min(0.25, 0.1 * (profile.get("versatility",1)-1))

    # AtCoder-specific rank bonus to elevate top positions
    rank_bonus = 0.0
    if profile.get("source") == "atcoder" and profile.get("rank") and profile.get("total_in_src"):
        total = profile["total_in_src"]
        if total > 1:
            rank_bonus = (total - profile["rank"] + 1) / total * 300  # up to +300

    score = (base_score + z_bonus + momentum) * versatility_factor + multi_source_bonus + rank_bonus

    # Build reason string
    source = profile.get("source", "unknown")
    reason_parts = [f"rating {int(profile.get('rating', 0))} on {source}"]
    if z_bonus:
        reason_parts.append(f"{profile.get('zscore', 0):+.1f}σ above avg")
    if multi_source_bonus:
        reason_parts.append("active on multiple platforms")
    if profile.get("source") == "atcoder":
        reason_parts.append("AtCoder boost applied")
    if rank_bonus:
        reason_parts.append(f"rank bonus +{int(rank_bonus)}")
    if momentum:
        reason_parts.append(f"momentum {momentum:+.0f}")
    if profile.get("versatility",1) >1:
        reason_parts.append("multi-platform")

    reason = ", ".join(reason_parts)

    return score, reason


__all__ = ["interestingness_score"] 