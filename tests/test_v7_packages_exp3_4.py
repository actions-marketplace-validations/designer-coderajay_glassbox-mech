"""Evidence packages for V7 Experiments 3, 3b, 4, 5, 6, 7b and 8 build and verify.

Each package must carry the ASSURANCE status of its row, so a REFUTED result is never
repackaged as supported.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from glassbox.v7.evidence import build_package, verify_package

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "experiments" / "v7"
CASES = [
    ("noise_baseline", "v7-exp3-noise-baseline", "REFUTED", "V2.7"),
    (
        "noise_baseline_3b",
        "v7-exp3b-noise-baseline-merge",
        "EXPERIMENTALLY_SUPPORTED",
        "V2.9",
    ),
    ("intervention", "v7-exp4-interventions", "EXPERIMENTALLY_SUPPORTED", "V3.1"),
    (
        "real_intervention",
        "v7-exp5-real-interventions",
        "EXPERIMENTALLY_SUPPORTED",
        "V3.3",
    ),
    ("cross_model", "v7-exp6-cross-model", "EXPERIMENTALLY_SUPPORTED", "V3.6"),
    ("agent_b", "v7-exp7b-agent", "EXPERIMENTALLY_SUPPORTED", "V3.8"),
    ("cross_stack", "v7-exp8-cross-stack", "EXPERIMENTALLY_SUPPORTED", "V2.10"),
]


def _load(folder: str):
    spec = importlib.util.spec_from_file_location(
        f"pkg_{folder}", EXP / folder / "package.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _assurance_status(row: str) -> str:
    for line in (ROOT / "ASSURANCE.md").read_text().splitlines():
        if line.startswith(f"| {row} |"):
            return re.findall(r"`([A-Z_]+)`", line)[0]
    raise AssertionError(f"row {row} not found")


@pytest.mark.parametrize("folder,pid,status,row", CASES)
def test_package_builds_verifies_and_matches_assurance(
    tmp_path, folder, pid, status, row
):
    mod = _load(folder)
    assert mod.PACKAGE_ID == pid
    spec = mod.spec()
    assert spec.status == status == _assurance_status(row)
    assert spec.provenance["assurance_row"] == row
    pkg = build_package(tmp_path, pid, spec)
    assert verify_package(pkg) == []
    claim = json.loads((pkg / "claim.json").read_text())
    assert claim["status"] == status


def test_exp3_package_says_fail_and_carries_part_b_traces(tmp_path):
    mod = _load("noise_baseline")
    assert "FAIL" in mod.CLAIM
    pkg = build_package(tmp_path, mod.PACKAGE_ID, mod.spec())
    roles = sorted(d.name for d in (pkg / "artifacts").glob("traces_part_b_*"))
    assert len(roles) == 3 * 8  # one role per (condition, question)
    traces = list((pkg / "artifacts").glob("traces_part_b_*/*.trace.jsonl"))
    assert len(traces) == 3 * 8 * 20


def test_exp7b_package_carries_both_runs_and_numeric_check(tmp_path):
    mod = _load("agent_b")
    pkg = build_package(tmp_path, mod.PACKAGE_ID, mod.spec())
    names = {p.name for p in (pkg / "artifacts").rglob("*") if p.is_file()}
    for required in (
        "results.json",
        "run_log_run1.txt",
        "notebook_run1.ipynb",
        "run_log_run2.txt",
        "numeric_check.json",
        "explain_numeric.py",
    ):
        assert required in names
    assert "not reproduced bit-identically" in mod.SCOPE
    assert "stopped sending" in mod.SCOPE


def test_exp8_package_carries_otlp_imported_and_schema_check(tmp_path):
    mod = _load("cross_stack")
    pkg = build_package(tmp_path, mod.PACKAGE_ID, mod.spec())
    arts = pkg / "artifacts"
    assert len(list(arts.glob("otlp_*/*.otlp.json"))) == 32
    assert len(list(arts.glob("imported_*/*.trace.jsonl"))) == 32
    names = {p.name for p in arts.rglob("*") if p.is_file()}
    for required in ("schema_check.json", "stack_b_env.json", "otlp.py", "subject.py"):
        assert required in names
    assert "retrieval only" in mod.SCOPE and "live OTLP collector" in mod.SCOPE
