"""Tests for V7 controlled interventions (experiments/v7/intervention/PROTOCOL.md §2).

Toy runners only; Experiment 4 itself is not run here.
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List

import pytest

from glassbox.v7.intervene import (
    Factor,
    InterventionSettings,
    run_interventions,
)
from glassbox.v7.trace import Recorder, read_trace


def _label_outcome(path: Path) -> str:
    spans, _ = read_trace(path)
    chat = [s for s in spans if s["attributes"].get("gen_ai.operation.name") == "chat"]
    return str(chat[0]["attributes"]["glassbox.answer.label"])


class ToyRunner:
    """Answer is wrong if any factor named in ``breaks`` is at its candidate value.

    ``noise`` flips the answer with that probability (seeded per run).
    """

    def __init__(self, breaks: Dict[str, Any], noise: float = 0.0) -> None:
        self.breaks = breaks
        self.noise = noise
        self.calls: List[Dict[str, Any]] = []
        self.seeds: List[int] = []

    def __call__(self, config: Dict[str, Any], seed: int, out: Path, run_id: str):
        self.calls.append(dict(config))
        self.seeds.append(seed)
        rng = random.Random(seed)
        broken = any(config.get(k) == v for k, v in self.breaks.items())
        label = "distractor" if broken else "correct"
        if rng.random() < self.noise:
            label = "correct" if label == "distractor" else "distractor"
        rec = Recorder(out_dir=out, run_id=run_id)
        rec.environment["glassbox.env.config"] = json.dumps(config, sort_keys=True)
        with rec:
            with rec.span("chat", "toy", attributes={"glassbox.answer.label": label}):
                pass
        return rec.path


A = Factor("a", base=0, candidate=1)
B = Factor("b", base="x", candidate="y")
INERT = Factor("log_level", base="info", candidate="debug")
FAST = InterventionSettings(n_per_cell=12, n_perm=199, alpha=0.05, seed="t")


def test_single_cause_attributed_inert_not(tmp_path):
    runner = ToyRunner({"a": 1})
    r = run_interventions([A, INERT], runner, _label_outcome, tmp_path, FAST)
    assert r.attributed == ["a"]
    assert r.total.significant
    suff = {t.factor: t for t in r.sufficiency}
    assert suff["a"].significant and suff["a"].tvd == 1.0
    assert not suff["log_level"].significant and suff["log_level"].tvd == 0.0
    assert r.cells["only_a"].counts == {"distractor": 12}
    assert r.cells["baseline"].counts == {"correct": 12}


def test_no_effect_attributes_nothing(tmp_path):
    runner = ToyRunner({}, noise=0.3)
    r = run_interventions([INERT], runner, _label_outcome, tmp_path, FAST)
    assert r.attributed == []
    assert not r.total.significant


def test_two_causes_both_attributed(tmp_path):
    runner = ToyRunner({"a": 1, "b": "y"})
    r = run_interventions([A, B], runner, _label_outcome, tmp_path, FAST)
    assert r.attributed == ["a", "b"]


def test_necessity_weak_under_interaction_is_reported_not_gated(tmp_path):
    """Either factor alone breaks the answer: reverting one leaves it broken."""
    runner = ToyRunner({"a": 1, "b": "y"})
    r = run_interventions([A, B], runner, _label_outcome, tmp_path, FAST)
    nec = {t.factor: t for t in r.necessity}
    assert not nec["a"].significant and not nec["b"].significant
    assert r.attributed == ["a", "b"]  # sufficiency decides attribution


def test_cells_are_deduplicated(tmp_path):
    runner = ToyRunner({"a": 1})
    r = run_interventions([A, B], runner, _label_outcome, tmp_path, FAST)
    assert set(r.cells) == {
        "baseline",
        "candidate",
        "only_a",
        "only_b",
        "all_but_a",
        "all_but_b",
    }
    distinct = {json.dumps(c, sort_keys=True) for c in runner.calls}
    assert len(distinct) == 4
    assert len(runner.calls) == 4 * 12
    assert r.cells["all_but_a"].config == r.cells["only_b"].config


def test_single_factor_reuses_baseline_and_candidate(tmp_path):
    runner = ToyRunner({"a": 1})
    run_interventions([A], runner, _label_outcome, tmp_path, FAST)
    assert len(runner.calls) == 2 * 12


def test_seeds_independent_across_cells_and_deterministic(tmp_path):
    r1 = ToyRunner({"a": 1}, noise=0.2)
    rep1 = run_interventions([A, B], r1, _label_outcome, tmp_path / "x", FAST)
    r2 = ToyRunner({"a": 1}, noise=0.2)
    rep2 = run_interventions([A, B], r2, _label_outcome, tmp_path / "y", FAST)
    assert r1.seeds == r2.seeds
    assert len(set(r1.seeds)) == len(r1.seeds)
    d1, d2 = rep1.to_dict(), rep2.to_dict()
    d1.pop("paths"), d2.pop("paths")
    assert d1 == d2


def test_report_wording_and_json(tmp_path):
    runner = ToyRunner({"a": 1})
    r = run_interventions([A, INERT], runner, _label_outcome, tmp_path, FAST)
    d = r.to_dict()
    json.dumps(d)
    text = " ".join(r.evidence)
    assert "switching a alone from the baseline changed the outcome" in text
    assert "caused" not in text.lower()
    assert d["attributed"] == ["a"]
    assert len(d["paths"]["baseline"]) == 12


@pytest.mark.parametrize(
    "factors,settings,err",
    [
        ([], FAST, "at least one factor"),
        ([A, Factor("a", 2, 3)], FAST, "unique"),
        ([Factor("z", 1, 1)], FAST, "differ"),
        ([A], InterventionSettings(n_per_cell=1), "n_per_cell"),
    ],
)
def test_validation(tmp_path, factors, settings, err):
    with pytest.raises(ValueError, match=err):
        run_interventions(factors, ToyRunner({}), _label_outcome, tmp_path, settings)


def test_intervene_module_imports_with_stdlib_only():
    import ast
    import sys

    import glassbox.v7.intervene as mod

    tree = ast.parse(Path(mod.__file__).read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    stdlib = set(sys.stdlib_module_names) | {"__future__", "glassbox"}
    assert roots <= stdlib, roots - stdlib
