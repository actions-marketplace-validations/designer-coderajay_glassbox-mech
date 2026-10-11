"""Evidence packages for V7 Experiments 3, 3b, 4, 5 and 6 build and verify.

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
