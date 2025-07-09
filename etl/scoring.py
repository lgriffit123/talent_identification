"""Scoring module: computes an 'interestingness' metric for each entity.

Future ranking ideas
====================
Today we simply sort on the scalar ``score`` returned by
``interestingness_score``.  Below are directions for making the ranking
layer more sophisticated (kept here so reviewers see the roadmap in one
place):

1. **Peer-group normalisation** Rank each user against a cohort of
   similar peers (same platform, region, tenure) and blend that
   percentile into the global score so under-represented regions get
   exposure.

2. **Long-term momentum** Replace the one-day Δσ with an exponentially
   weighted moving average to emphasise sustained
   improvement.

3. **Volatility-adjusted returns** Apply a Sharpe-ratio-like metric to
   reward consistent growth over erratic swings.

5. **Ensemble ranking** Combine multiple rank lists (absolute score,
   momentum, peer rank).

6. **Explainability** Store per-metric contributions so the report can
   state *"Alice is #1 because she's top 0.1 % globally **and** has the
   fastest month-over-month growth in India."*
"""

from typing import Dict, Tuple
import math

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
        base_score = (1 / (1 + math.exp(-z))) * 1000
    else:
        # Simpler: use global percentile directly (0–1 → 0–1000)
        p = min(max(profile.get("norm", 0.0), 0.0), 1.0)
        z = None
        base_score = p * 1000

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
        f"pct {profile.get('norm',0)*100:.1f}%" if z is None else f"z {z:+.2f}",
        f"Δσ {profile.get('delta_sigma',0):+.1f}" if momentum else None,
        f"geo +{int(geo_bonus)} (top {geo_norm*100:.1f}% in {profile.get('country')})" if geo_bonus else None,
        "Rising star" if rising_bonus else None,
        f"rank bonus +{int(rank_bonus)}" if rank_bonus else None,
        f"first seen {profile.get('first_seen')} (local snapshot)" if profile.get('first_seen') else None,
        f"multi-platform ({profile.get('versatility')})" if profile.get('versatility',1)>1 else None,
        # (f"fresh entrant (joined {profile.get('first_seen')} — {profile.get('first_seen_source')})" if fresh_bonus else None),
    ]

    reason = "\n  • " + "\n  • ".join(p for p in reason_parts if p)

    return score, reason


__all__ = ["interestingness_score"] 