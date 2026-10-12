"""V7 Experiment 10 (investigation benchmark) mechanics, with toy scorers and no model."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest

EXP = Path(__file__).resolve().parent.parent / "experiments" / "v7" / "benchmark"
TEST_SEED = "bench-test-seed-not-the-real-one"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"bench_{name}", EXP / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gen():
    return _load("generate")


@pytest.fixture(scope="module")
def fam():
    return _load("families")


@pytest.fixture(scope="module")
def meth():
    return _load("methods")


@pytest.fixture(scope="module")
def score():
    return _load("score")


@pytest.fixture(scope="module")
def run():
    return _load("run")


# --- generator --------------------------------------------------------------


def test_seed_hash_matches_addendum(gen):
    assert gen.SEED_SHA256 == (
        "7dff29241343a904eda8c01a9e49790b3cbd988f1cad6e756a5638a1d79b3742"
    )
    with pytest.raises(ValueError):
        gen.check_seed(TEST_SEED)


def test_generator_counts_and_rules(gen):
    inc = gen.generate(TEST_SEED)
    assert len(inc) == 32
    fams = [(i["family"], i["negative"]) for i in inc]
    assert fams.count(("R", False)) == 12 and fams.count(("R", True)) == 4
    assert fams.count(("S", False)) == 12 and fams.count(("S", True)) == 4
    for i in inc:
        names = [f["name"] for f in i["factors"]]
        inert = gen.R_INERT if i["family"] == "R" else gen.S_INERT
        effect = gen.R_EFFECT if i["family"] == "R" else gen.S_EFFECT
        assert len(set(names)) == len(names)
        assert all(f["base"] != f["candidate"] for f in i["factors"])
        if i["negative"]:
            assert 1 <= len(names) <= 2 and set(names) <= set(inert)
        else:
            assert 2 <= len(names) <= 4
            n_inert = len(set(names) & set(inert))
            assert 1 <= n_inert <= min(2, len(names) - 1)
            assert set(names) - set(inert) <= set(effect)


def test_generator_is_deterministic_and_seed_sensitive(gen):
    assert gen.generate(TEST_SEED) == gen.generate(TEST_SEED)
    assert gen.generate(TEST_SEED) != gen.generate(TEST_SEED + "x")


def test_s_magnitudes_in_ranges(gen):
    for i in gen.generate(TEST_SEED):
        for f in i["factors"]:
            if f["name"] in gen.S_RANGES:
                lo, hi = gen.S_RANGES[f["name"]]
                assert lo <= f["candidate"] <= hi
                assert round(f["candidate"], 3) == f["candidate"]


# --- family S (synthetic agent) ---------------------------------------------


def test_s_exact_is_a_distribution_and_inert_has_zero_effect(fam, gen):
    base = dict(gen.S_BASE)
    for item in fam.S_ITEMS:
        d = fam.s_exact(base, item)
        assert set(d) == {"0", "1", "2+"} and math.isclose(sum(d.values()), 1.0)
        inert = fam.s_exact(
            {**base, "log_level": "debug", "trace_sampling": "on"}, item
        )
        assert inert == d
    v2 = fam.s_exact({**base, "framework_retry": "v2"}, "c3")
    assert v2["2+"] > fam.s_exact(base, "c3")["2+"]


def test_s_simulation_matches_exact(fam, gen):
    import random

    cfg = {**gen.S_BASE, "skip_check": 0.3, "early_stop": 0.4}
    exact = fam.s_exact(cfg, "c1")
    rng = random.Random(1)
    n = 20000
    counts = {"0": 0, "1": 0, "2+": 0}
    for _ in range(n):
        counts[fam.s_simulate(cfg, "c1", rng)[1]] += 1
    for k in counts:
        assert abs(counts[k] / n - exact[k]) < 0.015


def test_s_runner_records_trace(fam, gen, tmp_path):
    from glassbox.v7.trace import read_trace

    run = fam.s_runner("c3")
    path = run({"framework_retry": "v2", "log_level": "debug"}, 5, tmp_path, "r0")
    spans, _ = read_trace(path)
    assert spans[0]["attributes"]["glassbox.env.log_level"] == "debug"
    assert fam.s_outcome(path) in {"0", "1", "2+"}


# --- family R (RAG, toy scorer) ---------------------------------------------


def test_r_prompt_factors(fam):
    base = dict(fam.R_BASE)
    p0 = fam.r_prompt(base, "q1")
    assert fam.r_prompt({**base, "log_level": "debug", "cache_mode": "on"}, "q1") == p0
    assert fam.r_prompt({**base, "preamble": "one_word"}, "q1").startswith(
        "Answer with one word.\n"
    )
    assert fam.r_prompt({**base, "top_k": 2}, "q1") != p0
    assert fam.r_prompt({**base, "index": "stale"}, "q5") == fam.r_prompt(base, "q5")
    assert fam.r_prompt({**base, "index": "stale"}, "q1") != p0


def test_r_exact_and_runner(fam, tmp_path):
    from glassbox.v7.demo_rag import toy_scorer

    margins = fam.Margins(toy_scorer)
    base = dict(fam.R_BASE)
    d = fam.r_exact(base, "q1", margins)
    assert math.isclose(d["correct"] + d["wrong"], 1.0)
    assert fam.r_exact({**base, "cache_mode": "on"}, "q1", margins) == d
    run = fam.r_runner("q1", margins)
    path = run({"index": "stale"}, 3, tmp_path, "r0")
    assert fam.r_outcome(path) in {"correct", "wrong"}


# --- methods and scoring ----------------------------------------------------


def _settings(meth, n=12):
    from glassbox.v7.intervene import InterventionSettings

    return InterventionSettings(n, 199, 0.05, "t")


def test_run_unit_s_large_cause_found(meth, fam, gen, tmp_path):
    inc = {
        "id": "T1",
        "family": "S",
        "negative": False,
        "factors": [
            {"name": "early_stop", "base": 0.02, "candidate": 0.8},
            {"name": "log_level", "base": "info", "candidate": "debug"},
        ],
    }
    u = meth.run_unit(inc, "c1", tmp_path, _settings(meth, 40))
    assert u["truth"]["log_level"] == 0.0
    assert u["truth"]["early_stop"] > 0.5
    assert u["methods"]["B0"]["blamed"] in ([], ["early_stop", "log_level"])
    assert u["methods"]["GB"]["blamed"] in ([], ["early_stop"])
    assert set(u["methods"]) == {"GB", "B0", "B1"}
    assert u["runs"] > 0
    for m in u["methods"].values():
        assert set(m) >= {"detected", "blamed", "fix_tvd"}


def test_run_unit_r_toy(meth, tmp_path):
    inc = {
        "id": "T2",
        "family": "R",
        "negative": True,
        "factors": [{"name": "cache_mode", "base": "off", "candidate": "on"}],
    }
    from glassbox.v7.demo_rag import toy_scorer

    u = meth.run_unit(inc, "q2", tmp_path, _settings(meth), scorer=toy_scorer)
    assert u["truth"] == {"cache_mode": 0.0}
    assert u["methods"]["B1"]["detected"] in (True, False)


def _unit(truth, gb, b0, b1, fam="R", neg=False):
    def m(blamed, det=True, fix=0.0):
        return {"detected": det, "blamed": blamed, "fix_tvd": fix}

    return {
        "family": fam,
        "negative": neg,
        "truth": truth,
        "runs": 10,
        "methods": {"GB": m(*gb), "B0": m(*b0), "B1": m(*b1)},
    }


def test_scoring_metrics_and_criteria(score):
    units = [
        _unit({"a": 0.8, "z": 0.0}, (["a"],), (["a", "z"],), (["a", "z"],)),
        _unit({"a": 0.7, "z": 0.0}, (["a"],), (["a", "z"],), ([], False)),
        _unit({"z": 0.0}, ([], False), ([], False), ([], False), neg=True),
    ]
    out = score.score(units)
    gb = out["pooled"]["GB"]
    assert gb["M2_exact_diagnosis"]["value"] == 1.0
    assert out["pooled"]["B0"]["M2_exact_diagnosis"]["value"] == 0.0
    assert gb["M4_zero_false_blame"]["value"] == 0.0
    assert out["pooled"]["B0"]["M4_zero_false_blame"]["value"] == pytest.approx(2 / 3)
    assert gb["M5_false_alarm"]["value"] == 0.0
    crit = out["criteria"]
    assert crit["K1"]["pass"] and crit["K2"]["pass"] and crit["K3"]["pass"]
    assert out["v10_1"] == "PASS"
    lo, hi = score.wilson(3, 4)
    assert 0 < lo < 0.75 < hi <= 1


def test_wilson_edge_cases(score):
    assert score.wilson(0, 0) == (None, None)
    lo, hi = score.wilson(0, 10)
    assert lo == 0.0 and hi > 0


def test_run_end_to_end_tiny_writes_once(run, tmp_path):
    from glassbox.v7.demo_rag import toy_scorer

    res = run.run_benchmark(
        TEST_SEED,
        tmp_path,
        scorer=toy_scorer,
        n_per_cell=6,
        n_perm=49,
        check=False,
        limit=2,
    )
    assert res["gate11"] == "MET" and res["v10_1"] in {"PASS", "FAIL"}
    saved = json.loads((tmp_path / "results.json").read_text())
    assert saved["seed_sha256"] == hashlib.sha256(TEST_SEED.encode()).hexdigest()
    with pytest.raises(FileExistsError):
        run.run_benchmark(TEST_SEED, tmp_path, scorer=toy_scorer, check=False, limit=1)


def test_run_cli_refuses_wrong_seed(run, tmp_path):
    with pytest.raises(ValueError):
        run.main(["--seed", TEST_SEED, "--out", str(tmp_path)])
