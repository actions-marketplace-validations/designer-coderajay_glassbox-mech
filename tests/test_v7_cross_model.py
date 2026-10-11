"""Mechanics of V7 Experiment 6 (experiments/v7/cross_model) without loading models.

A fake scorer stands in for every model. Smoke runs use a small N and few
permutations; the criteria logic is checked on fabricated summaries.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

EXP = Path(__file__).resolve().parent.parent / "experiments" / "v7" / "cross_model"


@pytest.fixture()
def e6():
    spec = importlib.util.spec_from_file_location("exp6_run", EXP / "run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeScorer:
    """+5 if the answer string occurs in the prompt, else -5 (template-insensitive)."""

    def __call__(self, prompt: str, answer: str) -> float:
        return 5.0 if answer.strip() in prompt else -5.0


def fake_factory(fail=()):
    loaded = []

    def make(name: str):
        if name in fail:
            raise OSError(f"cannot load {name}")
        loaded.append(name)
        return FakeScorer()

    make.loaded = loaded  # type: ignore[attr-defined]
    return make


@pytest.fixture()
def fast(e6, monkeypatch):
    monkeypatch.setattr(e6, "N_PER_CELL", 6)
    monkeypatch.setattr(e6, "N_PERM", 199)  # min p 0.005 < Holm 0.05/3
    return e6


def test_constants_match_protocol(e6):
    assert [m.name for m in e6.MODELS] == [
        "EleutherAI/pythia-160m",
        "facebook/opt-125m",
        "Qwen/Qwen2.5-0.5B",
    ]
    assert e6.MODELS[2].fallbacks == ("Qwen/Qwen2-0.5B",)
    assert e6.MODELS[0].fallbacks == () and e6.MODELS[1].fallbacks == ()
    assert (e6.N_PER_CELL, e6.N_PERM, e6.ALPHA) == (30, 999, 0.05)
    assert (e6.LARGE, e6.X2_MAX, e6.X3_TOL) == (0.5, 1, 1e-6)


def test_ground_truth_classes(e6):
    margins = {
        "full|context_first": 10.0,
        "stale|context_first": -10.0,
        "full|question_first": 9.0,
        "stale|question_first": -9.0,
    }
    truth = e6.true_effects(margins, "q1")
    assert truth["index"]["class"] == "large"
    assert truth["log_level"] == {"true_tvd": 0.0, "class": "zero"}
    assert truth["template"]["class"] == "small"
    same = dict(margins, **{"stale|context_first": 10.0, "stale|question_first": 9.0})
    assert e6.true_effects(same, "q5")["index"]["class"] == "zero"


def test_investigate_model_with_fake_scorer(fast, tmp_path):
    exp5 = fast.load_exp5()
    s = fast.investigate_model(exp5, FakeScorer(), "fake/model", tmp_path)
    assert set(s["per_question"]) == {f"q{i}" for i in range(1, 9)}
    q1 = s["per_question"]["q1"]
    assert (
        q1["pairs"]["index"]["class"] == "large" and q1["pairs"]["index"]["attributed"]
    )
    assert q1["pairs"]["log_level"]["class"] == "zero"
    assert s["recheck_max_diff"] == 0.0
    assert "first_beyond_noise" in q1["group_diff"]


def test_load_with_fallback_and_not_run(fast):
    exp5 = fast.load_exp5()
    factory = fake_factory(fail={"Qwen/Qwen2.5-0.5B"})
    name, scorer, errors = fast.load_model(fast.MODELS[2], factory)
    assert name == "Qwen/Qwen2-0.5B" and scorer is not None
    assert "Qwen/Qwen2.5-0.5B" in errors[0]
    factory2 = fake_factory(fail={"Qwen/Qwen2.5-0.5B", "Qwen/Qwen2-0.5B"})
    name2, scorer2, errors2 = fast.load_model(fast.MODELS[2], factory2)
    assert name2 is None and scorer2 is None and len(errors2) == 2
    assert exp5 is not None


def _model(x1="pass", zero_hits=0, recheck=0.0):
    large = {"q1": {"index": {"class": "large", "attributed": x1 != "fail"}}}
    if x1 == "n/a":
        large = {}
    pairs = dict(large)
    for q in ("q2", "q3"):
        pairs[q] = {"log_level": {"class": "zero", "attributed": False}}
    for i in range(zero_hits):
        pairs[f"z{i}"] = {"log_level": {"class": "zero", "attributed": True}}
    return {
        "status": "RUN",
        "per_question": {q: {"pairs": p} for q, p in pairs.items()},
        "recheck_max_diff": recheck,
    }


def test_criteria(e6):
    assert e6.model_criteria(_model())["pass"]
    assert e6.model_criteria(_model(x1="n/a"))["X1_sensitivity"]["applicable"] is False
    assert not e6.model_criteria(_model(x1="fail"))["pass"]
    assert e6.model_criteria(_model(zero_hits=1))["pass"]
    assert not e6.model_criteria(_model(zero_hits=2))["pass"]
    assert not e6.model_criteria(_model(recheck=1e-5))["pass"]


def test_overall(e6):
    run = {"status": "RUN", "criteria": {"pass": True}}
    bad = {"status": "RUN", "criteria": {"pass": False}}
    not_run = {"status": "NOT RUN"}
    assert e6.overall([run, run, not_run]) == "PASS"
    assert e6.overall([run, not_run, not_run]) == "FAIL"
    assert e6.overall([run, run, bad]) == "FAIL"


def test_run_writes_once_and_frees_models(fast, tmp_path):
    factory = fake_factory(fail={"facebook/opt-125m"})
    res = fast.run(tmp_path, factory)
    statuses = [m["status"] for m in res["models"]]
    assert statuses == ["RUN", "NOT RUN", "RUN"]
    assert res["models"][1]["errors"]
    assert res["overall"] == "PASS"
    saved = json.loads((tmp_path / "results.json").read_text())
    assert saved["settings"]["n_per_cell"] == 6
    with pytest.raises(FileExistsError):
        fast.run(tmp_path, factory)
