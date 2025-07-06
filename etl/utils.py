"""Utility helpers for ETL layer."""

import math
from typing import Callable

if hasattr(math, "erfinv"):
    erfinv: Callable[[float], float] = math.erfinv  # type: ignore[attr-defined]
else:
    # Polynomial approximation for inverse error function (Winitzki, 2008)
    # Accuracy ~1.5e-4 over |x|<1, sufficient for scoring purposes.
    def _erfinv(x: float) -> float:  # noqa: D401
        """Approximate inverse error function for -1 < x < 1."""
        if x <= -1 or x >= 1:
            if x == 1:
                return math.inf
            if x == -1:
                return -math.inf
            raise ValueError("erfinv domain must be -1 < x < 1")
        a = 0.147  # magic constant
        sign = 1 if x >= 0 else -1
        ln = math.log(1 - x * x)
        first = 2 / (math.pi * a) + ln / 2
        second = ln / a
        return sign * math.sqrt(math.sqrt(first * first - second) - first)

    erfinv = _erfinv  # type: ignore[assignment]

__all__ = ["erfinv"] 