"""Scoring module: computes an 'interestingness' metric for each entity."""

from typing import Dict, Tuple
import math
from etl.utils import erfinv

# No per-source default multipliers now


def interestingness_score(profile: Dict) -> Tuple[float, str]:
    """Compute the interestingness score and reason for a profile.

    Current heuristic:
    - Base score = percentile + capped z-score.
    - Bonus (10%) if the user comes from multiple sources (demonstrates versatility).
    - The reason string explains the contributors.
    """

    # Primary z: per-source rating z-score (avoids percentile saturation).
    if "rating_z" in profile:
        z = profile["rating_z"]
    elif "unified_z" in profile:
        z = profile["unified_z"]
    else:
        # Fallback – derive from percentile if caller hasn't provided any z yet
        p = min(max(profile.get("norm", 0.0), 1e-12), 1 - 1e-12)
        z = math.sqrt(2) * erfinv(2 * p - 1)

    # Map z to a 0-1 score via sigmoid and stretch to 0-1000
    sigmoid = 1 / (1 + math.exp(-z))  # 0–1
    base_score = sigmoid * 1000

    z_bonus = 0  # no separate bonus – z already captured

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

    # --------------------------- NEW BONUSES ---------------------------
    # Geography bonus – reward top performers within their country bucket
    geo_norm = profile.get("geo_norm", 0.0)
    geo_bonus = (geo_norm ** 2) * 100  # squared to emphasise top spots (max +100)

    # Rising-star bonus if yesterday-to-today sigma jump is significant
    rising_bonus = 50 if profile.get("delta_sigma", 0.0) > 1.5 else 0.0

    # -------------------------------------------------------------------

    # Fresh-entrant bonus (less than 1 year since first seen)
    # fresh_bonus = 25 if profile.get("fresh") else 0.0  # ← commented out for now

    score = (base_score + momentum + geo_bonus + rising_bonus) * versatility_factor + multi_source_bonus + rank_bonus  # + fresh_bonus

    source = profile.get("source", "unknown")
    reason_parts = [
        f"rating {int(profile.get('rating', 0))} on {source}",
        f"z {z:+.2f}",
        f"Δσ {profile.get('delta_sigma',0):+.1f}" if momentum else None,
        f"geo +{int(geo_bonus)} (top {geo_norm*100:.1f}% in {profile.get('country')})" if geo_bonus else None,
        "Rising star" if rising_bonus else None,
        f"rank bonus +{int(rank_bonus)}" if rank_bonus else None,
        f"multi-platform ({profile.get('versatility')})" if profile.get('versatility',1)>1 else None,
        # (f"fresh entrant (joined {profile.get('first_seen')} — {profile.get('first_seen_source')})" if fresh_bonus else None),
    ]

    reason = "\n  • " + "\n  • ".join(p for p in reason_parts if p)

    return score, reason


__all__ = ["interestingness_score"] 