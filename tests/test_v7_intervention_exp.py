"""Mechanics of V7 Experiment 4 (experiments/v7/intervention) without running it.

Smoke runs use a non-protocol master seed or replication index, a small N and few
permutations. The criteria logic is checked on fabricated summaries.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from glassbox.v7.trace import read_trace

EXP = Path(__file__).resolve().parent.parent / "experiments" / "v7" / "intervention"


@pytest.fixture()
def iv(monkeypatch):
    spec = importlib.util.spec_from_file_location("exp4_run", EXP / "run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_constants_match_protocol(iv):
    assert (iv.MASTER_SEED, iv.N_PER_CELL, iv.REPLICATIONS) == (20261011, 50, 200)
    assert (iv.N_PERM, iv.ALPHA, iv.C_W) == (999, 0.05, 0.20)
    assert (iv.RETRIEVAL.base, iv.RETRIEVAL.candidate) == (0.90, 0.40)
    assert (iv.CHAT.base, iv.CHAT.candidate) == (0.85, 0.35)
    assert (iv.INERT.base, iv.INERT.candidate) == ("info", "debug")
    assert [f.name for f in iv.WORLDS["V0"]] == ["log_level"]
    assert [f.name for f in iv.WORLDS["V1"]] == ["retrieval_r", "log_level"]
    assert [f.name for f in iv.WORLDS["V2"]] == ["retrieval_r", "chat_cr"]


def test_runner_records_log_level_and_is_inert(iv, tmp_path):
    runner = iv.PipelineRunner(iv.load_exp3())
    labels = {}
    for level in ("info", "debug"):
        p = runner({"log_level": level}, 12345, tmp_path / level, "r000")
        spans, _ = read_trace(p)
        assert spans[0]["attributes"]["glassbox.env.log_level"] == level
        labels[level] = iv.label_outcome(p)
    assert labels["info"] == labels["debug"]  # same seed, inert factor


def test_runner_restores_recorder(iv, tmp_path):
    exp3 = iv.load_exp3()
    original = exp3.Recorder
    iv.PipelineRunner(exp3)({}, 1, tmp_path, "r000")
    assert exp3.Recorder is original


def test_replicate_smoke_non_protocol(iv, monkeypatch):
    monkeypatch.setattr(iv, "N_PER_CELL", 4)
    monkeypatch.setattr(iv, "N_PERM", 19)
    exp3 = iv.load_exp3()
    for world in ("V0", "V1", "V2"):
        s = iv.replicate(exp3, world, -1)
        assert set(s) == {
            "attributed",
            "total_significant",
            "necessity_significant",
            "counts",
            "diff_flags_chat",
        }
        assert (s["diff_flags_chat"] is None) == (world != "V1")


def _s(attributed=(), total=True, nec=(), diff=None):
    return {
        "attributed": list(attributed),
        "total_significant": total,
        "necessity_significant": list(nec),
        "counts": {},
        "diff_flags_chat": diff,
    }


def _good(n=10):
    return {
        "V0": [_s(total=False) for _ in range(n)],
        "V1": [_s(["retrieval_r"], diff=True) for _ in range(n)],
        "V2": [_s(["retrieval_r", "chat_cr"], nec=["chat_cr"]) for _ in range(n)],
    }


def test_evaluate_pass(iv):
    crit = iv.evaluate(_good())
    assert iv.overall(crit) == "PASS"
    assert crit["I7_diff_vs_intervention_V1"] == {
        "group_diff_flags_chat": 1.0,
        "interventions_attribute_other_than_retrieval": 0.0,
    }
    assert crit["I6_necessity"]["V2"] == {"retrieval_r": 0.0, "chat_cr": 1.0}


@pytest.mark.parametrize(
    "world,rows,criterion",
    [
        ("V0", [_s(["log_level"])] * 10, "I1_type_I"),
        ("V1", [_s([])] * 10, "I2_single_cause"),
        ("V1", [_s(["retrieval_r", "log_level"])] * 10, "I3_inert_not_blamed"),
        ("V2", [_s(["retrieval_r"])] * 10, "I4_two_causes"),
    ],
)
def test_evaluate_fails(iv, world, rows, criterion):
    data = _good()
    data[world] = rows
    crit = iv.evaluate(data)
    assert not crit[criterion]["pass"]
    assert iv.overall(crit) == "FAIL"


def test_run_writes_once(iv, tmp_path, monkeypatch):
    monkeypatch.setattr(iv, "MASTER_SEED", 1)  # not the protocol seed
    monkeypatch.setattr(iv, "N_PER_CELL", 3)
    monkeypatch.setattr(iv, "N_PERM", 9)
    res = iv.run(tmp_path, reps=1)
    assert res["overall"] in {"PASS", "FAIL"}
    saved = json.loads((tmp_path / "results.json").read_text())
    assert set(saved["summaries"]) == {"V0", "V1", "V2"}
    with pytest.raises(FileExistsError):
        iv.run(tmp_path, reps=1)
