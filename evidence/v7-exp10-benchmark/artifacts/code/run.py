#!/usr/bin/env python3
"""Run V7 Experiment 10, the Glassbox Investigation Benchmark (PROTOCOL.md).

The seed is sealed: the CLI refuses any seed whose sha256 differs from the one in
Addendum 1. GPT-2 small (CPU) is the Family R model. Traces are written to a temporary
directory (regenerable from the seed) and not committed.

Usage:
    python3 experiments/v7/benchmark/run.py --seed "$(cat ~/.glassbox_bench_seed.txt)" \
        --out experiments/v7/benchmark/results
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Sequence

from glassbox.v7.intervene import InterventionSettings

HERE = Path(__file__).resolve().parent
N_PER_CELL = 30
N_PERM = 999
ALPHA = 0.05


def _sibling(name: str) -> ModuleType:
    key = f"exp10_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


GEN, FAM, METH, SCORE = (
    _sibling(n) for n in ("generate", "families", "methods", "score")
)


def progress(msg: str) -> None:
    """Progress line on stderr (no effect on results)."""
    sys.stderr.write(f"[exp10 {time.strftime('%H:%M:%S')}] {msg}\n")
    sys.stderr.flush()


def _select(
    incidents: List[Dict[str, Any]], limit: Optional[int]
) -> List[Dict[str, Any]]:
    if limit is None:
        return incidents
    seen: Dict[Any, int] = {}
    out = []
    for inc in incidents:
        key = (inc["family"], inc["negative"])
        if seen.get(key, 0) < limit:
            out.append(inc)
            seen[key] = seen.get(key, 0) + 1
    return out


def run_benchmark(
    seed: str,
    out: Path,
    scorer: Any = None,
    n_per_cell: int = N_PER_CELL,
    n_perm: int = N_PERM,
    check: bool = True,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Generate the incidents, run every unit and write ``results.json`` (never overwrites).

    ``check=False`` and ``limit`` exist for tests only; the CLI always checks the seed
    and runs everything.
    """
    out = Path(out)
    target = out / "results.json"
    if target.exists():
        raise FileExistsError(f"{target} exists; results are never overwritten")
    if check:
        GEN.check_seed(seed)
    incidents = _select(GEN.generate(seed), limit)
    units: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        for inc in incidents:
            progress(f"incident {inc['id']}: {[f['name'] for f in inc['factors']]}")
            for item in FAM.items(inc["family"]):
                settings = InterventionSettings(
                    n_per_cell, n_perm, ALPHA, f"bench:{inc['id']}:{item}"
                )
                units.append(
                    METH.run_unit(
                        inc, item, Path(tmp) / inc["id"] / item, settings, scorer=scorer
                    )
                )
    scored = SCORE.score(units)
    results = {
        "protocol": "experiments/v7/benchmark/PROTOCOL.md v1.0 + Addendum 1",
        "seed": seed.strip(),
        "seed_sha256": hashlib.sha256(seed.strip().encode("utf-8")).hexdigest(),
        "scorer": type(scorer).__name__ if scorer is not None else None,
        "settings": {
            "n_per_cell": n_per_cell,
            "n_perm": n_perm,
            "alpha": ALPHA,
            "large": SCORE.LARGE,
            "fix_tolerance": 0.10,
        },
        "incidents": incidents,
        "gate11": "MET",
        "v10_1": scored["v10_1"],
        "criteria": scored["criteria"],
        "pooled": scored["pooled"],
        "per_family": scored["per_family"],
        "n_units": scored["n_units"],
        "n_positive_units": scored["n_positive_units"],
        "units": units,
    }
    out.mkdir(parents=True, exist_ok=True)
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(results, indent=1) + "\n")
    return results


def _summary(res: Dict[str, Any]) -> None:
    for name, m in res["pooled"].items():
        line = ", ".join(
            f"{k} {v['value']:.3f} ({v['k']}/{v['n']})"
            for k, v in m.items()
            if isinstance(v, dict) and v["value"] is not None
        )
        sys.stdout.write(f"{name}: {line}\n")
    for k, c in res["criteria"].items():
        sys.stdout.write(
            f"{k}: {'PASS' if c['pass'] else 'FAIL'} {c['value']} {c['rule']}\n"
        )
    sys.stdout.write(f"units {res['n_units']} (positive {res['n_positive_units']})\n")
    sys.stdout.write(
        f"GATE 11: {res['gate11']}   V10.1 (useful vs baselines): {res['v10_1']}\n"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point (always checks the sealed seed, uses GPT-2 small)."""
    parser = argparse.ArgumentParser(description="V7 Experiment 10 benchmark")
    parser.add_argument("--seed", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    GEN.check_seed(args.seed)
    from glassbox.v7.demo_rag import GPT2Scorer

    progress("loading GPT-2 small")
    res = run_benchmark(args.seed, args.out, scorer=GPT2Scorer(), check=True)
    _summary(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
