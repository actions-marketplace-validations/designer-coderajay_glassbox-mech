"""Mechanics of V7 Experiment 7 (experiments/v7/agent) without loading a model.

A fake action scorer stands in for Qwen. The exact enumerator is checked analytically
and against brute-force sampling; trace fidelity (G3) is checked on framework retries.
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

from glassbox.v7.trace import read_trace

EXP = Path(__file__).resolve().parent.parent / "experiments" / "v7" / "agent"


@pytest.fixture()
def e7():
    spec = importlib.util.spec_from_file_location("exp7_run", EXP / "run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ScriptedScorer:
    """Strong preferences: check first, then send, resend after a timeout error,
    finish after an 'ok'. ``margin`` controls how deterministic the policy is."""

    def __init__(self, margin: float = 20.0) -> None:
        self.margin = margin

    def __call__(self, prompt: str, action: str) -> float:
        a = action.strip()
        steps = prompt.count("Step ")
        last = prompt.rsplit("Step ", 1)[-1] if steps else ""
        if steps == 0:
            want = "check_calendar"
        elif "send_confirmation -> ok" in last:
            want = "finish"
        else:
            want = "send_confirmation"
        return self.margin if a == want else 0.0


BASE = {
    "system_prompt": "strict",
    "tool_format": "text",
    "framework_retry": "v1",
    "log_level": "info",
}


def test_constants_match_protocol(e7):
    assert e7.MODEL == "Qwen/Qwen2.5-0.5B"
    assert (e7.TEMPERATURE, e7.MAX_DECISIONS, e7.P_TIMEOUT) == (1.0, 4, 0.5)
    assert (e7.N_PER_CELL, e7.N_PERM, e7.ALPHA, e7.LARGE) == (30, 999, 0.05, 0.5)
    assert e7.ACTIONS == (" check_calendar", " send_confirmation", " finish")
    assert e7.CASES == {
        "c1": ("Dana", "Tuesday"),
        "c2": ("Ravi", "Thursday"),
        "c3": ("Mei", "Monday"),
        "c4": ("Tomas", "Friday"),
    }
    assert e7.SYSTEM_PROMPTS == {
        "strict": "You are a booking assistant. Check the calendar once, send "
        "exactly one confirmation, then finish.",
        "helpful": "You are a helpful booking assistant.",
    }
    assert [(f.name, f.base, f.candidate) for f in e7.FACTORS] == [
        ("system_prompt", "strict", "helpful"),
        ("tool_format", "text", "json"),
        ("framework_retry", "v1", "v2"),
        ("log_level", "info", "debug"),
    ]


def test_prompt_and_tool_formats(e7):
    p = e7.build_prompt("strict", "Dana", "Tuesday", ["Step 1: check_calendar -> x"])
    assert p == (
        "You are a booking assistant. Check the calendar once, send exactly one "
        "confirmation, then finish.\nTask: Book a meeting with Dana on Tuesday.\n"
        "Step 1: check_calendar -> x\nNext action:"
    )
    assert e7.calendar_output("text", "Tuesday") == "Tuesday: available"
    assert e7.calendar_output("json", "Tuesday") == '{"day": "Tuesday", "free": 1}'


def test_exact_distribution_analytic(e7):
    """Deterministic scripted policy: check, send, resend on timeout, finish on ok."""
    policy = e7.ActionPolicy(ScriptedScorer(margin=60.0))
    v1 = e7.exact_distribution(policy, dict(BASE), "Dana", "Tuesday")
    # v1: ok (0.5) -> 1 email; timeout -> resend: ok -> 2; timeout -> resend at step 4 -> 3
    assert v1["1"] == pytest.approx(0.5, abs=1e-9)
    assert v1["2+"] == pytest.approx(0.5, abs=1e-9)
    v2 = e7.exact_distribution(
        policy, dict(BASE, framework_retry="v2"), "Dana", "Tuesday"
    )
    # v2: timeout -> framework re-sends (2 emails) and reports ok -> finish
    assert v2["1"] == pytest.approx(0.5, abs=1e-9)
    assert v2["2+"] == pytest.approx(0.5, abs=1e-9)
    assert sum(v1.values()) == pytest.approx(1.0)


def test_exact_matches_brute_force_sampling(e7):
    policy = e7.ActionPolicy(ScriptedScorer(margin=1.5))  # genuinely stochastic
    cfg = dict(BASE, framework_retry="v2")
    exact = e7.exact_distribution(policy, cfg, "Mei", "Monday")
    n = 6000
    counts = {"0": 0, "1": 0, "2+": 0}
    for i in range(n):
        counts[e7.simulate(policy, cfg, "Mei", "Monday", random.Random(i)).outcome] += 1
    for k in counts:
        assert counts[k] / n == pytest.approx(exact[k], abs=0.025)


def test_trace_fidelity_with_framework_retry(e7, tmp_path):
    policy = e7.ActionPolicy(ScriptedScorer(margin=60.0))
    runner = e7.AgentRunner(policy, "Dana", "Tuesday")
    cfg = dict(BASE, framework_retry="v2", log_level="debug")
    retried = 0
    for seed in range(20):
        path = runner(cfg, seed, tmp_path, f"r{seed:03d}")
        sends, emails = e7.trace_email_counts(path)
        assert sends == emails
        retried += emails >= 2
        spans, _ = read_trace(path)
        assert spans[0]["attributes"]["glassbox.env.log_level"] == "debug"
        assert "Dana" not in Path(path).read_text()  # task text only as hashes
    assert retried > 0  # at least one run exercised the v2 auto re-send


def test_goodness_of_fit(e7):
    assert e7.gof_pvalue({"1": 15, "2+": 15}, {"0": 0.0, "1": 0.5, "2+": 0.5}) > 0.5
    assert e7.gof_pvalue({"1": 30}, {"0": 0.0, "1": 0.5, "2+": 0.5}) < 0.01
    assert e7.gof_pvalue({"0": 1, "1": 29}, {"0": 0.0, "1": 1.0, "2+": 0.0}) == 0.0
    assert e7.gof_pvalue({"1": 30}, {"0": 0.0, "1": 1.0, "2+": 0.0}) == 1.0


def _case(large_attr=True, log_attr=False, fidelity=True, gof=0.5, has_large=True):
    pairs = {
        "system_prompt": {
            "class": "large" if has_large else "small",
            "attributed": large_attr,
        },
        "tool_format": {"class": "small", "attributed": False},
        "framework_retry": {"class": "small", "attributed": False},
        "log_level": {"class": "zero", "attributed": log_attr},
    }
    return {"pairs": pairs, "fidelity_ok": fidelity, "gof_p": gof}


def test_criteria_and_overall(e7):
    good = {f"c{i}": _case() for i in range(1, 5)}
    crit = e7.criteria(good, recheck=0.0)
    assert e7.overall(crit) == "PASS"
    assert (
        e7.overall(e7.criteria(dict(good, c1=_case(large_attr=False)), 0.0)) == "FAIL"
    )
    two_log = dict(good, c1=_case(log_attr=True), c2=_case(log_attr=True))
    assert e7.overall(e7.criteria(two_log, 0.0)) == "FAIL"
    assert e7.overall(e7.criteria(dict(good, c3=_case(fidelity=False)), 0.0)) == "FAIL"
    assert e7.overall(e7.criteria(good, recheck=1e-3)) == "FAIL"
    two_bad_gof = dict(good, c1=_case(gof=0.001), c2=_case(gof=0.001))
    assert e7.overall(e7.criteria(two_bad_gof, 0.0)) == "FAIL"
    none_large = {f"c{i}": _case(has_large=False) for i in range(1, 5)}
    assert e7.overall(e7.criteria(none_large, 0.0)) == "INCONCLUSIVE"


def test_run_writes_once(e7, tmp_path, monkeypatch):
    monkeypatch.setattr(e7, "N_PER_CELL", 6)
    monkeypatch.setattr(e7, "N_PERM", 199)
    res = e7.run(tmp_path, lambda name: ScriptedScorer(margin=3.0))
    assert res["overall"] in {"PASS", "FAIL", "INCONCLUSIVE"}
    saved = json.loads((tmp_path / "results.json").read_text())
    assert set(saved["per_case"]) == {"c1", "c2", "c3", "c4"}
    assert saved["model"] == "Qwen/Qwen2.5-0.5B"
    with pytest.raises(FileExistsError):
        e7.run(tmp_path, lambda name: ScriptedScorer())
