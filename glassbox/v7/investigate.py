"""End-to-end investigation: where do runs differ, and which change matters?

An :class:`Incident` names a system that changed in several ways at once (the
*factors*), a set of test cases, a way to run one case under a configuration (a
*runner* per case) and the outcome that matters. :func:`investigate` then, per case:

1. **Where** — runs ``baseline`` and ``candidate`` repeatedly (as part of the
   intervention design) and compares them with the noise-aware group diff
   (:mod:`glassbox.v7.groupdiff`): which steps differ beyond run-to-run noise.
2. **Which** — one-factor-at-a-time interventions (:mod:`glassbox.v7.intervene`):
   which change, switched alone, changes the outcome.

The result renders as a plain-language report and exports as a verifiable evidence
package (:mod:`glassbox.v7.evidence`). An ad-hoc investigation is not pre-registered,
so its package status is ``PRELIMINARY``.

Evidence for the method itself lives in ``experiments/v7/`` (Experiments 3b, 4 and 5;
``ASSURANCE.md`` rows V2.9, V3.1, V3.3). Running this module produces a new
investigation, not new evidence for those claims.

Usage:
    python -m glassbox.v7.investigate demo --out DIR [--scorer toy|gpt2] [--runs N]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from glassbox.v7.evidence import PackageSpec, build_package
from glassbox.v7.groupdiff import group_diff
from glassbox.v7.intervene import (
    Factor,
    InterventionSettings,
    Outcome,
    Runner,
    run_interventions,
)

LIMITS = (
    "A difference beyond noise says where runs differ, not why.",
    "An attribution means switching that factor alone changed the outcome "
    "distribution for these inputs, values and outcome measure; it is not a general "
    "causal claim.",
    "'Not attributed' means no change was detected at this number of runs; small "
    "effects can be missed.",
    "Factors were chosen by whoever defined the incident; changes not listed as "
    "factors were not tested.",
)


@dataclass(frozen=True)
class Incident:
    """What changed, on which test cases, and how to run and score the system."""

    name: str
    description: str
    factors: Sequence[Factor]
    cases: Sequence[str]
    runner_for: Callable[[str], Runner]
    outcome: Outcome


@dataclass
class CaseFinding:
    """Diff and intervention results for one test case."""

    case: str
    first_beyond_noise: Optional[List[str]]
    flagged_steps: List[str]
    attributed: List[str]
    reverting_matters: List[str]
    outcome_counts: Dict[str, Dict[str, int]]
    intervention: Dict[str, Any]


@dataclass
class Investigation:
    """All case findings plus the settings used."""

    incident: Incident
    settings: InterventionSettings
    findings: List[CaseFinding]
    trace_dir: Path

    def factor_summary(self) -> Dict[str, Dict[str, List[str]]]:
        """Per factor: cases where switching alone / reverting alone mattered."""
        return {
            f.name: {
                "switching_alone_changed": [
                    c.case for c in self.findings if f.name in c.attributed
                ],
                "reverting_alone_changed": [
                    c.case for c in self.findings if f.name in c.reverting_matters
                ],
            }
            for f in self.incident.factors
        }

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable form (without callables)."""
        return {
            "incident": {
                "name": self.incident.name,
                "description": self.incident.description,
                "factors": [f.__dict__ for f in self.incident.factors],
                "cases": list(self.incident.cases),
            },
            "settings": self.settings.__dict__,
            "factor_summary": self.factor_summary(),
            "findings": [c.__dict__ for c in self.findings],
            "limits": list(LIMITS),
        }

    def report_markdown(self) -> str:
        """Plain-language report."""
        return render_report(self)

    def export_evidence(self, out_dir: Path, package_id: str) -> Path:
        """Write report, JSON and baseline/candidate traces as an evidence package."""
        out_dir = Path(out_dir)
        work = self.trace_dir.parent
        report, data = work / "REPORT.md", work / "investigation.json"
        report.write_text(self.report_markdown(), encoding="utf-8")
        data.write_text(json.dumps(self.to_dict(), indent=1) + "\n", encoding="utf-8")
        artifacts: Dict[str, List[Any]] = {"report": [report], "data": [data]}
        for c in self.findings:
            for cell in ("baseline", "candidate"):
                artifacts[f"traces_{c.case}_{cell}"] = [
                    Path(p) for p in c.intervention["paths"][cell]
                ]
        spec = PackageSpec(
            claim=_answer(self),
            status="PRELIMINARY",
            scope=" ".join(LIMITS),
            artifacts=artifacts,
            provenance={
                "incident": self.incident.name,
                "incident_description": self.incident.description,
                "settings": json.dumps(self.settings.__dict__, sort_keys=True),
                "method_evidence": "ASSURANCE.md rows V2.9, V3.1, V3.3",
            },
        )
        return build_package(out_dir, package_id, spec)


def _investigate_case(
    incident: Incident, case: str, out_dir: Path, settings: InterventionSettings
) -> CaseFinding:
    case_settings = InterventionSettings(
        settings.n_per_cell, settings.n_perm, settings.alpha, f"{settings.seed}:{case}"
    )
    report = run_interventions(
        incident.factors,
        incident.runner_for(case),
        incident.outcome,
        out_dir / case,
        case_settings,
    )
    gd = group_diff(
        report.paths["baseline"],
        report.paths["candidate"],
        settings.n_perm,
        settings.alpha,
        0,
    )
    first = gd.first_beyond_noise
    return CaseFinding(
        case=case,
        first_beyond_noise=[first.step, first.field] if first else None,
        flagged_steps=sorted({f.step for f in gd.significant}),
        attributed=report.attributed,
        reverting_matters=[
            t.factor for t in report.necessity if t.significant and t.factor
        ],
        outcome_counts={k: v.counts for k, v in report.cells.items()},
        intervention=report.to_dict(),
    )


