#!/usr/bin/env python3
"""Experiment 7b, Addendum 3: are the run 1 / run 2 differences floating-point order effects?

Recomputes the competence of ``Qwen/Qwen2.5-0.5B-Instruct`` (run 1 0.327629,
run 2 0.327631) in four separate processes on one machine:

* ``A1``, ``A2``: default settings, twice;
* ``B_threads1``: one BLAS/OpenMP thread (changes how sums are split);
* ``C_scalar``: ``ATEN_CPU_CAPABILITY=default`` (no vectorised kernels, which changes
  summation order the way a different CPU instruction set would).

Pre-declared criteria (PROTOCOL.md Addendum 3):

* **E1:** ``A1`` and ``A2`` are bit-identical (repeatable within one setting);
* **E2:** ``B`` or ``C`` differs from ``A1`` by more than 0 and at most ``TOL``
  (a last-digits change of summation order);
* **E3:** every value is within ``TOL`` of both run 1 and run 2, and below 0.6, so the
  ladder decision is the same.

EXPLAINED iff E1, E2 and E3 all hold.

Usage:
    python3 experiments/v7/agent_b/explain_numeric.py --out experiments/v7/agent_b/numeric_check
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, Optional, Sequence

HERE = Path(__file__).resolve().parent
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
RUN1 = 0.327629
RUN2 = 0.327631
TOL = 1e-4
THRESHOLD = 0.6


@dataclass(frozen=True)
class Config:
    """One process setting: a name and the environment variables it adds."""

    name: str
    env: Dict[str, str] = field(default_factory=dict)


CONFIGS = (
    Config("A1"),
    Config("A2"),
    Config("B_threads1", {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}),
    Config("C_scalar", {"ATEN_CPU_CAPABILITY": "default"}),
)


def format_value(value: float) -> str:
    """Full-precision text form of a float (round-trips exactly)."""
    return repr(value)


def cpu_info(path: Path = Path("/proc/cpuinfo")) -> Dict[str, Any]:
    """CPU model name, logical CPU count and AVX2/AVX-512 flags from ``/proc/cpuinfo``."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"model_name": None, "logical_cpus": 0, "avx2": None, "avx512f": None}
    model: Optional[str] = None
    flags: set = set()
    count = 0
    for line in text.splitlines():
        key, _, value = line.partition(":")
        key = key.strip()
        if key == "processor":
            count += 1
        elif key == "model name" and model is None:
            model = value.strip()
        elif key == "flags" and not flags:
            flags = set(value.split())
    return {
        "model_name": model,
        "logical_cpus": count,
        "avx2": "avx2" in flags,
        "avx512f": "avx512f" in flags,
    }


def _load_run7b() -> ModuleType:
    spec = importlib.util.spec_from_file_location("exp7b_run_numeric", HERE / "run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def measure_single(factory: Optional[Callable[[str], Any]] = None) -> float:
    """Competence of ``MODEL`` with a fresh score cache, exactly as run.py computes it."""
    r7b = _load_run7b()
    scorer = (factory or r7b.load_exp7().default_factory)(MODEL)
    labels = r7b.choose_labels(getattr(scorer, "model"))
    assert labels is not None, "no single-token label set"
    return float(r7b.competence(r7b.MenuPolicy(scorer, labels)))


def evaluate(values: Dict[str, float]) -> Dict[str, Any]:
    """Apply E1–E3 to the four measured values."""
    a1 = values["A1"]
    e1 = values["A1"] == values["A2"]
    moves = {k: abs(values[k] - a1) for k in ("B_threads1", "C_scalar")}
    e2 = any(0.0 < d <= TOL for d in moves.values())
    e3 = all(
        abs(v - RUN1) <= TOL and abs(v - RUN2) <= TOL and v < THRESHOLD
        for v in values.values()
    )
    return {
        "E1_within_setting_identical": e1,
        "E2_order_sensitive": e2,
        "E3_close_and_same_decision": e3,
        "moves_vs_A1": moves,
        "verdict": "EXPLAINED" if (e1 and e2 and e3) else "NOT EXPLAINED",
    }


def _torch_report() -> Dict[str, Any]:
    import torch

    try:
        capability = torch.backends.cpu.get_cpu_capability()
    except AttributeError:
        capability = None
    return {
        "torch": torch.__version__,
        "threads": torch.get_num_threads(),
        "aten_cpu_capability": capability,
    }


def _run_config(cfg: Config) -> Dict[str, Any]:
    env = {**os.environ, **cfg.env}
    proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--single"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    sys.stderr.write(proc.stderr)
    last = [ln for ln in proc.stdout.splitlines() if ln.startswith("{")][-1]
    record: Dict[str, Any] = json.loads(last)
    record["config"] = cfg.name
    record["env"] = cfg.env
    return record


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: orchestrate the four processes, or (``--single``) measure once."""
    parser = argparse.ArgumentParser(description="Exp 7b Addendum 3 numeric check")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--single", action="store_true")
    args = parser.parse_args(argv)
    if args.single:
        value = measure_single()
        sys.stdout.write(
            json.dumps({"value": format_value(value), **_torch_report()}) + "\n"
        )
        return 0
    if args.out is None:
        parser.error("--out is required")
    target = args.out / "numeric_check.json"
    if target.exists():
        raise FileExistsError(f"{target} exists; results are never overwritten")
    args.out.mkdir(parents=True, exist_ok=True)
    records = [_run_config(cfg) for cfg in CONFIGS]
    values = {r["config"]: float(r["value"]) for r in records}
    result = {
        "protocol": "experiments/v7/agent_b/PROTOCOL.md Addendum 3",
        "model": MODEL,
        "reference": {"run1": RUN1, "run2": RUN2, "tol": TOL},
        "machine": {
            **cpu_info(),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "records": records,
        "evaluation": evaluate(values),
    }
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(result, indent=1) + "\n")
    sys.stdout.write(json.dumps(result, indent=1) + "\n")
    sys.stdout.write(f"ADDENDUM 3 VERDICT: {result['evaluation']['verdict']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
