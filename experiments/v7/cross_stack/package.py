#!/usr/bin/env python3
"""Package V7 Experiment 8 (cross-stack, Hard Gate 2) as a verifiable evidence bundle.

Usage:
    python3 experiments/v7/cross_stack/package.py --out evidence
    python -m glassbox.v7.evidence verify evidence/v7-exp8-cross-stack
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from glassbox.v7.evidence import PackageSpec, build_package

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PACKAGE_ID = "v7-exp8-cross-stack"
CONDITIONS = ("baseline", "baseline_repeat", "fault", "restored")

CLAIM = (
    "Traces written by independent instrumentation (OpenInference on the "
    "OpenTelemetry SDK) for a different framework (LlamaIndex), exported as OTLP JSON, "
    "were imported losslessly (32/32) into the common Glassbox representation, and the "
    "unchanged diff engine reached Experiment 1's conclusions on the same stale-index "
    "fault: localisation 4/4, specificity 4/4, recovery 8/8, determinism 8/8. Glassbox "
    "traces exported to OTLP JSON passed the official OTLP protobuf schema (32/32)."
)
SCOPE = (
    "Pre-registered (protocol 5a5d2da, addenda 7fcc028 including a disclosed "
    "toy-corpus code smoke test, code 226a4eb). Stack B is retrieval only (no LLM call), "
    "deterministic, one framework, one injected fault, pipeline and corpus written by "
    "the author, cause known by construction. The schema check uses "
    "opentelemetry-proto 1.45.1 and is not a test against a live OTLP collector. "
    "Single author, not independently reproduced."
)


def spec(root: Path = HERE) -> PackageSpec:
    """Build the package specification from the committed experiment files."""
    res = root / "results"
    artifacts: Dict[str, List[Union[str, Path]]] = {
        "protocol": [root / "PROTOCOL.md", root / "RUN.md"],
        "code": [
            root / "subject.py",
            root / "evaluate.py",
            REPO / "glassbox" / "v7" / "otlp.py",
        ],
        "measurements": [
            res / "results.json",
            res / "schema_check.json",
            res / "stack_b_env.json",
            root / "RESULTS.md",
        ],
    }
    for cond in CONDITIONS:
        artifacts[f"otlp_{cond}"] = sorted((res / "otlp" / cond).glob("*.otlp.json"))
        artifacts[f"imported_{cond}"] = sorted(
            (res / "imported" / cond).glob("*.trace.jsonl")
        )
    return PackageSpec(
        claim=CLAIM,
        status="EXPERIMENTALLY_SUPPORTED",
        scope=SCOPE,
        artifacts=artifacts,
        provenance={
            "protocol_commit": "5a5d2da",
            "addenda_commit": "7fcc028",
            "code_commit": "226a4eb",
            "results_commit": "3f99b2b",
            "writeup_commit": "42b4f38",
            "stack_b": "llama-index-core 0.14.19, "
            "openinference-instrumentation-llama-index 4.6.0, "
            "opentelemetry-sdk 1.45.1",
            "assurance_row": "V2.10",
            "related_assurance_row": "V1.2 (schema check)",
        },
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Package V7 Experiment 8 (cross-stack)"
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    pkg = build_package(args.out, PACKAGE_ID, spec())
    sys.stdout.write(f"wrote {pkg}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
