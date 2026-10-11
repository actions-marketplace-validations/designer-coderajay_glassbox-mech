#!/usr/bin/env python3
"""V7 Experiment 4: controlled one-factor interventions (PROTOCOL.md, commit 30ce32f).

Reuses Experiment 3's synthetic pipeline unchanged (``simulate_run`` from
``experiments/v7/noise_baseline/part_a.py``). Factors: ``retrieval_r`` and ``chat_cr``
(real effects) and ``log_level`` (inert; recorded on the root span as
``glassbox.env.log_level``, no effect on behaviour). Outcome: the ``chat`` span's
``glassbox.answer.label``. For worlds V0–V2 and replications 0–199, runs
``glassbox.v7.intervene.run_interventions`` with 50 runs per cell, keeps a summary,
and deletes the traces.

Usage (stdlib + glassbox only):
    python3 experiments/v7/intervention/run.py --out experiments/v7/intervention/results
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Iterator, List, Optional, Sequence

from glassbox.v7.groupdiff import group_diff
from glassbox.v7.intervene import Factor, InterventionSettings, run_interventions
from glassbox.v7.trace import Recorder, read_trace

HERE = Path(__file__).resolve().parent
EXP3 = HERE.parent / "noise_baseline" / "part_a.py"
MASTER_SEED = 20261011
N_PER_CELL = 50
REPLICATIONS = 200
N_PERM = 999
ALPHA = 0.05
C_W = 0.20
RETRIEVAL = Factor("retrieval_r", base=0.90, candidate=0.40)
CHAT = Factor("chat_cr", base=0.85, candidate=0.35)
INERT = Factor("log_level", base="info", candidate="debug")
WORLDS: Dict[str, List[Factor]] = {
    "V0": [INERT],
    "V1": [RETRIEVAL, INERT],
    "V2": [RETRIEVAL, CHAT],
}
DEFAULTS: Dict[str, Any] = {"retrieval_r": 0.90, "chat_cr": 0.85, "log_level": "info"}


def load_exp3() -> ModuleType:
    """Load Experiment 3 Part A by path."""
    spec = importlib.util.spec_from_file_location("exp3_part_a_iv", EXP3)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def _root_env(exp3: ModuleType, env: Dict[str, str]) -> Iterator[None]:
    """Make ``exp3.simulate_run`` record extra root environment attributes."""

    class _EnvRecorder(Recorder):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self.environment.update(env)

    original = exp3.Recorder
    exp3.Recorder = _EnvRecorder
    try:
        yield
    finally:
        exp3.Recorder = original


class PipelineRunner:
    """Runner for :func:`run_interventions` over Experiment 3's pipeline."""

    def __init__(self, exp3: ModuleType) -> None:
        self.exp3 = exp3

    def __call__(
        self, config: Dict[str, Any], seed: int, out: Path, run_id: str
    ) -> Path:
        cfg = {**DEFAULTS, **config}
        params = self.exp3.Params(r=cfg["retrieval_r"], c_r=cfg["chat_cr"], c_w=C_W)
        with _root_env(self.exp3, {"glassbox.env.log_level": str(cfg["log_level"])}):
            path: Path = self.exp3.simulate_run(
                random.Random(seed), params, out, run_id
            )
        return path


def label_outcome(path: Path) -> str:
    """The ``chat`` span's answer label."""
    spans, _ = read_trace(path)
    chat = [s for s in spans if s["attributes"].get("gen_ai.operation.name") == "chat"]
    return str(chat[0]["attributes"]["glassbox.answer.label"])


def replicate(exp3: ModuleType, world: str, rep: int) -> Dict[str, Any]:
    """One replication of one world; returns a summary (traces are deleted)."""
    settings = InterventionSettings(
        N_PER_CELL, N_PERM, ALPHA, f"{MASTER_SEED}:{world}:{rep}"
    )
    with tempfile.TemporaryDirectory() as tmp:
        report = run_interventions(
            WORLDS[world], PipelineRunner(exp3), label_outcome, Path(tmp), settings
        )
        diff_chat: Optional[bool] = None
        if world == "V1":
            gd = group_diff(
                report.paths["baseline"],
                report.paths["candidate"],
                N_PERM,
                ALPHA,
                rep,
                merge_redundant=True,
            )
            diff_chat = any(f.step == "chat#0" for f in gd.significant)
    return {
        "attributed": report.attributed,
        "total_significant": report.total.significant,
        "necessity_significant": [t.factor for t in report.necessity if t.significant],
        "counts": {k: v.counts for k, v in report.cells.items()},
        "diff_flags_chat": diff_chat,
    }


