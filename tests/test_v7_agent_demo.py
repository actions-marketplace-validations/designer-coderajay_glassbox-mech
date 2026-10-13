"""Tests for the simulated-agent investigation tab (dashboard/v7_agent_demo.py)."""

from __future__ import annotations

import ast
import importlib.util
import json
import math
import random
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

MOD_PATH = Path(__file__).resolve().parent.parent / "dashboard" / "v7_agent_demo.py"


@pytest.fixture(scope="module")
def demo():
    spec = importlib.util.spec_from_file_location("v7_agent_demo", MOD_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _label(demo, name):
    return next(k for k, v in demo.CHANGES.items() if v[0] == name)


def test_exact_is_a_distribution_and_log_level_is_inert(demo):
    d = demo.exact({})
    assert set(d) == {"0", "1", "2+"} and math.isclose(sum(d.values()), 1.0)
    assert demo.exact({"log_level": "debug"}) == d
    assert demo.exact({"framework_retry": "v2"})["2+"] > d["2+"]


def test_simulation_matches_exact(demo):
    cfg = {"framework_retry": "v2", "resend_bias": 0.6}
    ex = demo.exact(cfg)
    rng = random.Random(3)
    n = 20000
    counts = {"0": 0, "1": 0, "2+": 0}
    for _ in range(n):
        counts[demo.simulate(cfg, rng)[1]] += 1
    for k in counts:
        assert abs(counts[k] / n - ex[k]) < 0.015


def test_investigation_finds_framework_and_not_log_level(demo, tmp_path):
    sel = [_label(demo, "framework_retry"), _label(demo, "log_level")]
    md, traj, path = demo.run_agent_investigation(sel, 100, tmp_path)
    assert "attributes the change to:** `framework_retry`." in md
    assert "True effect" in md and "| `log_level` | no detectable change |" in md
    assert "Before the changes" in traj and "After the changes" in traj
    data = json.loads(Path(path).read_text())
    assert data["attributed"] == ["framework_retry"]


def test_deterministic(demo, tmp_path):
    sel = [_label(demo, "resend_bias")]
    a = demo.run_agent_investigation(sel, 40, tmp_path / "a")[0]
    b = demo.run_agent_investigation(sel, 40, tmp_path / "b")[0]
    assert a == b


@pytest.mark.parametrize(
    "sel,runs,msg", [([], 50, "Select at least one"), (None, 5, "between 10 and 200")]
)
def test_invalid_input(demo, sel, runs, msg):
    sel = list(demo.CHANGES)[:1] if sel is None else sel
    md, traj, path = demo.run_agent_investigation(sel, runs)
    assert msg in md and path is None


def test_build_tab_wires_button(demo):
    gr = MagicMock()
    demo.build_tab(gr, concurrency_id="x")
    kwargs = gr.Button.return_value.click.call_args.kwargs
    assert kwargs["fn"] is demo.run_agent_investigation
    assert kwargs["concurrency_id"] == "x"


def test_no_gradio_import_and_says_simulated(demo):
    tree = ast.parse(MOD_PATH.read_text())
    names = {a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names}
    assert "gradio" not in names
    assert "simulated" in demo.INTRO.lower()
