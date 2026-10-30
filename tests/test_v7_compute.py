"""Compute selection for V7 scorers (V8 phase B): device/dtype resolution and the
environment record, tested with a fake torch so no GPU is needed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from glassbox.v7 import compute


def fake_torch(cuda: bool, name: str = "Tesla T4", cuda_version: str = "12.4"):
    return SimpleNamespace(
        __version__="2.10.0",
        version=SimpleNamespace(cuda=cuda_version if cuda else None),
        cuda=SimpleNamespace(
            is_available=lambda: cuda,
            get_device_name=lambda i=0: name,
        ),
        float32="f32",
        float16="f16",
        bfloat16="bf16",
    )


def test_default_is_cpu_float32_like_before():
    c = compute.ComputeConfig()
    assert (c.device, c.dtype) == ("cpu", "float32")
    assert compute.resolve(c, fake_torch(cuda=True)) == c  # no silent switch to GPU


@pytest.mark.parametrize("cuda,expected", [(True, "cuda"), (False, "cpu")])
def test_auto_picks_cuda_only_when_available(cuda, expected):
    r = compute.resolve(compute.ComputeConfig("auto"), fake_torch(cuda=cuda))
    assert r.device == expected


def test_cuda_requested_but_missing_is_a_clear_error():
    with pytest.raises(ValueError, match="CUDA was requested"):
        compute.resolve(compute.ComputeConfig("cuda"), fake_torch(cuda=False))


def test_half_precision_on_cpu_is_rejected():
    with pytest.raises(ValueError, match="needs a GPU"):
        compute.resolve(compute.ComputeConfig("cpu", "float16"), fake_torch(cuda=True))


@pytest.mark.parametrize("device,dtype", [("tpu", "float32"), ("cpu", "int8")])
def test_unknown_values_rejected(device, dtype):
    with pytest.raises(ValueError):
        compute.ComputeConfig(device, dtype)


def test_environment_record_gpu():
    rec = compute.environment_record(
        compute.ComputeConfig("cuda", "bfloat16"), fake_torch(cuda=True)
    )
    assert rec["device"] == "cuda" and rec["dtype"] == "bfloat16"
    assert rec["gpu_name"] == "Tesla T4" and rec["cuda_version"] == "12.4"
    assert rec["torch_version"] == "2.10.0"
    assert rec["python_version"] and rec["platform"]


def test_environment_record_cpu_has_no_gpu_name():
    rec = compute.environment_record(compute.ComputeConfig(), fake_torch(cuda=False))
    assert rec["gpu_name"] is None and rec["cuda_version"] is None


def test_torch_dtype_mapping():
    t = fake_torch(cuda=True)
    assert compute.torch_dtype(compute.ComputeConfig("cuda", "float16"), t) == "f16"


def test_cli_args_round_trip():
    import argparse

    p = argparse.ArgumentParser()
    compute.add_cli_args(p)
    ns = p.parse_args(["--device", "auto", "--dtype", "bfloat16"])
    assert compute.from_args(ns) == compute.ComputeConfig("auto", "bfloat16")
    ns = p.parse_args([])
    assert compute.from_args(ns) == compute.ComputeConfig()


def test_scorer_default_still_loads_on_cpu(monkeypatch):
    """GPT2Scorer() without a compute config must load exactly as before (cpu)."""
    from glassbox.v7 import demo_rag

    calls = {}

    class FakeHT:
        @staticmethod
        def from_pretrained(name, **kw):
            calls.update(kw, name=name)
            return SimpleNamespace(eval=lambda: None)

    import sys

    monkeypatch.setitem(
        sys.modules, "transformer_lens", SimpleNamespace(HookedTransformer=FakeHT)
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch(cuda=False))
    s = demo_rag.GPT2Scorer()
    assert calls == {"name": "gpt2", "device": "cpu"}
    assert s.compute == compute.ComputeConfig()


def test_scorer_passes_device_and_dtype(monkeypatch):
    from glassbox.v7 import demo_rag

    calls = {}

    class FakeHT:
        @staticmethod
        def from_pretrained(name, **kw):
            calls.update(kw)
            return SimpleNamespace(eval=lambda: None)

    import sys

    monkeypatch.setitem(
        sys.modules, "transformer_lens", SimpleNamespace(HookedTransformer=FakeHT)
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch(cuda=True))
    s = demo_rag.GPT2Scorer(compute=compute.ComputeConfig("auto", "float16"))
    assert calls == {"device": "cuda", "dtype": "f16"}
    assert s.compute.device == "cuda"


def test_make_scorer_forwards_compute(monkeypatch):
    from glassbox.v7 import demo_rag

    seen = {}
    monkeypatch.setattr(
        demo_rag, "GPT2Scorer", lambda compute=None: seen.setdefault("c", compute)
    )
    cfg = compute.ComputeConfig("auto")
    demo_rag.make_scorer("gpt2", cfg)
    assert seen["c"] is cfg
