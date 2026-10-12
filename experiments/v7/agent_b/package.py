#!/usr/bin/env python3
"""Package V7 Experiment 7b (LLM tool-using agent) as a verifiable evidence bundle.

Usage:
    python3 experiments/v7/agent_b/package.py --out evidence
    python -m glassbox.v7.evidence verify evidence/v7-exp7b-agent
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from glassbox.v7.evidence import PackageSpec, build_package

HERE = Path(__file__).resolve().parent
PACKAGE_ID = "v7-exp7b-agent"

CLAIM = (
    "On a small instruction-tuned LLM tool-using agent (Qwen2.5-3B-Instruct, chosen "
    "by a pre-declared competence check), Glassbox's investigation blamed the large "
    "real cause in 4/4 cases, never blamed the inert change, recorded every tool "
    "execution including hidden framework retries, and its exact and sampled outcomes "
    "agreed (G1-G5 PASS, Hard Gate 8)."
)
SCOPE = (
    "Pre-registered (protocol 821333a, addenda 2eb6aac, 7ae8a08, 5d4ffcb). PASS in two "
    "Kaggle CPU runs; run 1's result files were lost and only its printed log "
    "survives. Run 2 matched every gate, attribution, observed value and p-value but "
    "was not reproduced bit-identically (13 exact probabilities differ in the 6th "
    "decimal); a pre-registered check attributed this to floating-point summation "
    "order on one machine, not to the exact original sessions. The measured change "
    "was mostly that the agent stopped sending the confirmation (P(0 emails) about "
    "0.31 to 0.97), not duplicates (about 0.005 to 0.016). The mid-sized cause "
    "framework_retry (about 0.34) was attributed in 2/4 cases. Fixed action menu, "
    "raw-text prompts without a chat template, factors chosen by the author, cause "
    "known by construction, single author, not independently reproduced. Traces are "
    "regenerable and not included."
)


def spec(root: Path = HERE) -> PackageSpec:
    """Build the package specification from the committed experiment files."""
    artifacts: Dict[str, List[Union[str, Path]]] = {
        "protocol": [root / "PROTOCOL.md"],
        "code": [root / "run.py", root / "explain_numeric.py"],
        "measurements": [root / "results" / "results.json", root / "RESULTS.md"],
        "run1": [
            root / "run1_kaggle" / "run_log_run1.txt",
            root / "run1_kaggle" / "notebook_run1.ipynb",
        ],
        "run2": [
            root / "run2_kaggle" / "run_log_run2.txt",
            root / "run2_kaggle" / "env_freeze.txt",
        ],
        "numeric_check": [
            root / "numeric_check" / "numeric_check.json",
            root / "numeric_check" / "numeric_check_log.txt",
        ],
    }
    return PackageSpec(
        claim=CLAIM,
        status="EXPERIMENTALLY_SUPPORTED",
        scope=SCOPE,
        artifacts=artifacts,
        provenance={
            "protocol_commit": "821333a",
            "code_commit": "b807af7",
            "run_code_commit": "2eb6aac",
            "addendum2_commit": "7ae8a08",
            "run2_results_commit": "80197c5",
            "addendum3_commits": "5d4ffcb, 38dba0d",
            "numeric_check_commit": "4bcf553",
            "writeup_commit": "222abd6",
            "assurance_row": "V3.8",
        },
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Package V7 Experiment 7b (LLM tool-using agent)"
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    pkg = build_package(args.out, PACKAGE_ID, spec())
    sys.stdout.write(f"wrote {pkg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
