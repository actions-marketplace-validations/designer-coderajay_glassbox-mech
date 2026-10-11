#!/usr/bin/env python3
"""V7 Experiment 7: investigating an LLM tool-using agent (PROTOCOL.md, cc37722).

A booking agent chooses actions in a loop (at most 4 decisions) from
`` check_calendar`` / `` send_confirmation`` / `` finish``. Each choice is sampled from
softmax(log p(action | prompt) / T) under Qwen2.5-0.5B (Experiment 1's teacher-forced
scorer). The email API times out with probability 0.5 but always delivers. Framework
v2 auto re-sends on timeout. Every decision and every tool execution, including
framework retries, is recorded as a Glassbox span.

Because action probabilities are deterministic per prompt, the exact outcome
distribution (0 / 1 / 2+ emails) of any configuration is computed by enumerating the
run tree (:func:`exact_distribution`); the gates G1–G5 are defined against it.

Usage (owner's machine):
    python3 experiments/v7/agent/run.py --out experiments/v7/agent/results
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import math
import random
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from glassbox.v7.groupdiff import group_diff
from glassbox.v7.intervene import Factor, InterventionSettings, run_interventions
from glassbox.v7.trace import Recorder, read_trace

HERE = Path(__file__).resolve().parent
EXP1 = HERE.parent / "rag_fault" / "run.py"
MODEL = "Qwen/Qwen2.5-0.5B"
TEMPERATURE = 1.0
MAX_DECISIONS = 4
P_TIMEOUT = 0.5
N_PER_CELL = 30
N_PERM = 999
ALPHA = 0.05
LARGE = 0.5
G2_MAX = 1
G4_TOL = 1e-6
G5_ALPHA = 0.01
G5_MIN_CASES = 3
ACTIONS = (" check_calendar", " send_confirmation", " finish")
OUTCOMES = ("0", "1", "2+")
CASES: Dict[str, Tuple[str, str]] = {
    "c1": ("Dana", "Tuesday"),
    "c2": ("Ravi", "Thursday"),
    "c3": ("Mei", "Monday"),
    "c4": ("Tomas", "Friday"),
}
SYSTEM_PROMPTS = {
    "strict": "You are a booking assistant. Check the calendar once, send exactly "
    "one confirmation, then finish.",
    "helpful": "You are a helpful booking assistant.",
}
FACTORS = [
    Factor("system_prompt", base="strict", candidate="helpful"),
    Factor("tool_format", base="text", candidate="json"),
    Factor("framework_retry", base="v1", candidate="v2"),
    Factor("log_level", base="info", candidate="debug"),
]
BASE_CONFIG: Dict[str, Any] = {f.name: f.base for f in FACTORS}

Scorer = Callable[[str, str], float]
Dist = Dict[str, float]


# --- the agent --------------------------------------------------------------------


def build_prompt(system_key: str, person: str, day: str, lines: Sequence[str]) -> str:
    """System prompt, task, one line per previous step, then ``Next action:``."""
    task = f"Task: Book a meeting with {person} on {day}."
    return "\n".join([SYSTEM_PROMPTS[system_key], task, *lines, "Next action:"])


def calendar_output(fmt: str, day: str) -> str:
    """``check_calendar`` output in the text (base) or JSON (candidate) format."""
    return f"{day}: available" if fmt == "text" else json.dumps({"day": day, "free": 1})


def outcome_label(emails: int) -> str:
    """Number of emails sent as ``0`` / ``1`` / ``2+``."""
    return "0" if emails == 0 else ("1" if emails == 1 else "2+")


class ActionPolicy:
    """Deterministic action probabilities per prompt, scored once and cached."""

    def __init__(self, scorer: Scorer) -> None:
        self.scorer = scorer
        self._scores: Dict[str, Tuple[float, ...]] = {}

    def scores(self, prompt: str) -> Tuple[float, ...]:
        """log p(action | prompt) for each action."""
        if prompt not in self._scores:
            self._scores[prompt] = tuple(self.scorer(prompt, a) for a in ACTIONS)
        return self._scores[prompt]

    def probs(self, prompt: str) -> Tuple[float, ...]:
        """softmax(scores / T), numerically stable."""
        s = [x / TEMPERATURE for x in self.scores(prompt)]
        top = max(s)
        e = [math.exp(x - top) for x in s]
        z = sum(e)
        return tuple(x / z for x in e)

    def recheck(self) -> float:
        """Re-score every cached prompt; max absolute difference (G4)."""
        diffs = [
            abs(self.scorer(p, a) - s)
            for p, sc in self._scores.items()
            for a, s in zip(ACTIONS, sc)
        ]
        return max(diffs) if diffs else 0.0


@dataclass
class RunRecord:
    """Ordered events of one agent run and the true number of emails delivered."""

    events: List[Tuple[Any, ...]] = field(default_factory=list)
    emails: int = 0

    @property
    def outcome(self) -> str:
        """``0`` / ``1`` / ``2+``."""
        return outcome_label(self.emails)


def _pick(probs: Sequence[float], u: float) -> str:
    acc = 0.0
    for action, p in zip(ACTIONS, probs):
        acc += p
        if u < acc:
            return action
    return ACTIONS[-1]


def _send(cfg: Dict[str, Any], rec: RunRecord, rng: random.Random) -> str:
    rec.emails += 1  # delivered, whatever the acknowledgement says
    if rng.random() >= P_TIMEOUT:
        rec.events.append(("tool", "send_confirmation", "ok", False))
        return "ok"
    rec.events.append(("tool", "send_confirmation", "timeout", False))
    if cfg["framework_retry"] == "v1":
        return "error: timeout"
    rec.emails += 1  # framework v2 re-sends once; its own timeout is ignored
    rec.events.append(("tool", "send_confirmation", "ok", True))
    return "ok"


def simulate(
    policy: ActionPolicy, cfg: Dict[str, Any], person: str, day: str, rng: random.Random
) -> RunRecord:
    """One sampled agent run."""
    rec, lines = RunRecord(), []
    for i in range(1, MAX_DECISIONS + 1):
        prompt = build_prompt(cfg["system_prompt"], person, day, lines)
        action = _pick(policy.probs(prompt), rng.random())
        rec.events.append(("decision", prompt, action))
        if action == " finish":
            break
        if action == " check_calendar":
            out = calendar_output(cfg["tool_format"], day)
            rec.events.append(("tool", "check_calendar", "ok", False))
        else:
            out = _send(cfg, rec, rng)
        lines.append(f"Step {i}: {action.strip()} -> {out}")
    return rec


def exact_distribution(
    policy: ActionPolicy, cfg: Dict[str, Any], person: str, day: str
) -> Dist:
    """Exact outcome distribution by enumerating every decision path and timeout."""
    acc: Dist = {k: 0.0 for k in OUTCOMES}

    def walk(lines: List[str], emails: int, i: int, mass: float) -> None:
        if i > MAX_DECISIONS:
            acc[outcome_label(emails)] += mass
            return
        prompt = build_prompt(cfg["system_prompt"], person, day, lines)
        for action, pa in zip(ACTIONS, policy.probs(prompt)):
            m = mass * pa
            if m == 0.0:
                continue
            step = f"Step {i}: {action.strip()} -> "
            if action == " finish":
                acc[outcome_label(emails)] += m
            elif action == " check_calendar":
                walk(
                    lines + [step + calendar_output(cfg["tool_format"], day)],
                    emails,
                    i + 1,
                    m,
                )
            else:
                walk(lines + [step + "ok"], emails + 1, i + 1, m * (1 - P_TIMEOUT))
                if cfg["framework_retry"] == "v1":
                    walk(
                        lines + [step + "error: timeout"],
                        emails + 1,
                        i + 1,
                        m * P_TIMEOUT,
                    )
                else:
                    walk(lines + [step + "ok"], emails + 2, i + 1, m * P_TIMEOUT)

    walk([], 0, 1, 1.0)
    return acc


def tvd(a: Dist, b: Dist) -> float:
    """Total-variation distance between two outcome distributions."""
    return 0.5 * sum(abs(a[k] - b[k]) for k in OUTCOMES)


# --- tracing ----------------------------------------------------------------------


class AgentRunner:
    """Runner for :func:`run_interventions`: one recorded agent run per call."""

    def __init__(self, policy: ActionPolicy, person: str, day: str) -> None:
        self.policy, self.person, self.day = policy, person, day

    def __call__(
        self, config: Dict[str, Any], seed: int, out: Path, run_id: str
    ) -> Path:
        cfg = {**BASE_CONFIG, **config}
        rec = simulate(self.policy, cfg, self.person, self.day, random.Random(seed))
        trace = Recorder(out_dir=out, run_id=run_id)
        trace.environment["glassbox.env.log_level"] = str(cfg["log_level"])
        with trace:
            for ev in rec.events:
                if ev[0] == "decision":
                    msgs = [
                        {"role": "user", "parts": [{"type": "text", "content": ev[1]}]}
                    ]
                    with trace.span(
                        "chat",
                        "agent-policy",
                        attributes={"glassbox.agent.action": ev[2].strip()},
                        content={"gen_ai.input.messages": msgs},
                    ):
                        pass
                else:
                    attrs = {"gen_ai.tool.name": ev[1], "glassbox.tool.result": ev[2]}
                    if ev[3]:
                        attrs["glassbox.tool.framework_retry"] = True
                    with trace.span(
                        "execute_tool", ev[1], kind="INTERNAL", attributes=attrs
                    ):
                        pass
            with trace.step(
                "outcome", attributes={"glassbox.agent.emails_sent": rec.emails}
            ):
                pass
        return Path(trace.path)


def trace_email_counts(path: Path) -> Tuple[int, int]:
    """(number of send_confirmation tool spans, emails_sent recorded by the run)."""
    spans, _ = read_trace(path)
    sends = sum(
        1
        for s in spans
        if s["attributes"].get("gen_ai.operation.name") == "execute_tool"
        and s["attributes"].get("gen_ai.tool.name") == "send_confirmation"
    )
    emails = [
        s["attributes"]["glassbox.agent.emails_sent"]
        for s in spans
        if "glassbox.agent.emails_sent" in s["attributes"]
    ]
    return sends, int(emails[0])


def outcome_from_trace(path: Path) -> str:
    """Outcome read back from the trace."""
    return outcome_label(trace_email_counts(path)[1])


# --- statistics (G5) --------------------------------------------------------------


def _multinomial_exact_p(counts: List[int], probs: List[float]) -> float:
    n = sum(counts)

    def logpmf(x: Sequence[int]) -> float:
        return math.lgamma(n + 1) + sum(
            xi * math.log(p) - math.lgamma(xi + 1) for xi, p in zip(x, probs)
        )

    obs = logpmf(counts)
    total = 0.0
    for head in itertools.product(range(n + 1), repeat=len(probs) - 1):
        if sum(head) <= n:
            x = [*head, n - sum(head)]
            lp = logpmf(x)
            if lp <= obs + 1e-9:
                total += math.exp(lp)
    return min(1.0, total)


def gof_pvalue(observed: Dict[str, int], exact: Dist) -> float:
    """Chi-square GOF (categories merged to expected >= 5), else exact multinomial."""
    n = sum(observed.values())
    if any(observed.get(k, 0) > 0 and exact[k] == 0.0 for k in OUTCOMES):
        return 0.0
    cats = [k for k in OUTCOMES if exact[k] > 0.0]
    groups = sorted(([k] for k in cats), key=lambda g: sum(exact[k] for k in g))
    while len(groups) > 1 and n * sum(exact[k] for k in groups[0]) < 5:
        merged = groups[0] + groups[1]
        groups = sorted([merged, *groups[2:]], key=lambda g: sum(exact[k] for k in g))
    if len(groups) == 1:
        if len(cats) == 1:
            return 1.0
        return _multinomial_exact_p(
            [observed.get(k, 0) for k in cats], [exact[k] for k in cats]
        )
    stat = 0.0
    for g in groups:
        e = n * sum(exact[k] for k in g)
        o = sum(observed.get(k, 0) for k in g)
        stat += (o - e) ** 2 / e
    df = len(groups) - 1
    return math.erfc(math.sqrt(stat / 2)) if df == 1 else math.exp(-stat / 2)


# --- investigation ----------------------------------------------------------------


def _ground_truth(policy: ActionPolicy, person: str, day: str) -> Dict[str, Any]:
    base = exact_distribution(policy, dict(BASE_CONFIG), person, day)
    cand = exact_distribution(
        policy, {f.name: f.candidate for f in FACTORS}, person, day
    )
    pairs = {}
    for f in FACTORS:
        only = exact_distribution(
            policy, {**BASE_CONFIG, f.name: f.candidate}, person, day
        )
        t = tvd(base, only)
        cls = "zero" if f.name == "log_level" else ("large" if t >= LARGE else "small")
        pairs[f.name] = {"true_tvd": round(t, 6), "class": cls}
    return {"exact_baseline": base, "exact_candidate": cand, "pairs": pairs}


def investigate_case(policy: ActionPolicy, case: str, tmp: Path) -> Dict[str, Any]:
    """Ground truth, interventions, fidelity, GOF and group diff for one case."""
    person, day = CASES[case]
    truth = _ground_truth(policy, person, day)
    settings = InterventionSettings(N_PER_CELL, N_PERM, ALPHA, f"exp7:{case}")
    runner = AgentRunner(policy, person, day)
    report = run_interventions(
        FACTORS, runner, outcome_from_trace, tmp / case, settings
    )
    all_paths = {p for ps in report.paths.values() for p in ps}
    fidelity = all(a == b for a, b in (trace_email_counts(Path(p)) for p in all_paths))
    gd = group_diff(
        report.paths["baseline"], report.paths["candidate"], N_PERM, ALPHA, 0
    )
    first = gd.first_beyond_noise
    suff = {t.factor: t for t in report.sufficiency}
    pairs = {
        f: {
            **truth["pairs"][f],
            "observed_tvd": round(suff[f].tvd, 6),
            "p_value": suff[f].p_value,
            "attributed": suff[f].significant,
        }
        for f in truth["pairs"]
    }
    return {
        "exact_baseline": truth["exact_baseline"],
        "exact_candidate": truth["exact_candidate"],
        "pairs": pairs,
        "necessity_significant": [t.factor for t in report.necessity if t.significant],
        "cell_counts": {k: v.counts for k, v in report.cells.items()},
        "fidelity_ok": fidelity,
        "runs_checked": len(all_paths),
        "gof_p": gof_pvalue(report.cells["baseline"].counts, truth["exact_baseline"]),
        "group_diff": {
            "first_beyond_noise": [first.step, first.field] if first else None,
            "flagged_steps": sorted({f.step for f in gd.significant}),
        },
    }


def criteria(per_case: Dict[str, Dict[str, Any]], recheck: float) -> Dict[str, Any]:
    """G1–G5 per PROTOCOL.md §4."""
    pairs = [(c, f, p) for c, s in per_case.items() for f, p in s["pairs"].items()]
    large = [p for _, _, p in pairs if p["class"] == "large"]
    log_hits = sum(1 for _, f, p in pairs if f == "log_level" and p["attributed"])
    gof_ok = sum(1 for s in per_case.values() if s["gof_p"] >= G5_ALPHA)
    return {
        "G1_sensitivity": {
            "applicable": bool(large),
            "large_pairs": len(large),
            "attributed": sum(1 for p in large if p["attributed"]),
            "pass": bool(large) and all(p["attributed"] for p in large),
        },
        "G2_specificity": {
            "log_level_attributed": log_hits,
            "pass": log_hits <= G2_MAX,
        },
        "G3_trace_fidelity": {
            "cases_ok": sum(1 for s in per_case.values() if s["fidelity_ok"]),
            "pass": all(s["fidelity_ok"] for s in per_case.values()),
        },
        "G4_determinism": {"max_abs_diff": recheck, "pass": recheck <= G4_TOL},
        "G5_exact_vs_observed": {"cases_ok": gof_ok, "pass": gof_ok >= G5_MIN_CASES},
    }


def overall(crit: Dict[str, Any]) -> str:
    """INCONCLUSIVE without a large pair; else PASS iff G1–G5 all pass."""
    if not crit["G1_sensitivity"]["applicable"]:
        return "INCONCLUSIVE"
    return "PASS" if all(c["pass"] for c in crit.values()) else "FAIL"


def default_factory(name: str) -> Scorer:
    """Experiment 1's teacher-forced scorer for a TransformerLens model."""
    spec = importlib.util.spec_from_file_location("exp1_run_e7", EXP1)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    scorer: Scorer = module.GPT2Scorer(name)
    return scorer