def investigate(
    incident: Incident, out_dir: Path, settings: InterventionSettings
) -> Investigation:
    """Run the diff and the interventions for every case of ``incident``."""
    trace_dir = Path(out_dir) / "traces"
    findings = [
        _investigate_case(incident, case, trace_dir, settings)
        for case in incident.cases
    ]
    return Investigation(incident, settings, findings, trace_dir)


# --- report ---------------------------------------------------------------------


def _fmt_counts(counts: Dict[str, int]) -> str:
    total = sum(counts.values())
    return ", ".join(f"{k} {v}/{total}" for k, v in sorted(counts.items()))


def _answer(inv: Investigation) -> str:
    summary = inv.factor_summary()
    n = len(inv.findings)
    parts = []
    for name, s in summary.items():
        k = len(s["switching_alone_changed"])
        if k:
            parts.append(
                f"switching {name} alone changed the outcome in {k}/{n} test cases"
            )
    quiet = [name for name, s in summary.items() if not s["switching_alone_changed"]]
    text = (
        "; ".join(parts)
        if parts
        else "no single change was detected to change the outcome"
    )
    if quiet:
        text += f". No outcome change was detected from {', '.join(quiet)} alone"
    return (
        text[0].upper()
        + text[1:]
        + f" ({inv.settings.n_per_cell} runs per configuration)."
    )


def _differ_without_effect(inv: Investigation) -> List[str]:
    cases = [c.case for c in inv.findings if c.first_beyond_noise and not c.attributed]
    if not cases:
        return []
    return [
        f"In {len(cases)} case(s) ({', '.join(cases)}) the runs differed beyond noise, "
        "but no single change was detected to alter the outcome: something changed "
        "inside the run without changing the result.",
        "",
    ]


def _case_table(inv: Investigation) -> List[str]:
    lines = ["", "## Per test case", ""]
    lines += [
        "| Case | Before (baseline) | After (all changes) | Runs differ first at | "
        "Change(s) that matter |",
        "|---|---|---|---|---|",
    ]
    for c in inv.findings:
        where = (
            f"`{c.first_beyond_noise[0]}`"
            if c.first_beyond_noise
            else "nowhere beyond noise"
        )
        lines.append(
            f"| {c.case} | {_fmt_counts(c.outcome_counts['baseline'])} | "
            f"{_fmt_counts(c.outcome_counts['candidate'])} | {where} | "
            f"{', '.join(c.attributed) or 'none detected'} |"
        )
    return lines


def render_report(inv: Investigation) -> str:
    """Markdown report: answer, per-factor table, per-case detail, limits."""
    inc = inv.incident
    lines = [
        f"# Investigation: {inc.name}",
        "",
        inc.description,
        "",
        "## Answer",
        "",
        _answer(inv),
        "",
        *_differ_without_effect(inv),
        "## Changes investigated",
        "",
        "| Change | From | To | Switching it alone changed the outcome | "
        "Reverting it alone changed the outcome |",
        "|---|---|---|---|---|",
    ]
    summary = inv.factor_summary()
    for f in inc.factors:
        s = summary[f.name]
        lines.append(
            f"| `{f.name}` | {f.base} | {f.candidate} | "
            f"{', '.join(s['switching_alone_changed']) or '—'} | "
            f"{', '.join(s['reverting_alone_changed']) or '—'} |"
        )
    lines += _case_table(inv)
    lines += ["", "## What this does not show", ""]
    lines += [f"- {limit}" for limit in LIMITS]
    lines += [
        "",
        "## Verify",
        "",
        "`python -m glassbox.v7.evidence verify <evidence-package>`",
        "",
    ]
    return "\n".join(lines)


# --- CLI ------------------------------------------------------------------------


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI: ``demo`` runs the GPT-2 RAG incident and writes report + evidence."""
    parser = argparse.ArgumentParser(description="Glassbox V7 investigation")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="investigate the built-in RAG incident")
    demo.add_argument("--out", required=True, type=Path)
    demo.add_argument("--scorer", choices=("toy", "gpt2"), default="gpt2")
    demo.add_argument("--runs", type=int, default=30)
    demo.add_argument("--seed", default="demo")
    args = parser.parse_args(argv)
    from glassbox.v7 import demo_rag

    out: Path = args.out
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"{out} is not empty; choose a new directory")
    incident = demo_rag.make_incident(demo_rag.make_scorer(args.scorer))
    settings = InterventionSettings(args.runs, 999, 0.05, args.seed)
    inv = investigate(incident, out / "work", settings)
    pkg = inv.export_evidence(out / "evidence", "investigation")
    (out / "REPORT.md").write_text(inv.report_markdown(), encoding="utf-8")
    sys.stdout.write(inv.report_markdown())
    sys.stdout.write(f"\nEvidence package: {pkg}\n")
    if args.scorer == "toy":
        sys.stdout.write("NOTE: toy scorer, not a language model. Use --scorer gpt2.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
