"""V8 phase B GPU sanity check (experiments/v7/gpu_check/run.py): comparison, gates and
the end-to-end runner, tested with the toy scorer and fake environments (no GPU)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from glassbox.v7 import demo_rag
from glassbox.v7.intervene import InterventionSettings

RUN = Path(__file__).resolve().parent.parent / "experiments" / "v7" / "gpu_check"


@pytest.fixture(scope="module")
def gc():
    spec = importlib.util.spec_from_file_location("gpu_check_run", RUN / "run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _result(cid, decisions, env=None, summary=None):
    return {
        "id": cid,
        "environment": env or {"device": "cpu", "gpu_name": None, "cuda_version": None},
        "decisions": decisions,
        "factor_summary": summary or {"index": {"switching_alone_changed": ["q1"]}},
    }


GPU_ENV = {"device": "cuda", "gpu_name": "Tesla T4", "cuda_version": "12.4"}
SAME = {"q1": {"attributed": ["index"], "reverting_matters": ["index"]}}


def test_settings_match_protocol(gc):
    assert gc.SETTINGS == InterventionSettings(30, 999, 0.05, "gpu-check")
    assert [c[0] for c in gc.CONFIGS] == ["A", "B", "C"]
    assert dict((c[0], (c[1], c[2])) for c in gc.CONFIGS) == {
        "A": ("cpu", "float32"),
        "B": ("cuda", "float32"),
        "C": ("cuda", "bfloat16"),
    }


def test_compare_identical(gc):
    cmp = gc.compare(_result("A", SAME), _result("B", SAME, GPU_ENV))
    assert cmp == {"identical": True, "summary_equal": True, "differing_cases": []}


def test_compare_reports_every_differing_case(gc):
    other = {"q1": {"attributed": [], "reverting_matters": ["index"]}}
    cmp = gc.compare(
        _result("A", SAME),
        _result(
            "B", other, GPU_ENV, summary={"index": {"switching_alone_changed": []}}
        ),
    )
    assert cmp["identical"] is False and cmp["summary_equal"] is False
    assert cmp["differing_cases"] == [{"case": "q1", "a": SAME["q1"], "b": other["q1"]}]


def test_gate_pass(gc):
    g = gc.gate([_result("A", SAME), _result("B", SAME, GPU_ENV)])
    assert g["G1"]["pass"] and g["G2"]["pass"] and g["overall"] == "PASS"


def test_gate_fail_on_decision_difference(gc):
    other = {"q1": {"attributed": [], "reverting_matters": []}}
    g = gc.gate([_result("A", SAME), _result("B", other, GPU_ENV)])
    assert not g["G1"]["pass"] and g["overall"] == "FAIL"


def test_gate_g2_needs_gpu_name_and_cuda(gc):
    no_gpu = {"device": "cuda", "gpu_name": None, "cuda_version": None}
    g = gc.gate([_result("A", SAME), _result("B", SAME, no_gpu)])
    assert g["G1"]["pass"] and not g["G2"]["pass"] and g["overall"] == "FAIL"


def test_gate_infrastructure_failure_is_never_pass(gc):
    g = gc.gate([_result("A", SAME), {"id": "B", "error": "CUDA was requested ..."}])
    assert g["overall"] == "INFRASTRUCTURE_FAILURE"
    assert g["G1"]["pass"] is None


def test_descriptive_c_counts_matching_cases(gc):
    c = _result("C", {"q1": {"attributed": [], "reverting_matters": []}}, GPU_ENV)
    d = gc.describe_c(_result("A", SAME), c)
    assert d == {"cases": 1, "matching_A": 0}
    assert gc.describe_c(_result("A", SAME), {"id": "C", "error": "x"}) is None


def _fake_factory(config):
    env = (
        dict(GPU_ENV, dtype=config.dtype)
        if config.device == "cuda"
        else {
            "device": "cpu",
            "dtype": "float32",
            "gpu_name": None,
            "cuda_version": None,
        }
    )
    return demo_rag.toy_scorer, env


def test_main_end_to_end_with_toy_scorer(gc, tmp_path, monkeypatch):
    monkeypatch.setattr(gc, "SETTINGS", InterventionSettings(10, 99, 0.05, "t"))
    out = tmp_path / "out"
    assert gc.main(["--out", str(out)], scorer_factory=_fake_factory) == 0
    res = json.loads((out / "results.json").read_text())
    assert [r["id"] for r in res["configurations"]] == ["A", "B", "C"]
    assert res["gates"]["overall"] == "PASS"  # same toy scorer: decisions identical
    assert res["descriptive_C"]["cases"] == len(demo_rag.QUESTIONS)
    a = res["configurations"][0]
    assert set(a["decisions"]) == set(demo_rag.QUESTIONS)
    assert a["runtime_s"] >= 0 and a["outcome_counts"]
    assert res["protocol"] == "experiments/v7/gpu_check/PROTOCOL.md v1.0"
    assert "software" in res and "glassbox-mech-interp" in res["software"]
    assert (out / "run.log").read_text().strip()


def test_main_records_missing_gpu_as_infrastructure_failure(gc, tmp_path, monkeypatch):
    monkeypatch.setattr(gc, "SETTINGS", InterventionSettings(10, 99, 0.05, "t"))

    def no_gpu(config):
        if config.device == "cuda":
            raise ValueError("CUDA was requested but torch reports no GPU.")
        return _fake_factory(config)

    out = tmp_path / "out"
    assert gc.main(["--out", str(out)], scorer_factory=no_gpu) == 1
    res = json.loads((out / "results.json").read_text())
    assert res["gates"]["overall"] == "INFRASTRUCTURE_FAILURE"
    assert "CUDA was requested" in res["configurations"][1]["error"]


def test_main_refuses_non_empty_out(gc, tmp_path):
    (tmp_path / "x").write_text("x")
    with pytest.raises(FileExistsError):
        gc.main(["--out", str(tmp_path)], scorer_factory=_fake_factory)