def _rate(xs: Sequence[bool]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def evaluate(summaries: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    """Apply PROTOCOL.md §4 criteria."""

    def attr(world: str, factor: str) -> float:
        return _rate([factor in s["attributed"] for s in summaries[world]])

    i1 = attr("V0", "log_level")
    i2, i3 = attr("V1", "retrieval_r"), attr("V1", "log_level")
    i4 = _rate(
        [{"retrieval_r", "chat_cr"} <= set(s["attributed"]) for s in summaries["V2"]]
    )
    return {
        "I1_type_I": {"rate": i1, "rule": "<= 0.08", "pass": i1 <= 0.08},
        "I2_single_cause": {"rate": i2, "rule": ">= 0.80", "pass": i2 >= 0.80},
        "I3_inert_not_blamed": {"rate": i3, "rule": "<= 0.08", "pass": i3 <= 0.08},
        "I4_two_causes": {"rate": i4, "rule": ">= 0.80", "pass": i4 >= 0.80},
        "I5_total_change": {
            w: _rate([s["total_significant"] for s in summaries[w]])
            for w in ("V1", "V2")
        },
        "I6_necessity": {
            w: {
                f.name: _rate(
                    [f.name in s["necessity_significant"] for s in summaries[w]]
                )
                for f in WORLDS[w]
            }
            for w in ("V1", "V2")
        },
        "I7_diff_vs_intervention_V1": {
            "group_diff_flags_chat": _rate(
                [bool(s["diff_flags_chat"]) for s in summaries["V1"]]
            ),
            "interventions_attribute_other_than_retrieval": _rate(
                [bool(set(s["attributed"]) - {"retrieval_r"}) for s in summaries["V1"]]
            ),
        },
    }


GATED = ("I1_type_I", "I2_single_cause", "I3_inert_not_blamed", "I4_two_causes")


def overall(criteria: Dict[str, Any]) -> str:
    """PASS iff every gated criterion passes."""
    return "PASS" if all(criteria[g]["pass"] for g in GATED) else "FAIL"


def run(out: Path, reps: int = REPLICATIONS) -> Dict[str, Any]:
    """Run every world and replication; write ``results.json`` (never overwrites)."""
    out.mkdir(parents=True, exist_ok=True)
    target = out / "results.json"
    if target.exists():
        raise FileExistsError(f"{target} exists; results are never overwritten")
    exp3 = load_exp3()
    summaries = {w: [replicate(exp3, w, i) for i in range(reps)] for w in WORLDS}
    criteria = evaluate(summaries)
    results = {
        "protocol": "experiments/v7/intervention/PROTOCOL.md v1.0",
        "settings": {
            "master_seed": MASTER_SEED,
            "n_per_cell": N_PER_CELL,
            "replications": reps,
            "n_perm": N_PERM,
            "alpha": ALPHA,
            "c_w": C_W,
            "worlds": {w: [f.__dict__ for f in fs] for w, fs in WORLDS.items()},
            "traces_committed": False,
        },
        "criteria": criteria,
        "overall": overall(criteria),
        "summaries": summaries,
    }
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(results, indent=1) + "\n")
    return results


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point; prints the criteria and the overall result."""
    parser = argparse.ArgumentParser(description="V7 Experiment 4 (interventions)")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    results = run(args.out)
    for name, c in results["criteria"].items():
        tag = "" if "pass" not in c else ("PASS " if c["pass"] else "FAIL ")
        rest = {k: v for k, v in c.items() if k != "pass"}
        sys.stdout.write(f"{name}: {tag}{json.dumps(rest)}\n")
    sys.stdout.write(f"EXPERIMENT 4 OVERALL: {results['overall']}\n")
    return 0 if results["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
