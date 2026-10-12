"""glassbox.v7.reproduce: plan and check a reproduction from an evidence package."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from glassbox.v7 import reproduce
from glassbox.v7.evidence import PackageSpec, build_package

ROOT = Path(__file__).resolve().parent.parent
ORIG = {
    "overall": "PASS",
    "criteria": {"C1": {"pass": True, "value": 0.825, "n": 40, "label": "4/4"}},
    "environment": {"python": "3.11.9"},
}


def _clone(d):
    return json.loads(json.dumps(d))


def test_identical_is_reproduced():
    rep = reproduce.compare_results(ORIG, _clone(ORIG))
    assert rep["verdict"] == "REPRODUCED" and rep["mismatches"] == []


def test_float_within_tolerance_is_reproduced():
    fresh = _clone(ORIG)
    fresh["criteria"]["C1"]["value"] = 0.82500004
    assert reproduce.compare_results(ORIG, fresh, tol=1e-6)["verdict"] == "REPRODUCED"


def test_float_beyond_tolerance_keeps_decisions():
    fresh = _clone(ORIG)
    fresh["criteria"]["C1"]["value"] = 0.83
    rep = reproduce.compare_results(ORIG, fresh, tol=1e-6)
    assert rep["verdict"] == "DECISIONS_ONLY"
    assert rep["mismatches"][0]["path"] == "criteria.C1.value"


@pytest.mark.parametrize(
    "path,value",
    [
        (("overall",), "FAIL"),
        (("criteria", "C1", "pass"), False),
        (("criteria", "C1", "n"), 41),
        (("criteria", "C1", "label"), "3/4"),
    ],
)
def test_decision_level_change_is_not_reproduced(path, value):
    fresh = _clone(ORIG)
    node = fresh
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    assert reproduce.compare_results(ORIG, fresh)["verdict"] == "NOT_REPRODUCED"


def test_missing_key_is_not_reproduced_and_ignored_keys_skipped():
    fresh = _clone(ORIG)
    del fresh["criteria"]["C1"]["n"]
    assert reproduce.compare_results(ORIG, fresh)["verdict"] == "NOT_REPRODUCED"
    env = _clone(ORIG)
    env["environment"]["python"] = "3.13.0"
    rep = reproduce.compare_results(ORIG, env, ignore=("environment",))
    assert rep["verdict"] == "REPRODUCED"


def test_every_evidence_package_has_a_recipe():
    recipes = reproduce.load_recipes()
    packages = sorted(p.name for p in (ROOT / "evidence").iterdir() if p.is_dir())
    assert set(packages) <= set(recipes)
    for pid in packages:
        r = recipes[pid]
        assert len(r["commit"]) >= 7 and r["run"] and r["results"]
        for rel in r["packaged_results"]:
            assert (ROOT / "evidence" / pid / "artifacts" / rel).is_file()


def test_plan_lists_checkout_and_steps():
    text = reproduce.plan(ROOT / "evidence" / "v7-exp8-cross-stack")
    recipe = reproduce.load_recipes()["v7-exp8-cross-stack"]
    assert f"git checkout {recipe['commit']}" in text
    assert "python -m glassbox.v7.reproduce compare" in text


def _toy_package(tmp_path):
    res = tmp_path / "results.json"
    res.write_text(json.dumps(ORIG))
    spec = PackageSpec("c", "PRELIMINARY", "s", {"measurements": [res]}, {})
    return build_package(tmp_path / "ev", "toy", spec)


def test_check_writes_report_once(tmp_path):
    pkg = _toy_package(tmp_path)
    fresh = tmp_path / "fresh.json"
    fresh.write_text(json.dumps(ORIG))
    recipe = {"packaged_results": ["measurements/results.json"], "results": ["x"]}
    out = tmp_path / "report.json"
    rep = reproduce.check(
        pkg, [fresh], out, "Alice Example", "Linux x86", recipe=recipe
    )
    assert rep["verdict"] == "REPRODUCED"
    saved = json.loads(out.read_text())
    assert saved["reproducer"] == "Alice Example" and saved["package_manifest_sha256"]
    with pytest.raises(FileExistsError):
        reproduce.check(pkg, [fresh], out, "Alice Example", "Linux x86", recipe=recipe)


def test_check_refuses_tampered_package(tmp_path):
    pkg = _toy_package(tmp_path)
    (pkg / "artifacts" / "measurements" / "results.json").write_text("{}")
    fresh = tmp_path / "fresh.json"
    fresh.write_text(json.dumps(ORIG))
    recipe = {"packaged_results": ["measurements/results.json"], "results": ["x"]}
    with pytest.raises(reproduce.ReproductionError):
        reproduce.check(pkg, [fresh], tmp_path / "r.json", "A", "B", recipe=recipe)
