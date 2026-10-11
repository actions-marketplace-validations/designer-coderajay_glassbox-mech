"""Mechanics of V7 Experiment 3b (experiments/v7/noise_baseline_3b) without running it.

No test uses a protocol group size (10, 20, 30, 50) with the protocol seeds: smoke
runs use N = 4, and the criteria logic is checked on fabricated summaries.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

EXP = (
    Path(__file__).resolve().parent.parent / "experiments" / "v7" / "noise_baseline_3b"
)


@pytest.fixture(scope="module")
def r3b():
    spec = importlib.util.spec_from_file_location("exp3b_run", EXP / "run.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_constants_match_protocol(r3b):
    assert r3b.MASTER_SEED == 20261006
    assert tuple(r3b.GROUP_SIZES) == (10, 20, 30, 50)
    assert (r3b.GATE_N, r3b.REPLICATIONS, r3b.N_PERM, r3b.ALPHA) == (30, 200, 999, 0.05)
    exp3 = r3b.load_exp3()
    assert exp3.BASELINE == exp3.Params(0.90, 0.85, 0.20)
    assert exp3.CANDIDATE["W1"] == exp3.Params(0.90, 0.35, 0.20)


def _report(label_tested=True, merged=("present", "status", "gen_ai.tool.name")):
    tool = "execute_tool:send_confirmation#0"
    return {
        "fields": [
            {
                "step": "chat#0",
                "field": "glassbox.answer.label",
                "classification": "tested" if label_tested else "constant",
                "merged_with": [f"{tool} {m}" for m in merged],
            }
        ]
    }


def test_merge_ok(r3b):
    assert r3b.merge_ok(_report())
    assert not r3b.merge_ok(_report(merged=("present",)))
    assert not r3b.merge_ok(_report(label_tested=False))
    assert not r3b.merge_ok({"fields": []})


def test_replicate_smoke_non_protocol_size(r3b):
    exp3 = r3b.load_exp3()
    out = r3b.replicate(exp3, "W1", 4, 0)
    assert set(out) == {"merged", "unmerged"}
    assert {"merge_ok", "n_tests"} <= set(out["merged"])
    assert out["merged"]["output_hash_classification"] == "untestable"


def _s(first=None, steps=(), merge_ok=True):
    return {
        "any_significant": bool(steps),
        "first": list(first) if first else None,
        "significant_steps": sorted(steps),
        "output_hash_classification": "untestable",
        "pairwise_divergence_rate": None,
        "merge_ok": merge_ok,
        "n_tests": 2,
    }


def _world(n_rows=10, sizes=(10, 30)):
    chat, ret = ("chat#0", "x"), ("retrieval#0", "y")
    good = {
        "W0": lambda: _s(),
        "W1": lambda: _s(chat, ["chat#0", "execute_tool:send_confirmation#0"]),
        "W2": lambda: _s(ret, ["retrieval#0", "chat#0"]),
        "W3": lambda: _s(ret, ["retrieval#0", "chat#0"]),
    }
    return {
        w: {
            str(n): [{"merged": f(), "unmerged": f()} for _ in range(n_rows)]
            for n in sizes
        }
        for w, f in good.items()
    }


def test_evaluate_pass(r3b):
    crit = r3b.evaluate(_world())
    assert r3b.overall(crit) == "PASS"
    assert crit["D1_power_curve"]["30"]["W1_first_at_chat"] == 1.0
    assert crit["D3_one_vs_two_causes"]["10"]["chat_flagged_W2"] == 1.0


def test_type_I_must_hold_at_every_size(r3b):
    world = _world()
    for row in world["W0"]["10"]:
        row["merged"] = _s(("chat#0", "x"), ["chat#0"])
    crit = r3b.evaluate(world)
    assert not crit["A1p_type_I"]["pass"]
    assert r3b.overall(crit) == "FAIL"


def test_localisation_and_merge_failures(r3b):
    world = _world()
    for row in world["W1"]["30"]:
        row["merged"] = _s(None, [], merge_ok=False)
    crit = r3b.evaluate(world)
    assert not crit["A2p_chat_localisation"]["pass"]
    assert not crit["A7_merge_validity"]["pass"]


def test_unmerged_rates_do_not_gate(r3b):
    world = _world()
    for row in world["W1"]["30"]:
        row["unmerged"] = _s()
    crit = r3b.evaluate(world)
    assert crit["D2_merge_effect_unmerged"]["30"]["W1_first_at_chat"] == 0.0
    assert r3b.overall(crit) == "PASS"


def test_run_writes_once(r3b, tmp_path, monkeypatch):
    monkeypatch.setattr(r3b, "GATE_N", 4)
    res = r3b.run(tmp_path, reps=2, sizes=(4,))
    assert res["overall"] in {"PASS", "FAIL"}
    saved = json.loads((tmp_path / "results.json").read_text())
    assert saved["settings"]["master_seed"] == 20261006
    with pytest.raises(FileExistsError):
        r3b.run(tmp_path, reps=2, sizes=(4,))
