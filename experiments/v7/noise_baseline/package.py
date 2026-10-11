#!/usr/bin/env python3
"""Package V7 Experiment 3 (noise-aware group diff) as a verifiable evidence bundle.

Usage:
    python3 experiments/v7/noise_baseline/package.py --out evidence
    python -m glassbox.v7.evidence verify evidence/v7-exp3-noise-baseline
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from glassbox.v7.evidence import PackageSpec, build_package

HERE = Path(__file__).resolve().parent
PACKAGE_ID = "v7-exp3-noise-baseline"

CLAIM = (
    "Pre-registered claim: at N = 30 per group, the noise-aware group diff localises "
    "a single injected change in at least 80% of replications while controlling false "
    "alarms. Result: FAIL. Chat-step localisation was 0.79 (158/200) against the 0.80 "
    "threshold; the other gated criteria passed (false alarms 0.015; GPT-2 real null "
    "8/8; real retrieval fault localised 4/4)."
)
SCOPE = (
    "Synthetic three-step pipeline (Part A, 200 replications per world) and GPT-2 "
    "small sampling on Experiment 1's corpus (Part B, 20 runs per condition). Post-"
    "hoc diagnosis: missed detections, not mislocalisation, plausibly from redundant "
    "fields inflating Holm. The pairwise diff fired on every pair of same-"
    "configuration sampled runs. Single author, not blind. The library code at the "
    "time of the run is commit 21ceb61; later versions add field merging (Experiment "
    "3b)."
)


def spec(root: Path = HERE) -> PackageSpec:
    """Build the package specification from the committed experiment files."""
    res = root / "results"
    artifacts: Dict[str, List[Union[str, Path]]] = {
        "protocol": [root / "PROTOCOL.md"],
        "code": [root / "part_a.py", root / "part_b.py"],
        "measurements_part_a": [res / "part_a" / "results.json"],
        "measurements_part_b": [res / "part_b" / "results.json"],
        "report": [root / "RESULTS.md"],
    }
    for cond in ("baseline", "baseline_more", "fault"):
        for qdir in sorted((res / "part_b" / cond).iterdir()):
            artifacts[f"traces_part_b_{cond}_{qdir.name}"] = sorted(
                qdir.glob("*.trace.jsonl")
            )
    return PackageSpec(
        claim=CLAIM,
        status="REFUTED",
        scope=SCOPE,
        artifacts=artifacts,
        provenance={
            "protocol_commit": "31f80c7",
            "code_commit": "21ceb61",
            "results_commit": "3cf24ac",
            "assurance_row": "V2.7",
        },
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Package V7 Experiment 3 (noise-aware group diff)"
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    pkg = build_package(args.out, PACKAGE_ID, spec())
    sys.stdout.write(f"wrote {pkg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
