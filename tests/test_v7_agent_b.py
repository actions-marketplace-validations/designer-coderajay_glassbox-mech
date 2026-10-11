"""Mechanics of V7 Experiment 7b (experiments/v7/agent_b) without loading a model.

Fake scorers with fake tokenisation stand in for the Qwen-Instruct ladder.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from glassbox.v7.trace import canonical_json, read_trace

EXP = Path(__file__).resolve().parent.parent / "experiments" / "v7" / "agent_b"


@pytest.fixture()
def e7b():
    spec = importlib.util.spec_from_file_location("exp7b_run", EXP / "run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _Shape:
    def __init__(self, n: int) -> None:
        self.shape = (1, n)


class FakeModel:
    """Tokenises `` 1``-style labels as one token unless told otherwise."""

    def __init__(self, spaced_single: bool = True, bare_single: bool = True) -> None:
        self.spaced_single, self.bare_single = spaced_single, bare_single

    def to_tokens(self, text: str, prepend_bos: bool = False) -> _Shape:
        if text.startswith(" "):
            return _Shape(1 if self.spaced_single else 2)
        return _Shape(1 if self.bare_single else 2)


class MenuScorer:
    """Competent policy: check, then send, resend after timeout, finish after ok."""

    def __init__(self, competent: bool = True, margin: float = 20.0, **tok) -> None:
        self.competent, self.margin = competent, margin
        self.model = FakeModel(**tok)

    def __call__(self, prompt: str, label: str) -> float:
        k = label.strip()
        if not self.competent:
            return self.margin if k == "3" else 0.0  # always finish
        history = prompt.split("Actions:")[0]
        steps = history.count("Step ")
        last = history.rsplit("Step ", 1)[-1] if steps else ""
        if steps == 0:
            want = "1"
        elif "send_confirmation -> ok" in last:
            want = "3"
        else:
            want = "2"
        return self.margin if k == want else 0.0


def test_constants_match_protocol(e7b):
    assert e7b.LADDER == (
        "Qwen/Qwen2.5-0.5B-Instruct",
        "Qwen/Qwen2.5-1.5B-Instruct",
        "Qwen/Qwen2.5-3B-Instruct",
    )
    assert (e7b.COMPETENCE_MIN, e7b.SEED_PREFIX) == (0.6, "exp7b")
    assert e7b.MENU == (
        "Actions:\n1. check_calendar\n2. send_confirmation\n3. finish\n"
        "Next action (1, 2 or 3):"
    )
    assert e7b.LABEL_SETS == ((" 1", " 2", " 3"), ("1", "2", "3"))
    e7 = e7b.load_exp7()
    assert (e7.N_PER_CELL, e7.N_PERM, e7.P_TIMEOUT, e7.MAX_DECISIONS) == (
        30,
        999,
        0.5,
        4,
    )


def test_menu_prompt(e7b):
    e7 = e7b.load_exp7()
    base = e7.build_prompt("strict", "Dana", "Tuesday", ["Step 1: check_calendar -> x"])
    menu = e7b.menu_prompt(base)
    assert menu.endswith(e7b.MENU)
    assert "Step 1: check_calendar -> x\nActions:\n1. check_calendar" in menu
    assert "Next action:" not in menu


def test_choose_labels(e7b):
    assert e7b.choose_labels(FakeModel()) == (" 1", " 2", " 3")
    assert e7b.choose_labels(FakeModel(spaced_single=False)) == ("1", "2", "3")
    assert e7b.choose_labels(FakeModel(spaced_single=False, bare_single=False)) is None


def test_menu_policy_maps_labels_to_actions(e7b):
    e7 = e7b.load_exp7()
    policy = e7b.MenuPolicy(MenuScorer(), (" 1", " 2", " 3"))
    p = policy.probs(e7.build_prompt("strict", "Dana", "Tuesday", []))
    assert p[0] > 0.99  # check_calendar first
    assert policy.recheck() == 0.0


def test_competence(e7b):
    good = e7b.MenuPolicy(MenuScorer(margin=60.0), (" 1", " 2", " 3"))
    assert e7b.competence(good) == pytest.approx(0.5, abs=1e-6)  # timeout 0.5 -> resend
    lazy = e7b.MenuPolicy(MenuScorer(competent=False, margin=60.0), (" 1", " 2", " 3"))
    assert e7b.competence(lazy) == pytest.approx(0.0, abs=1e-6)


class OneShotScorer(MenuScorer):
    """Sends exactly once: after any send (ok or timeout) it finishes."""

    def __call__(self, prompt: str, label: str) -> float:
        k = label.strip()
        history = prompt.split("Actions:")[0]
        steps = history.count("Step ")
        last = history.rsplit("Step ", 1)[-1] if steps else ""
        want = "1" if steps == 0 else ("3" if "send_confirmation" in last else "2")
        return self.margin if k == want else 0.0


def test_ladder_stops_at_first_competent(e7b):
    calls = []

    def factory(name):
        calls.append(name)
        if name.endswith("0.5B-Instruct"):
            return MenuScorer(competent=False, margin=60.0)
        return OneShotScorer(margin=60.0)

    selected, ladder = e7b.select_model(factory)
    assert selected is not None and selected[0] == "Qwen/Qwen2.5-1.5B-Instruct"
    assert calls == ["Qwen/Qwen2.5-0.5B-Instruct", "Qwen/Qwen2.5-1.5B-Instruct"]
    assert ladder[0]["competence"] == pytest.approx(0.0, abs=1e-6)
    assert ladder[1]["competence"] == pytest.approx(1.0, abs=1e-6)


def test_ladder_records_not_run_and_inconclusive(e7b):
    def factory(name):
        if name.endswith("3B-Instruct"):
            raise MemoryError("does not fit in 8 GB")
        if name.endswith("1.5B-Instruct"):
            return MenuScorer(spaced_single=False, bare_single=False)
        return MenuScorer(competent=False, margin=60.0)

    selected, ladder = e7b.select_model(factory)
    assert selected is None
    assert [r["status"] for r in ladder] == ["NOT COMPETENT", "NOT RUN", "NOT RUN"]
    assert (
        "single-token" in ladder[1]["reason"] and "MemoryError" in ladder[2]["reason"]
    )


def test_runner_records_menu_prompt_and_label(e7b, tmp_path):
    e7 = e7b.load_exp7()
    policy = e7b.MenuPolicy(OneShotScorer(margin=60.0), (" 1", " 2", " 3"))
    runner = e7b.MenuAgentRunner(policy, "Dana", "Tuesday")
    cfg = dict(e7.BASE_CONFIG, framework_retry="v2")
    path = runner(cfg, 3, tmp_path, "r000")
    spans, _ = read_trace(path)
    chats = [s for s in spans if s["attributes"].get("gen_ai.operation.name") == "chat"]
    assert [c["attributes"]["glassbox.agent.action_label"] for c in chats][0] == "1"
    first_menu = e7b.menu_prompt(e7.build_prompt("strict", "Dana", "Tuesday", []))
    msgs = [{"role": "user", "parts": [{"type": "text", "content": first_menu}]}]
    want = hashlib.sha256(canonical_json(msgs).encode()).hexdigest()
    assert (
        chats[0]["attributes"]["glassbox.content.gen_ai.input.messages.sha256"] == want
    )
    sends, emails = e7.trace_email_counts(path)
    assert sends == emails


def test_run_writes_once(e7b, tmp_path, monkeypatch):
    e7 = e7b.load_exp7()
    monkeypatch.setattr(e7, "N_PER_CELL", 6)
    monkeypatch.setattr(e7, "N_PERM", 199)
    res = e7b.run(tmp_path, lambda name: OneShotScorer(margin=3.0))
    assert res["selected_model"] == "Qwen/Qwen2.5-0.5B-Instruct"
    assert res["overall"] in {"PASS", "FAIL", "INCONCLUSIVE"}
    saved = json.loads((tmp_path / "results.json").read_text())
    assert set(saved["per_case"]) == {"c1", "c2", "c3", "c4"}
    with pytest.raises(FileExistsError):
        e7b.run(tmp_path, lambda name: OneShotScorer())


def test_run_inconclusive_when_no_competent_model(e7b, tmp_path):
    res = e7b.run(tmp_path, lambda name: MenuScorer(competent=False, margin=60.0))
    assert res["overall"] == "INCONCLUSIVE" and res["selected_model"] is None
    assert res["per_case"] == {}
