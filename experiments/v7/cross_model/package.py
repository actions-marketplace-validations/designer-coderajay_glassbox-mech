#!/usr/bin/env python3
"""Package V7 Experiment 6 (cross-model investigation) as a verifiable evidence bundle.

Usage:
    python3 experiments/v7/cross_model/package.py --out evidence
    python -m glassbox.v7.evidence verify evidence/v7-exp6-cross-model
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from glassbox.v7.evidence import PackageSpec, build_package

HERE = Path(__file__).resolve().parent
PACKAGE_ID = "v7-exp6-cross-model"

CLAIM = (
    "Experiment 5's investigation, unchanged, on three further model families "
    "(Pythia-160m, OPT-125m, Qwen2.5-0.5B) blamed every large true effect "
    "(3/3, 3/3, 4/4), none of the 36 exactly-zero effects, and re-scored "
    "deterministically."
)
SCOPE = (
    "Pre-registered (protocol 74f1958). Ground truth computed exactly from each "
    "model's deterministic margins. Large effects were mostly near-deterministic. "
    "Detection limit at 30 runs per configuration: true effects of about 0.41 and "
    "above detected, about 0.16 and below missed. Small local open-weights models "
    "only, no hosted providers, two-option sampling, factors chosen by the author. "
    "Traces are regenerable and not included. Single author."
)


def spec(root: Path = HERE) -> PackageSpec:
    """Build the package specification from the committed experiment files."""
    res = root / "results"
    artifacts: Dict[str, List[Union[str, Path]]] = {
        "protocol": [root / "PROTOCOL.md"],
        "code": [root / "run.py"],
        "measurements": [res / "results.json", root / "RESULTS.md"],
    }
    return PackageSpec(
        claim=CLAIM,
        status="EXPERIMENTALLY_SUPPORTED",
        scope=SCOPE,
        artifacts=artifacts,
        provenance={
            "protocol_commit": "74f1958",
            "code_commit": "a0f8c7d",
            "results_commit": "3314c58",
            "assurance_row": "V3.6",
        },
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Package V7 Experiment 6 (cross-model investigation)"
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    pkg = build_package(args.out, PACKAGE_ID, spec())
    sys.stdout.write(f"wrote {pkg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
