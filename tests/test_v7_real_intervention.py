"""Mechanics of V7 Experiment 5 (experiments/v7/real_intervention) without running it.

GPT-2 is never loaded: a fake scorer stands in. Smoke runs use a non-protocol seed,
a small N and few permutations.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from glassbox.v7.trace import read_trace

EXP = (
    Path(__file__).resolve().parent.parent / "experiments" / "v7" / "real_intervention"
)


@pytest.fixture()
def e5():
    spec = importlib.util.spec_from_file_location("exp5_run", EXP / "run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeScorer:
    """+5 if the answer string occurs in the prompt's context, else -5. Counts calls."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, prompt: str, answer: str) -> float:
        self.calls += 1
        return 5.0 if answer.strip() in prompt else -5.0


def test_constants_match_protocol(e5):
    assert (e5.N_PER_CELL, e5.N_PERM, e5.ALPHA, e5.TEMPERATURE) == (30, 999, 0.05, 1.0)
    assert e5.MASTER_SEED == "exp5-20261011"
    names = [(f.name, f.base, f.candidate) for f in e5.FACTORS]
    assert names == [
        ("index", "full", "stale"),
        ("template", "context_first", "question_first"),
        ("log_level", "info", "debug"),
    ]
    assert e5.AFFECTED == ("q1", "q2", "q3", "q4")
    assert e5.UNAFFECTED == ("q5", "q6", "q7", "q8")


def test_templates(e5):
    exp1 = e5.load_exp1()
    ctx, q = ["Doc one.", "Doc two."], "Who?"
    assert e5.build_prompt("context_first", ctx, q) == exp1.build_prompt(ctx, q)
    assert e5.build_prompt("question_first", ctx, q) == (
        "Question: Who?\nContext:\nDoc one.\nDoc two.\nAnswer:"
    )
    with pytest.raises(ValueError):
        e5.build_prompt("other", ctx, q)


def test_p_correct(e5):
    assert e5.p_correct(0.0) == 0.5
    assert e5.p_correct(30.0) > 0.999
    assert e5.p_correct(-30.0) < 0.001
    assert e5.p_correct(-800.0) == pytest.approx(0.0)  # no overflow


def test_margin_cache_scores_each_prompt_once_and_rechecks(e5):
    scorer = FakeScorer()
    cache = e5.MarginCache(scorer)
    q = {"correct": " Kestrel", "distractor": " Halcyon"}
    assert cache.margin("x Kestrel", q) == 10.0
    assert cache.margin("x Kestrel", q) == 10.0
    assert scorer.calls == 2  # one prompt, two answers
    assert cache.recheck() == 0.0


def test_runner_records_trace_without_raw_text(e5, tmp_path):
    exp1 = e5.load_exp1()
    docs, questions = exp1.load_corpus(e5.EXP1_DIR / "corpus.json")
    runner = e5.RagRunner(exp1, docs, questions[0], e5.MarginCache(FakeScorer()))
    cfg = {"index": "full", "template": "context_first", "log_level": "debug"}
    path = runner(cfg, 7, tmp_path, "r000")
    spans, _ = read_trace(path)
    assert spans[0]["attributes"]["glassbox.env.log_level"] == "debug"
    ops = [s["attributes"].get("gen_ai.operation.name") for s in spans[1:]]
    assert ops == ["retrieval", "chat"]
    assert spans[2]["attributes"]["glassbox.answer.label"] in {"correct", "distractor"}
    text = Path(path).read_text()
    assert questions[0]["question"] not in text and "Kestrel" not in text


def test_investigate_question_with_fake_scorer(e5, tmp_path, monkeypatch):
    monkeypatch.setattr(e5, "MASTER_SEED", "test-not-protocol")
    monkeypatch.setattr(e5, "N_PER_CELL", 8)
    monkeypatch.setattr(e5, "N_PERM", 99)
    exp1 = e5.load_exp1()
    docs, questions = exp1.load_corpus(e5.EXP1_DIR / "corpus.json")
    cache = e5.MarginCache(FakeScorer())
    s1 = e5.investigate(exp1, docs, questions[0], cache, tmp_path)  # q1, affected
    assert s1["attributed"] == ["index"]
    assert set(s1["margins"]) == {
        "full|context_first",
        "full|question_first",
        "stale|context_first",
        "stale|question_first",
    }
    s5 = e5.investigate(exp1, docs, questions[4], cache, tmp_path)  # q5, unaffected
    assert "index" not in s5["attributed"]
    assert s5["margins"]["full|context_first"] == s5["margins"]["stale|context_first"]
    assert {"first_beyond_noise", "flagged_steps"} <= set(s1["group_diff"])


def _q(attributed=(), margins=None):
    return {
        "attributed": list(attributed),
        "sufficiency": [],
        "necessity": [],
        "total": {},
        "p_correct": {},
        "margins": margins or {"full|context_first": 1.0, "stale|context_first": 1.0},
        "group_diff": {"first_beyond_noise": None, "flagged_steps": []},
    }


def _good():
    per = {f"q{i}": _q(["index"]) for i in range(1, 5)}
    per.update({f"q{i}": _q([]) for i in range(5, 9)})
    return per


def test_evaluate_pass_and_fail(e5):
    exp1_margins = {"baseline": {}, "fault": {}}
    for q in range(1, 9):
        exp1_margins["baseline"][f"q{q}"] = 1.0
        exp1_margins["fault"][f"q{q}"] = 1.0
    crit = e5.evaluate(_good(), recheck_max_diff=0.0, exp1_margins=exp1_margins)
    assert e5.overall(crit) == "PASS"
    assert crit["D4_exp1_crosscheck"]["max_abs_diff"] == 0.0

    bad = _good()
    bad["q2"] = _q([])
    assert not e5.evaluate(bad, 0.0, exp1_margins)["E1_real_fault_attributed"]["pass"]
    bad = _good()
    bad["q5"], bad["q6"] = _q(["index"]), _q(["index"])
    assert not e5.evaluate(bad, 0.0, exp1_margins)["E2_no_false_index_blame"]["pass"]
    bad = _good()
    bad["q1"], bad["q6"] = _q(["index", "log_level"]), _q(["log_level"])
    assert not e5.evaluate(bad, 0.0, exp1_margins)["E3_inert_never_blamed"]["pass"]
    assert not e5.evaluate(_good(), 1e-6, exp1_margins)["E4_scorer_determinism"]["pass"]


def test_run_writes_once(e5, tmp_path, monkeypatch):
    monkeypatch.setattr(e5, "MASTER_SEED", "test-not-protocol")
    monkeypatch.setattr(e5, "N_PER_CELL", 4)
    monkeypatch.setattr(e5, "N_PERM", 19)
    res = e5.run(tmp_path, FakeScorer(), model_name="fake")
    assert res["overall"] in {"PASS", "FAIL"}
    saved = json.loads((tmp_path / "results.json").read_text())
    assert len(saved["per_question"]) == 8 and saved["model"] == "fake"
    with pytest.raises(FileExistsError):
        e5.run(tmp_path, FakeScorer(), model_name="fake")
