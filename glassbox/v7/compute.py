# SPDX-License-Identifier: BUSL-1.1
# Copyright (C) 2026 Ajay Pravin Mahale <mahale.ajay01@gmail.com>
# Licensed under the Business Source License 1.1 (see LICENSE-COMMERCIAL).
# Free for non-production use and for production use inside your own organisation.
# Offering it as a commercial service or product to third parties needs a license.
"""Device and precision selection for V7 scorers, plus an environment record.

The default (``cpu``, ``float32``) reproduces every published V7 experiment exactly;
GPU use is always explicit (``cuda``) or opted into (``auto``). ``environment_record``
is written into ``results.json`` of new experiments so a run states where it ran.
"""

from __future__ import annotations

import argparse
import platform
import sys
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

DEVICES = ("cpu", "cuda", "auto")
DTYPES = ("float32", "float16", "bfloat16")


@dataclass(frozen=True)
class ComputeConfig:
    """Where and in what precision a model runs."""

    device: str = "cpu"
    dtype: str = "float32"

    def __post_init__(self) -> None:
        if self.device not in DEVICES:
            raise ValueError(f"device must be one of {DEVICES}, got {self.device!r}")
        if self.dtype not in DTYPES:
            raise ValueError(f"dtype must be one of {DTYPES}, got {self.dtype!r}")


def _torch(torch_module: Any = None) -> Any:
    if torch_module is not None:
        return torch_module
    import torch

    return torch


def resolve(config: ComputeConfig, torch_module: Any = None) -> ComputeConfig:
    """Turn ``auto`` into a concrete device and reject impossible combinations.

    Raises:
        ValueError: ``cuda`` requested but unavailable, or half precision on CPU.
    """
    torch = _torch(torch_module)
    has_cuda = bool(torch.cuda.is_available())
    device = config.device
    if device == "auto":
        device = "cuda" if has_cuda else "cpu"
    if device == "cuda" and not has_cuda:
        raise ValueError(
            "CUDA was requested but torch reports no GPU. On Colab, choose a GPU "
            "runtime (Runtime > Change runtime type) or use --device cpu."
        )
    if device == "cpu" and config.dtype != "float32":
        raise ValueError(f"{config.dtype} needs a GPU; use float32 on CPU")
    return ComputeConfig(device, config.dtype)


def torch_dtype(config: ComputeConfig, torch_module: Any = None) -> Any:
    """The ``torch`` dtype object for ``config.dtype``."""
    return getattr(_torch(torch_module), config.dtype)


def environment_record(
    config: ComputeConfig, torch_module: Any = None
) -> Dict[str, Optional[str]]:
    """Device, precision and software versions, for ``results.json``."""
    torch = _torch(torch_module)
    on_gpu = config.device == "cuda"
    record: Dict[str, Optional[str]] = dict(asdict(config))
    record.update(
        {
            "gpu_name": str(torch.cuda.get_device_name(0)) if on_gpu else None,
            "cuda_version": (
                str(torch.version.cuda) if on_gpu and torch.version.cuda else None
            ),
            "torch_version": str(torch.__version__),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
        }
    )
    return record


def add_cli_args(parser: argparse.ArgumentParser) -> None:
    """Add ``--device`` and ``--dtype`` with the reproducible defaults."""
    parser.add_argument("--device", choices=DEVICES, default="cpu")
    parser.add_argument("--dtype", choices=DTYPES, default="float32")


def from_args(args: argparse.Namespace) -> ComputeConfig:
    """Build a :class:`ComputeConfig` from parsed CLI arguments."""
    return ComputeConfig(
        getattr(args, "device", "cpu"), getattr(args, "dtype", "float32")
    )
