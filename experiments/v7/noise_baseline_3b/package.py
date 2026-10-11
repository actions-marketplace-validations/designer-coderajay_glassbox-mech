#!/usr/bin/env python3
"""Package V7 Experiment 3b (redundant-field merging) as a verifiable evidence bundle.

Usage:
    python3 experiments/v7/noise_baseline_3b/package.py --out evidence
    python -m glassbox.v7.evidence verify evidence/v7-exp3b-noise-baseline-merge
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from glassbox.v7.evidence import PackageSpec, build_package

HERE = Path(__file__).resolve().parent
PACKAGE_ID = "v7-exp3b-noise-baseline-merge"

CLAIM = (
    "With redundant fields merged, the group diff localised a single injected change "
    "at the right step in 0.875 of replications at N = 30 (threshold 0.80) and kept "
    "false alarms at or below 0.02 at every N from 10 to 50, on a synthetic three-"
    "step pipeline."
)
SCOPE = (
    "Pre-registered (protocol ff75707), new master seed 20261006, 200 replications "
    "per world and N. Same synthetic worlds where Experiment 3's problem was found, "
    "so not an independent test of generality. Power 0.235 at N = 10. The unmerged "
    "method reached 0.82 at N = 30 on the same data, so merging is a moderate gain. "
    "Downstream propagation is flagged more as N grows. Traces are regenerable from "
    "seeds and not included. Single author, not blind."
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
            "protocol_commit": "ff75707",
            "code_commit": "3462ed1",
            "results_commit": "55e8bcf",
            "assurance_row": "V2.9",
        },
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Package V7 Experiment 3b (redundant-field merging)"
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    pkg = build_package(args.out, PACKAGE_ID, spec())
    sys.stdout.write(f"wrote {pkg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
