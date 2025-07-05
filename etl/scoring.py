"""Scoring module: computes an 'interestingness' metric for each entity."""

from typing import Dict


def interestingness_score(profile: Dict) -> float:
    """Compute the interestingness score for a given profile.

    Parameters
    ----------
    profile : Dict
        Entity profile with enriched attributes.

    Returns
    -------
    float
        Calculated score (higher is more interesting).
    """
    # TODO: Replace with meaningful formula.
    return 0.0

__all__ = ["interestingness_score"] 