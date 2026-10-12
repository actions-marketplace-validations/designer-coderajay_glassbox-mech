#!/usr/bin/env python3
"""Package V7 Experiment 10 (investigation benchmark, Hard Gate 11) as an evidence bundle.

Usage:
    python3 experiments/v7/benchmark/package.py --out evidence
    python -m glassbox.v7.evidence verify evidence/v7-exp10-benchmark
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from glassbox.v7.evidence import PackageSpec, build_package

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PACKAGE_ID = "v7-exp10-benchmark"

CLAIM = (
    "On a pre-registered benchmark of 32 known-cause incidents generated from a sealed "
    "seed (GPT-2 small RAG and a synthetic tool-using agent; 192 units, 28 positive), "
    "Glassbox interventions diagnosed the exact set of large causes in 21/28 positive "
    "units (0.75; first-divergence baseline 0.50, revert-all baseline 0.00), blamed "
    "1/299 zero-effect factors, raised 1/48 false alarms on negative controls, and its "
    "implied fix was verified in 20/24 detected units. All five pre-declared criteria "
    "K1-K5 PASS; Hard Gate 11 met."
)
SCOPE = (
    "Pre-registered (protocol 5328a2b, addendum 379f8ee with the sealed seed hash, code "
    "416262f). Only 28 positive units, 26 of them from the GPT-2 RAG family; units share "
    "incidents and two factor sets were drawn twice, so Wilson intervals overstate "
    "precision; K1 interval 0.57-0.87. Four positive units whose co-changes cancelled at "
    "the outcome were missed; small effects were diagnosed exactly in 10/39 units. "
    "Factor pools, families and generator designed by the author; baselines are "
    "automated stand-ins, not human engineers; causes come from a known pool, so this "
    "is not blind diagnosis (Gate 3). Single author, one machine, one run, not "
    "independently reproduced."
)


def spec(root: Path = HERE) -> PackageSpec:
    """Build the package specification from the committed experiment files."""
    artifacts: Dict[str, List[Union[str, Path]]] = {
        "protocol": [root / "PROTOCOL.md"],
        "code": [
            root / name
            for name in (
                "generate.py",
                "families.py",
                "methods.py",
                "score.py",
                "run.py",
            )
        ]
        + [
            REPO / "glassbox" / "v7" / "intervene.py",
            REPO / "glassbox" / "v7" / "demo_rag.py",
        ],
        "tests": [REPO / "tests" / "test_v7_benchmark.py"],
        "measurements": [root / "results" / "results.json", root / "RESULTS.md"],
    }
    return PackageSpec(
        claim=CLAIM,
        status="EXPERIMENTALLY_SUPPORTED",
        scope=SCOPE,
        artifacts=artifacts,
        provenance={
            "protocol_commit": "5328a2b",
            "addendum_commit": "379f8ee",
            "code_commit": "416262f",
            "results_commit": "1a0e13a",
            "writeup_commit": "d2cf7ed",
            "sealed_seed_sha256": (
                "7dff29241343a904eda8c01a9e49790b3cbd988f1cad6e756a5638a1d79b3742"
            ),
            "model": "GPT-2 small (TransformerLens), CPU",
            "assurance_row": "V10.1",
            "related_assurance_rows": "V10 (Gate 11), V6",
        },
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Package V7 Experiment 10 (benchmark)")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    pkg = build_package(args.out, PACKAGE_ID, spec())
    sys.stdout.write(f"wrote {pkg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
