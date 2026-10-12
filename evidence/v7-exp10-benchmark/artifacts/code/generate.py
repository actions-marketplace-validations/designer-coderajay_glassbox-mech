"""Case generator for V7 Experiment 10 (PROTOCOL.md §2 and Addendum 1).

All draws come from one seed. The real seed is sealed: only its sha256 is in the
protocol, and :func:`check_seed` refuses any other value.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, List, Sequence, Tuple

SEED_SHA256 = "7dff29241343a904eda8c01a9e49790b3cbd988f1cad6e756a5638a1d79b3742"

R_EFFECT: Tuple[str, ...] = ("index", "top_k", "template", "preamble")
R_INERT: Tuple[str, ...] = ("log_level", "cache_mode")
R_BASE: Dict[str, Any] = {
    "index": "full",
    "top_k": 1,
    "template": "context_first",
    "preamble": "none",
    "log_level": "info",
    "cache_mode": "off",
}
R_CANDIDATE: Dict[str, Any] = {
    "index": "stale",
    "top_k": 2,
    "template": "question_first",
    "preamble": "one_word",
    "log_level": "debug",
    "cache_mode": "on",
}

S_EFFECT: Tuple[str, ...] = (
    "skip_check",
    "early_stop",
    "wrong_order",
    "resend_bias",
    "framework_retry",
)
S_INERT: Tuple[str, ...] = ("log_level", "trace_sampling")
S_BASE: Dict[str, Any] = {
    "skip_check": 0.95,
    "early_stop": 0.02,
    "wrong_order": 0.03,
    "resend_bias": 0.02,
    "framework_retry": "v1",
    "log_level": "info",
    "trace_sampling": "off",
}
S_RANGES: Dict[str, Tuple[float, float]] = {
    "skip_check": (0.05, 0.90),
    "early_stop": (0.05, 0.80),
    "wrong_order": (0.05, 0.80),
    "resend_bias": (0.05, 0.90),
}
S_FIXED_CANDIDATE: Dict[str, Any] = {
    "framework_retry": "v2",
    "log_level": "debug",
    "trace_sampling": "on",
}
COUNTS = (("R", False, 12), ("R", True, 4), ("S", False, 12), ("S", True, 4))


def check_seed(seed: str) -> None:
    """Raise ``ValueError`` unless ``sha256(seed)`` equals the sealed hash."""
    digest = hashlib.sha256(seed.strip().encode("utf-8")).hexdigest()
    if digest != SEED_SHA256:
        raise ValueError("seed does not match the sealed sha256 in PROTOCOL.md")


def _candidate(family: str, name: str, rng: random.Random) -> Any:
    if family == "R":
        return R_CANDIDATE[name]
    if name in S_RANGES:
        lo, hi = S_RANGES[name]
        return round(rng.uniform(lo, hi), 3)
    return S_FIXED_CANDIDATE[name]


def _pick(family: str, negative: bool, rng: random.Random) -> List[str]:
    effect, inert = (R_EFFECT, R_INERT) if family == "R" else (S_EFFECT, S_INERT)
    if negative:
        return rng.sample(list(inert), rng.randint(1, 2))
    k = rng.choice([2, 3, 4])
    n_inert = rng.randint(1, min(2, k - 1))
    return rng.sample(list(effect), k - n_inert) + rng.sample(list(inert), n_inert)


def generate(seed: str) -> List[Dict[str, Any]]:
    """The 32 incidents, in a fixed order (R positives, R negatives, S, S negatives)."""
    rng = random.Random(hashlib.sha256(seed.strip().encode("utf-8")).hexdigest())
    out: List[Dict[str, Any]] = []
    for family, negative, n in COUNTS:
        base = R_BASE if family == "R" else S_BASE
        for i in range(1, n + 1):
            names = _pick(family, negative, rng)
            factors = [
                {
                    "name": name,
                    "base": base[name],
                    "candidate": _candidate(family, name, rng),
                }
                for name in names
            ]
            tag = f"{family}{'N' if negative else ''}{i:02d}"
            out.append(
                {"id": tag, "family": family, "negative": negative, "factors": factors}
            )
    return out


def factor_names(incident: Dict[str, Any]) -> Sequence[str]:
    """Names of the changed factors of an incident."""
    return [f["name"] for f in incident["factors"]]
