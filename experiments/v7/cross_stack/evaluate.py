#!/usr/bin/env python3
"""Evaluate V7 Experiment 8 (cross-stack, Hard Gate 2) against PROTOCOL.md §4.

Runs in the main environment. Imports stack B's OTLP files with ``glassbox.v7.otlp``,
then compares them with the unchanged ``glassbox.v7.diff.diff_traces``.

Usage:
    python3 experiments/v7/cross_stack/evaluate.py --results experiments/v7/cross_stack/results
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from glassbox.v7.diff import diff_traces
from glassbox.v7.otlp import fidelity_problems, import_file
from glassbox.v7.trace import read_trace

REPO = Path(__file__).resolve().parents[3]
PROTOCOL_COMMIT = "5a5d2da"
CONDITIONS = ("baseline", "baseline_repeat", "fault", "restored")
QUESTIONS = tuple(f"q{i}" for i in range(1, 9))
AFFECTED = ("q1", "q2", "q3", "q4")
UNAFFECTED = ("q5", "q6", "q7", "q8")
DOC_KEY = "retrieval.documents.0.document.id"
EXP1_RESULTS = REPO / "experiments" / "v7" / "rag_fault" / "results" / "results.json"


def diff_py_unchanged() -> Tuple[bool, str]:
    """S6: sha256 of glassbox/v7/diff.py now vs at the protocol commit."""
    now = hashlib.sha256((REPO / "glassbox/v7/diff.py").read_bytes()).hexdigest()
    try:
        old_bytes = subprocess.run(
            ["git", "show", f"{PROTOCOL_COMMIT}:glassbox/v7/diff.py"],
            cwd=REPO,
            capture_output=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        return False, f"cannot read diff.py at {PROTOCOL_COMMIT}: {exc}"
    old = hashlib.sha256(old_bytes).hexdigest()
    return now == old, f"now {now} / protocol {old}"


def _import_all(results: Path) -> Tuple[Dict[Tuple[str, str], Path], List[str], int]:
    paths: Dict[Tuple[str, str], Path] = {}
    problems: List[str] = []
    vectors = 0
    for cond in CONDITIONS:
        for q in QUESTIONS:
            src = results / "otlp" / cond / f"{q}.otlp.json"
            dst = results / "imported" / cond / f"{q}.trace.jsonl"
            res = import_file(src, dst)
            data = json.loads(src.read_text(encoding="utf-8"))
            problems += [f"{cond}/{q}: {p}" for p in fidelity_problems(data, res)]
            vectors += res.vectors_dropped
            paths[(cond, q)] = dst
    return paths, problems, vectors


def _span_at(path: Path, index: Optional[int]) -> Dict[str, Any]:
    spans, _ = read_trace(path)
    for s in spans:
        if s["attributes"].get("glassbox.step.index") == index:
            return s
    return {"attributes": {}, "name": None}


def _first_is_retrieval(a: Path, b: Path) -> bool:
    first = diff_traces(a, b).first_divergence
    if first is None:
        return False
    index = first.step_a if first.step_a is not None else first.step_b
    span = _span_at(a if first.step_a is not None else b, index)
    return span["attributes"].get("gen_ai.operation.name") == "retrieval"


def _retrieved(path: Path) -> Optional[str]:
    spans, _ = read_trace(path)
    for s in spans:
        if s["attributes"].get("gen_ai.operation.name") == "retrieval":
            value = s["attributes"].get(DOC_KEY)
            return str(value) if value is not None else None
    return None


def _crit(passed: int, total: int) -> Dict[str, Any]:
    return {"value": f"{passed}/{total}", "pass": passed == total}


def _specific(base: Path, fault: Path) -> bool:
    if _retrieved(base) == _retrieved(fault):
        return diff_traces(base, fault).identical
    return _first_is_retrieval(base, fault)


def _descriptive(paths: Dict[Tuple[str, str], Path], vectors: int) -> Dict[str, Any]:
    names: Counter = Counter()
    for p in paths.values():
        spans, _ = read_trace(p)
        for s in spans[1:]:
            names[
                f"{s['name']} [{s['attributes'].get('openinference.span.kind')}]"
            ] += 1
    agree, total = 0, 0
    if EXP1_RESULTS.exists():
        exp1 = json.loads(EXP1_RESULTS.read_text(encoding="utf-8"))["outcomes"]
        for (cond, q), p in paths.items():
            a = exp1.get(cond, {}).get(q, {}).get("retrieved", [None])[0]
            total += 1
            agree += a == _retrieved(p)
    return {
        "D1_span_names_kinds": dict(sorted(names.items())),
        "D2_vectors_dropped": vectors,
        "D3_same_document_as_stack_A": f"{agree}/{total}",
    }


def evaluate(
    results: Path, diff_unchanged: Callable[[], Tuple[bool, str]] = diff_py_unchanged
) -> Dict[str, Any]:
    """Import, compare and score S1–S7 (overall from S1–S6)."""
    paths, problems, vectors = _import_all(results)
    base = {q: paths[("baseline", q)] for q in QUESTIONS}
    same = lambda c, q: diff_traces(base[q], paths[(c, q)]).identical  # noqa: E731
    s6_ok, s6_detail = diff_unchanged()
    schema = json.loads((results / "schema_check.json").read_text(encoding="utf-8"))
    crit: Dict[str, Any] = {
        "S1": {
            **_crit(32 - len({p.split(":")[0] for p in problems}), 32),
            "problems": problems[:50],
        },
        "S2": _crit(
            sum(_first_is_retrieval(base[q], paths[("fault", q)]) for q in AFFECTED), 4
        ),
        "S3": _crit(
            sum(_specific(base[q], paths[("fault", q)]) for q in UNAFFECTED), 4
        ),
        "S4": _crit(sum(same("restored", q) for q in QUESTIONS), 8),
        "S5": _crit(sum(same("baseline_repeat", q) for q in QUESTIONS), 8),
        "S6": {"value": s6_detail, "pass": s6_ok},
        "S7": {
            **_crit(int(schema["ok"]), int(schema["traces"])),
            "problems": schema.get("problems", [])[:50],
        },
    }
    overall = (
        "PASS"
        if all(crit[k]["pass"] for k in ("S1", "S2", "S3", "S4", "S5", "S6"))
        else "FAIL"
    )
    return {
        "protocol": f"experiments/v7/cross_stack/PROTOCOL.md v1.0 ({PROTOCOL_COMMIT})",
        "criteria": crit,
        "overall": overall,
        "descriptive": _descriptive(paths, vectors),
        "stack_b_env": json.loads(
            (results / "stack_b_env.json").read_text(encoding="utf-8")
        ),
    }


def run(
    results: Path, diff_unchanged: Callable[[], Tuple[bool, str]] = diff_py_unchanged
) -> Dict[str, Any]:
    """Evaluate and write ``results.json`` (never overwrites)."""
    target = results / "results.json"
    if target.exists():
        raise FileExistsError(f"{target} exists; results are never overwritten")
    out = evaluate(results, diff_unchanged)
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(out, indent=1) + "\n")
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Evaluate V7 Experiment 8")
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args(argv)
    out = run(args.results)
    for name, c in out["criteria"].items():
        tag = "PASS" if c["pass"] else "FAIL"
        sys.stdout.write(f"{name}: {tag} {c['value']}\n")
    for name, value in out["descriptive"].items():
        sys.stdout.write(f"{name}: {json.dumps(value)}\n")
    sys.stdout.write(f"EXPERIMENT 8 OVERALL: {out['overall']}\n")
    return 0 if out["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
