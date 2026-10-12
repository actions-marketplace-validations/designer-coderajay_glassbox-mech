"""Metrics M1–M7 and criteria K1–K5 of V7 Experiment 10 (PROTOCOL.md §4, §6).

Classes from exact ground truth: large ≥ 0.5, zero == 0.0. Descriptive "small" units are
units whose largest effect lies in [0.1, 0.5); for them, the target set is the factors
with effect ≥ 0.1 (defined here, descriptive only, not gated).
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

LARGE = 0.5
SMALL_LO = 0.1
METHODS = ("GB", "B0", "B1")


def wilson(k: int, n: int, z: float = 1.96) -> Tuple[Optional[float], Optional[float]]:
    """95% Wilson interval for k successes out of n (``(None, None)`` if n == 0)."""
    if n == 0:
        return None, None
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, round(centre - half, 6)), min(1.0, round(centre + half, 6))


def _rate(k: int, n: int) -> Dict[str, Any]:
    lo, hi = wilson(k, n)
    return {"k": k, "n": n, "value": (k / n) if n else None, "wilson95": [lo, hi]}


def _large(unit: Dict[str, Any]) -> set:
    return {f for f, v in unit["truth"].items() if v >= LARGE}


def _metrics(units: Sequence[Dict[str, Any]], method: str) -> Dict[str, Any]:
    pos = [u for u in units if _large(u)]
    det = sum(u["methods"][method]["detected"] for u in pos)
    exact = sum(set(u["methods"][method]["blamed"]) == _large(u) for u in pos)
    hit = sum(len(set(u["methods"][method]["blamed"]) & _large(u)) for u in pos)
    n_large = sum(len(_large(u)) for u in pos)
    zero_pairs = [(u, f) for u in units for f, v in u["truth"].items() if v == 0.0]
    false_blame = sum(f in u["methods"][method]["blamed"] for u, f in zero_pairs)
    neg = [u for u in units if u["negative"]]
    alarms = sum(
        bool(u["methods"][method]["detected"] or u["methods"][method]["blamed"])
        for u in neg
    )
    fixable = [u for u in pos if u["methods"][method]["detected"]]
    fixed = sum(u["methods"][method]["fix_tvd"] <= 0.10 for u in fixable)
    small = [
        u
        for u in units
        if not _large(u) and u["truth"] and SMALL_LO <= max(u["truth"].values()) < LARGE
    ]
    small_target = [{f for f, v in u["truth"].items() if v >= SMALL_LO} for u in small]
    small_exact = sum(
        set(u["methods"][method]["blamed"]) == t for u, t in zip(small, small_target)
    )
    small_hit = sum(
        len(set(u["methods"][method]["blamed"]) & t)
        for u, t in zip(small, small_target)
    )
    return {
        "M1_detection": _rate(det, len(pos)),
        "M2_exact_diagnosis": _rate(exact, len(pos)),
        "M3_large_recall": _rate(hit, n_large),
        "M4_zero_false_blame": _rate(false_blame, len(zero_pairs)),
        "M5_false_alarm": _rate(alarms, len(neg)),
        "M6_fix_verified": _rate(fixed, len(fixable)),
        "M7_mean_runs": (sum(u["runs"] for u in units) / len(units)) if units else None,
        "small_M2_exact": _rate(small_exact, len(small)),
        "small_M3_recall": _rate(small_hit, sum(len(t) for t in small_target)),
    }


def _value(m: Dict[str, Any], key: str) -> Optional[float]:
    v = m[key]["value"]
    return None if v is None else float(v)


def criteria(pooled: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """K1–K5 on the pooled numbers (None counts as fail)."""
    gb = pooled["GB"]
    m2 = _value(gb, "M2_exact_diagnosis")
    best = max((_value(pooled[b], "M2_exact_diagnosis") or 0.0) for b in ("B0", "B1"))
    m4 = _value(gb, "M4_zero_false_blame")
    m5 = _value(gb, "M5_false_alarm")
    m6 = _value(gb, "M6_fix_verified")
    return {
        "K1": {"value": m2, "rule": ">= 0.70", "pass": m2 is not None and m2 >= 0.70},
        "K2": {
            "value": None if m2 is None else round(m2 - best, 6),
            "rule": ">= +0.15 over the better baseline",
            "pass": m2 is not None and m2 - best >= 0.15,
        },
        "K3": {"value": m4, "rule": "<= 0.05", "pass": m4 is not None and m4 <= 0.05},
        "K4": {"value": m5, "rule": "<= 0.10", "pass": m5 is not None and m5 <= 0.10},
        "K5": {"value": m6, "rule": ">= 0.80", "pass": m6 is not None and m6 >= 0.80},
    }


def score(units: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Per-family and pooled metrics for every method, plus K1–K5."""
    families = sorted({u["family"] for u in units})
    per_family = {
        fam: {m: _metrics([u for u in units if u["family"] == fam], m) for m in METHODS}
        for fam in families
    }
    pooled = {m: _metrics(units, m) for m in METHODS}
    crit = criteria(pooled)
    return {
        "per_family": per_family,
        "pooled": pooled,
        "criteria": crit,
        "v10_1": "PASS" if all(c["pass"] for c in crit.values()) else "FAIL",
        "n_units": len(units),
        "n_positive_units": sum(bool(_large(u)) for u in units),
    }
