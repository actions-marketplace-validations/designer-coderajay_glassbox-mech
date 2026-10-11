#!/usr/bin/env python3
"""Package V7 Experiment 4 (controlled interventions) as a verifiable evidence bundle.

Usage:
    python3 experiments/v7/intervention/package.py --out evidence
    python -m glassbox.v7.evidence verify evidence/v7-exp4-interventions
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from glassbox.v7.evidence import PackageSpec, build_package

HERE = Path(__file__).resolve().parent
PACKAGE_ID = "v7-exp4-interventions"

CLAIM = (
    "On a synthetic pipeline with 50 runs per cell, one-factor-at-a-time "
    "interventions attributed a behaviour change to the real cause in 0.825 of "
    "replications, blamed an inert co-change in at most 0.025, and attributed both of "
    "two simultaneous causes in 0.90."
)
SCOPE = (
    "Pre-registered (protocol 30ce32f), master seed 20261011, 200 replications per "
    "world, 2 factors. I2 is a narrow pass (Wilson 95% CI 0.77-0.87). Revert-one "
    "necessity missed retrieval in about 95% of two-cause replications and is not "
    "used for attribution. Synthetic only; real systems with unknown causes remain "
    "open. Traces are regenerable from seeds and not included. Single author, not "
    "blind."
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
            "protocol_commit": "30ce32f",
            "code_commit": "87cb447",
            "results_commit": "ad75d43",
            "assurance_row": "V3.1",
        },
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Package V7 Experiment 4 (controlled interventions)"
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    pkg = build_package(args.out, PACKAGE_ID, spec())
    sys.stdout.write(f"wrote {pkg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
