"""Experiment 7b Addendum 3: the numeric-explanation check, without loading a model."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "experiments"
    / "v7"
    / "agent_b"
    / "explain_numeric.py"
)


@pytest.fixture()
def mod():
    spec = importlib.util.spec_from_file_location("exp7b_numeric", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_constants_match_addendum(mod):
    assert mod.MODEL == "Qwen/Qwen2.5-0.5B-Instruct"
    assert (mod.RUN1, mod.RUN2) == (0.327629, 0.327631)
    assert mod.TOL == 1e-4
    assert [c.name for c in mod.CONFIGS] == ["A1", "A2", "B_threads1", "C_scalar"]
    env = {c.name: c.env for c in mod.CONFIGS}
    assert env["A1"] == {} and env["A2"] == {}
    assert env["B_threads1"] == {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}
    assert env["C_scalar"] == {"ATEN_CPU_CAPABILITY": "default"}


def _vals(a1, a2, b, c):
    return {"A1": a1, "A2": a2, "B_threads1": b, "C_scalar": c}


def test_explained_when_repeatable_sensitive_and_close(mod):
    ev = mod.evaluate(_vals(0.3276301, 0.3276301, 0.3276312, 0.3276301))
    assert ev["E1_within_setting_identical"]
    assert ev["E2_order_sensitive"]
    assert ev["E3_close_and_same_decision"]
    assert ev["verdict"] == "EXPLAINED"


def test_not_explained_if_nothing_moves(mod):
    ev = mod.evaluate(_vals(0.3276301, 0.3276301, 0.3276301, 0.3276301))
    assert not ev["E2_order_sensitive"]
    assert ev["verdict"] == "NOT EXPLAINED"


def test_not_explained_if_same_setting_differs(mod):
    ev = mod.evaluate(_vals(0.3276301, 0.3276302, 0.3276312, 0.3276301))
    assert not ev["E1_within_setting_identical"]
    assert ev["verdict"] == "NOT EXPLAINED"


def test_not_explained_if_far_from_runs_or_decision_flips(mod):
    far = mod.evaluate(_vals(0.33, 0.33, 0.3301, 0.33))
    assert not far["E3_close_and_same_decision"]
    assert far["verdict"] == "NOT EXPLAINED"
    big_move = mod.evaluate(_vals(0.3276301, 0.3276301, 0.3279, 0.3276301))
    assert not big_move["E2_order_sensitive"]  # a move > TOL is not "last digits"


def test_cpu_info_parses_proc_cpuinfo(mod, tmp_path):
    f = tmp_path / "cpuinfo"
    f.write_text(
        "processor\t: 0\nmodel name\t: Intel(R) Xeon(R) CPU @ 2.20GHz\n"
        "flags\t\t: fpu sse avx2 avx512f\n\nprocessor\t: 1\n"
        "model name\t: Intel(R) Xeon(R) CPU @ 2.20GHz\nflags\t\t: fpu avx2 avx512f\n"
    )
    info = mod.cpu_info(f)
    assert info["model_name"] == "Intel(R) Xeon(R) CPU @ 2.20GHz"
    assert info["logical_cpus"] == 2
    assert info["avx2"] is True and info["avx512f"] is True


def test_cpu_info_missing_file(mod, tmp_path):
    info = mod.cpu_info(tmp_path / "nope")
    assert info["model_name"] is None and info["logical_cpus"] == 0


def test_measure_single_uses_fresh_cache_and_full_precision(mod):
    class FakeModel:
        def to_tokens(self, text, prepend_bos=False):
            class S:
                shape = (1, 1)

            return S()

    class FakeScorer:
        model = FakeModel()
        calls = 0

        def __call__(self, prompt, label):
            FakeScorer.calls += 1
            return 1.0 if label.strip() == "2" else 0.0

    value = mod.measure_single(lambda name: FakeScorer())
    assert isinstance(value, float)
    assert FakeScorer.calls > 0
    assert repr(value) == mod.format_value(value)
