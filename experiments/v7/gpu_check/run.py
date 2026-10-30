#!/usr/bin/env python3
"""Run the V8 phase B GPU sanity check (PROTOCOL.md v1.0).

Runs the built-in RAG investigation (GPT-2 small, all 3 changes, 8 cases) three times
in one session: A cpu/float32 (reference), B cuda/float32 (gated), C cuda/bfloat16
(descriptive). It compares decisions, applies gates G1 and G2 and writes
``results.json`` plus ``run.log``. Nothing is interpreted here; RESULTS.md is written
afterwards from the committed, unchanged results.

Usage (Colab, GPU runtime; see docs/v7/COLAB_GPU.md):
    python3 experiments/v7/gpu_check/run.py --out experiments/v7/gpu_check/results
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import tempfile
import time
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from glassbox.v7 import compute, demo_rag
from glassbox.v7.intervene import InterventionSettings
from glassbox.v7.investigate import investigate

PROTOCOL = "experiments/v7/gpu_check/PROTOCOL.md v1.0"
SETTINGS = InterventionSettings(30, 999, 0.05, "gpu-check")
CONFIGS: Tuple[Tuple[str, str, str, str], ...] = (
    ("A", "cpu", "float32", "reference"),
    ("B", "cuda", "float32", "gated"),
    ("C", "cuda", "bfloat16", "descriptive"),
)
PACKAGES = (
    "glassbox-mech-interp",
    "torch",
    "transformer-lens",
    "transformers",
    "numpy",
)

Env = Dict[str, Any]
ScorerFactory = Callable[[compute.ComputeConfig], Tuple[Any, Env]]
log = logging.getLogger("gpu_check")


def gpt2_factory(config: compute.ComputeConfig) -> Tuple[Any, Env]:
    """Load GPT-2 small on ``config`` and return it with its environment record.

    Raises:
        ValueError: If CUDA is requested but unavailable (infrastructure failure).
    """
    scorer = demo_rag.make_scorer("gpt2", config)
    return scorer, compute.environment_record(scorer.compute)


def run_config(
    cid: str, config: compute.ComputeConfig, factory: ScorerFactory, work: Path
) -> Dict[str, Any]:
    """Run the investigation for one configuration; errors are recorded, not raised."""
    try:
        scorer, env = factory(config)
    except ValueError as exc:
        log.error("%s: %s", cid, exc)
        return {"id": cid, "requested": config.__dict__, "error": str(exc)}
    start = time.perf_counter()
    inv = investigate(demo_rag.make_incident(scorer), work / cid, SETTINGS)
    runtime = time.perf_counter() - start
    log.info("%s: done in %.1fs on %s", cid, runtime, env.get("gpu_name") or "cpu")
    return {
        "id": cid,
        "requested": config.__dict__,
        "environment": env,
        "runtime_s": round(runtime, 3),
        "decisions": {
            f.case: {
                "attributed": sorted(f.attributed),
                "reverting_matters": sorted(f.reverting_matters),
            }
            for f in inv.findings
        },
        "factor_summary": inv.factor_summary(),
        "outcome_counts": {f.case: f.outcome_counts for f in inv.findings},
    }


def compare(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Decision-level comparison of two configuration results."""
    cases = sorted(set(a["decisions"]) | set(b["decisions"]))
    differing = [
        {"case": c, "a": a["decisions"].get(c), "b": b["decisions"].get(c)}
        for c in cases
        if a["decisions"].get(c) != b["decisions"].get(c)
    ]
    summary_equal = a["factor_summary"] == b["factor_summary"]
    return {
        "identical": summary_equal and not differing,
        "summary_equal": summary_equal,
        "differing_cases": differing,
    }


def gate(results: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Apply G1 and G2 (PROTOCOL.md section 4) to configurations A and B."""
    by_id = {r["id"]: r for r in results}
    a, b = by_id.get("A"), by_id.get("B")
    if not a or not b or "error" in a or "error" in b:
        return {
            "G1": {"pass": None},
            "G2": {"pass": None},
            "overall": "INFRASTRUCTURE_FAILURE",
        }
    cmp = compare(a, b)
    env_a, env_b = a["environment"], b["environment"]
    g2 = bool(
        env_b.get("gpu_name") and env_b.get("cuda_version") and env_a["device"] == "cpu"
    )
    passed = cmp["identical"] and g2
    return {
        "G1": {"pass": cmp["identical"], **cmp},
        "G2": {"pass": g2},
        "overall": "PASS" if passed else "FAIL",
    }


def describe_c(
    a: Dict[str, Any], c: Optional[Dict[str, Any]]
) -> Optional[Dict[str, int]]:
    """Descriptive only: how many of C's cases match A's decisions."""
    if not c or "error" in c or "error" in a:
        return None
    return {
        "cases": len(c["decisions"]),
        "matching_A": sum(
            a["decisions"].get(k) == v for k, v in c["decisions"].items()
        ),
    }


def _software() -> Dict[str, Optional[str]]:
    found: Dict[str, Optional[str]] = {}
    for name in PACKAGES:
        try:
            found[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            found[name] = None
    try:
        found["git_commit"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        found["git_commit"] = None
    return found


def main(
    argv: Optional[Sequence[str]] = None, scorer_factory: ScorerFactory = gpt2_factory
) -> int:
    """Run A, B and C, write results.json and run.log; exit 0 unless infra failed."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    out: Path = args.out
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} is not empty; choose a new directory")
    out.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(out / "run.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        log.info("protocol %s, settings %s", PROTOCOL, SETTINGS.__dict__)
        results: List[Dict[str, Any]] = []
        with tempfile.TemporaryDirectory() as tmp:
            for cid, device, dtype, _role in CONFIGS:
                log.info("%s: start (%s, %s)", cid, device, dtype)
                cfg = compute.ComputeConfig(device, dtype)
                results.append(run_config(cid, cfg, scorer_factory, Path(tmp)))
        gates = gate(results)
        log.info("overall: %s", gates["overall"])
        payload = {
            "protocol": PROTOCOL,
            "settings": SETTINGS.__dict__,
            "software": _software(),
            "configurations": results,
            "gates": gates,
            "descriptive_C": describe_c(results[0], results[2]),
        }
        (out / "results.json").write_text(
            json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
        )
    finally:
        log.removeHandler(handler)
        handler.close()
    sys.stdout.write(f"overall: {gates['overall']}\nresults: {out / 'results.json'}\n")
    return 1 if gates["overall"] == "INFRASTRUCTURE_FAILURE" else 0


if __name__ == "__main__":
    sys.exit(main())
