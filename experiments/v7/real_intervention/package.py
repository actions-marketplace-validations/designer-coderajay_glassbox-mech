#!/usr/bin/env python3
"""Package V7 Experiment 5 (interventions on GPT-2 RAG) as a verifiable evidence bundle.

Usage:
    python3 experiments/v7/real_intervention/package.py --out evidence
    python -m glassbox.v7.evidence verify evidence/v7-exp5-real-interventions
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from glassbox.v7.evidence import PackageSpec, build_package

HERE = Path(__file__).resolve().parent
PACKAGE_ID = "v7-exp5-real-interventions"

CLAIM = (
    "On GPT-2 small RAG with three simultaneous changes (stale index, prompt-template "
    "edit, inert log setting), one-factor interventions with 30 runs per cell "
    "attributed the known real fault for 4/4 affected questions, never blamed the "
    "zero-effect index (4/4 unaffected questions) or the inert setting (0/8), and the "
    "model's scores were deterministic on re-scoring."
)
SCOPE = (
    "Pre-registered (protocol 47ce955). Two-option sampling from GPT-2's own "
    "probabilities on Experiment 1's 8 fictional questions. The fault attribution was "
    "close to mechanical. Small real template effects (true TVD 0.05-0.11 on q3, q7) "
    "were not detected at 30 runs per cell. Factors were chosen and switched by the "
    "author, so this is not a blind test. Traces are regenerable and not included. "
    "Single author."
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
            "protocol_commit": "47ce955",
            "code_commit": "d1ac3ec",
            "results_commit": "e47cf4e",
            "assurance_row": "V3.3",
        },
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Package V7 Experiment 5 (interventions on GPT-2 RAG)"
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    pkg = build_package(args.out, PACKAGE_ID, spec())
    sys.stdout.write(f"wrote {pkg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
