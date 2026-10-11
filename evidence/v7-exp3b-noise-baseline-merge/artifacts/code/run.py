#!/usr/bin/env python3
"""V7 Experiment 3b: redundant-field merging and a power curve (PROTOCOL.md).

Reuses Experiment 3's synthetic pipeline unchanged (``simulate_run``, ``BASELINE``,
``CANDIDATE`` from ``experiments/v7/noise_baseline/part_a.py``). For every world W0–W3,
group size N ∈ {10, 20, 30, 50} and replication 0–199 it writes N + N traces to a
temporary directory, runs the group diff with ``merge_redundant=True`` (gated) and
``merge_redundant=False`` (descriptive, D2) on the same traces, and keeps summaries.
The permutation seed of each comparison is the replication index, as in Experiment 3.

Usage (stdlib + glassbox only):
    python3 experiments/v7/noise_baseline_3b/run.py --out experiments/v7/noise_baseline_3b/results
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List, Optional, Sequence

from glassbox.v7.groupdiff import group_diff

HERE = Path(__file__).resolve().parent
EXP3 = HERE.parent / "noise_baseline" / "part_a.py"
MASTER_SEED = 20261006
GROUP_SIZES = (10, 20, 30, 50)
GATE_N = 30
REPLICATIONS = 200
N_PERM = 999
ALPHA = 0.05
WORLDS = ("W0", "W1", "W2", "W3")
CHAT = "chat#0"
RETRIEVAL = "retrieval#0"
LABEL = "chat#0 glassbox.answer.label"
TOOL_MEMBERS = frozenset(
    f"execute_tool:send_confirmation#0 {f}"
    for f in ("present", "status", "gen_ai.tool.name")
)

Summaries = Dict[str, Dict[str, List[Dict[str, Any]]]]


def load_exp3() -> ModuleType:
    """Load Experiment 3 Part A by path (pipeline, parameters, ``summarise``)."""
    spec = importlib.util.spec_from_file_location("exp3_part_a", EXP3)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def merge_ok(report: Dict[str, Any]) -> bool:
    """A7: the chat label is a tested representative merging all three tool fields."""
    for f in report["fields"]:
        if f"{f['step']} {f['field']}" == LABEL:
            return f["classification"] == "tested" and TOOL_MEMBERS <= set(
                f["merged_with"]
            )
    return False


def replicate(exp3: ModuleType, world: str, n: int, rep: int) -> Dict[str, Any]:
    """One replication: merged and unmerged summaries on the same traces."""
    tag = f"{MASTER_SEED}:{world}:{n}:{rep}"
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        a = exp3._group(f"{tag}:A", exp3.BASELINE, out, "a", n)
        b = exp3._group(f"{tag}:B", exp3.CANDIDATE[world], out, "b", n)
        merged = group_diff(a, b, N_PERM, ALPHA, rep, merge_redundant=True).to_dict()
        plain = group_diff(a, b, N_PERM, ALPHA, rep, merge_redundant=False).to_dict()
    summary = exp3.summarise(merged, None)
    summary["merge_ok"] = merge_ok(merged)
    summary["n_tests"] = merged["n_tests"]
    unmerged = exp3.summarise(plain, None)
    return {"merged": summary, "unmerged": unmerged}


def _rate(xs: Sequence[bool]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _first_at(rows: List[Dict[str, Any]], step: str) -> float:
    return _rate([bool(s["first"]) and s["first"][0] == step for s in rows])


def _flagged(rows: List[Dict[str, Any]], step: str) -> float:
    return _rate([step in s["significant_steps"] for s in rows])


def _rows(summaries: Summaries, world: str, n: int, kind: str) -> List[Dict[str, Any]]:
    return [r[kind] for r in summaries[world][str(n)]]


def evaluate(summaries: Summaries) -> Dict[str, Any]:
    """Apply PROTOCOL.md §4 criteria to ``summaries[world][str(N)]``."""
    ns = [int(k) for k in summaries["W0"]]

    def m(world: str, n: int) -> List[Dict[str, Any]]:
        return _rows(summaries, world, n, "merged")

    def u(world: str, n: int) -> List[Dict[str, Any]]:
        return _rows(summaries, world, n, "unmerged")

    a1 = {n: _rate([s["any_significant"] for s in m("W0", n)]) for n in ns}
    a2 = _first_at(m("W1", GATE_N), CHAT)
    a2b = {n: _flagged(m("W1", n), RETRIEVAL) for n in ns}
    a3 = _first_at(m("W2", GATE_N), RETRIEVAL)
    a4 = all(
        s["output_hash_classification"] == "untestable"
        for w in WORLDS
        for n in ns
        for s in m(w, n)
    )
    a7 = _rate([s["merge_ok"] for s in m("W1", GATE_N)])
    return {
        "A1p_type_I": {
            "rate_by_N": a1,
            "rule": "<= 0.08 at each N",
            "pass": all(v <= 0.08 for v in a1.values()),
        },
        "A2p_chat_localisation": {
            "rate": a2,
            "N": GATE_N,
            "rule": ">= 0.80",
            "pass": a2 >= 0.80,
        },
        "A2bp_no_false_upstream": {
            "rate_by_N": a2b,
            "rule": "<= 0.08 at each N",
            "pass": all(v <= 0.08 for v in a2b.values()),
        },
        "A3p_retrieval_localisation": {
            "rate": a3,
            "N": GATE_N,
            "rule": ">= 0.80",
            "pass": a3 >= 0.80,
        },
        "A4p_free_text_untestable": {"all_untestable": a4, "pass": a4},
        "A7_merge_validity": {
            "rate": a7,
            "N": GATE_N,
            "rule": ">= 0.95",
            "pass": a7 >= 0.95,
        },
        "D1_power_curve": {
            str(n): {
                "W1_first_at_chat": _first_at(m("W1", n), CHAT),
                "W1_any_detection": _rate([s["any_significant"] for s in m("W1", n)]),
                "W2_first_at_retrieval": _first_at(m("W2", n), RETRIEVAL),
                "W2_any_detection": _rate([s["any_significant"] for s in m("W2", n)]),
            }
            for n in ns
        },
        "D2_merge_effect_unmerged": {
            str(n): {
                "W0_any_significant": _rate([s["any_significant"] for s in u("W0", n)]),
                "W1_first_at_chat": _first_at(u("W1", n), CHAT),
            }
            for n in ns
        },
        "D3_one_vs_two_causes": {
            str(n): {
                "chat_flagged_W2": _flagged(m("W2", n), CHAT),
                "chat_flagged_W3": _flagged(m("W3", n), CHAT),
            }
            for n in ns
        },
    }


GATED = (
    "A1p_type_I",
    "A2p_chat_localisation",
    "A2bp_no_false_upstream",
    "A3p_retrieval_localisation",
    "A4p_free_text_untestable",
    "A7_merge_validity",
)


def overall(criteria: Dict[str, Any]) -> str:
    """PASS iff every gated criterion passes."""
    return "PASS" if all(criteria[g]["pass"] for g in GATED) else "FAIL"


def run(
    out: Path, reps: int = REPLICATIONS, sizes: Sequence[int] = GROUP_SIZES
) -> Dict[str, Any]:
    """Run every world × N × replication; write ``results.json`` (never overwrites)."""
    out.mkdir(parents=True, exist_ok=True)
    target = out / "results.json"
    if target.exists():
        raise FileExistsError(f"{target} exists; results are never overwritten")
    exp3 = load_exp3()
    summaries: Summaries = {
        w: {str(n): [replicate(exp3, w, n, i) for i in range(reps)] for n in sizes}
        for w in WORLDS
    }
    criteria = evaluate(summaries)
    results = {
        "protocol": "experiments/v7/noise_baseline_3b/PROTOCOL.md v1.0",
        "settings": {
            "master_seed": MASTER_SEED,
            "group_sizes": list(sizes),
            "gate_N": GATE_N,
            "replications": reps,
            "n_perm": N_PERM,
            "alpha": ALPHA,
            "baseline": exp3.BASELINE.__dict__,
            "candidates": {w: p.__dict__ for w, p in exp3.CANDIDATE.items()},
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
    parser = argparse.ArgumentParser(description="V7 Experiment 3b")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    results = run(args.out)
    for name, c in results["criteria"].items():
        tag = "" if "pass" not in c else ("PASS " if c["pass"] else "FAIL ")
        rest = {k: v for k, v in c.items() if k != "pass"}
        sys.stdout.write(f"{name}: {tag}{json.dumps(rest)}\n")
    sys.stdout.write(f"EXPERIMENT 3b OVERALL: {results['overall']}\n")
    return 0 if results["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