def run(
    out: Path, factory: Callable[[str], Scorer] = default_factory
) -> Dict[str, Any]:
    """Investigate all cases; write ``results.json`` (never overwrites)."""
    out.mkdir(parents=True, exist_ok=True)
    target = out / "results.json"
    if target.exists():
        raise FileExistsError(f"{target} exists; results are never overwritten")
    policy = ActionPolicy(factory(MODEL))
    with tempfile.TemporaryDirectory() as tmp:
        per_case = {c: investigate_case(policy, c, Path(tmp)) for c in CASES}
    crit = criteria(per_case, policy.recheck())
    results = {
        "protocol": "experiments/v7/agent/PROTOCOL.md v1.0",
        "model": MODEL,
        "settings": {
            "n_per_cell": N_PER_CELL,
            "n_perm": N_PERM,
            "alpha": ALPHA,
            "temperature": TEMPERATURE,
            "max_decisions": MAX_DECISIONS,
            "p_timeout": P_TIMEOUT,
            "distinct_prompts_scored": len(policy._scores),
            "traces_committed": False,
        },
        "criteria": crit,
        "overall": overall(crit),
        "per_case": per_case,
    }
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(results, indent=1) + "\n")
    return results


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point; prints criteria, per-case truth vs attribution, overall."""
    parser = argparse.ArgumentParser(description="V7 Experiment 7 (agent)")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    res = run(args.out)
    for name, c in res["criteria"].items():
        tag = "PASS" if c["pass"] else "FAIL"
        sys.stdout.write(
            f"{name}: {tag} {json.dumps({k: v for k, v in c.items() if k != 'pass'})}\n"
        )
    for case, s in res["per_case"].items():
        exact = {k: round(v, 3) for k, v in s["exact_baseline"].items()}
        cand = {k: round(v, 3) for k, v in s["exact_candidate"].items()}
        sys.stdout.write(f"{case}: exact baseline {exact} -> candidate {cand}\n")
        for f, p in s["pairs"].items():
            sys.stdout.write(
                f"   {f}: {p['class']} true {p['true_tvd']} observed {p['observed_tvd']} "
                f"p {p['p_value']} attributed {p['attributed']}\n"
            )
    sys.stdout.write(f"EXPERIMENT 7 OVERALL: {res['overall']}\n")
    return 0 if res["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
