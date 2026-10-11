#!/usr/bin/env python3
"""V7 Experiment 7b: the LLM agent with a numbered menu and a competence ladder.

Protocol: ``PROTOCOL.md`` (committed in 821333a before this code).

Reuses Experiment 7 unchanged by import: the agent loop (:func:`simulate`), the exact
enumerator, tools, factors, gates G1–G5, GOF and trace-fidelity check. What 7b adds:

* :class:`MenuPolicy`: actions are chosen from a numbered menu by scoring one token
  per label (`` 1``/`` 2``/`` 3``, else ``1``/``2``/``3``), which removes the length bias
  diagnosed in Experiment 7 (``experiments/v7/agent/DIAGNOSIS_2026-10-11.md``);
* :func:`select_model`: the Qwen2.5-Instruct ladder (0.5B, 1.5B, 3B). The first model
  whose exact baseline P(exactly 1 email), averaged over the 4 cases, is >= 0.6 is
  used. Only baseline behaviour is examined before selection;
* :class:`MenuAgentRunner`: records the menu prompt the model actually saw (hashed) and
  the chosen label.

Usage:
    python3 experiments/v7/agent_b/run.py --out experiments/v7/agent_b/results
"""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import random
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from glassbox.v7.groupdiff import group_diff
from glassbox.v7.intervene import InterventionSettings, run_interventions
from glassbox.v7.trace import Recorder

HERE = Path(__file__).resolve().parent
EXP7 = HERE.parent / "agent" / "run.py"
LADDER = (
    "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-1.5B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct",
)
COMPETENCE_MIN = 0.6
SEED_PREFIX = "exp7b"
MENU = (
    "Actions:\n1. check_calendar\n2. send_confirmation\n3. finish\n"
    "Next action (1, 2 or 3):"
)
LABEL_SETS = ((" 1", " 2", " 3"), ("1", "2", "3"))

Scorer = Callable[[str, str], float]
_EXP7: Dict[str, ModuleType] = {}


def load_exp7() -> ModuleType:
    """Experiment 7's ``run.py``, loaded once per process."""
    if "m" not in _EXP7:
        spec = importlib.util.spec_from_file_location("exp7_run_for_7b", EXP7)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _EXP7["m"] = module
    return _EXP7["m"]


def menu_prompt(exp7_prompt: str) -> str:
    """Replace Experiment 7's final ``Next action:`` line with the numbered menu."""
    head, sep, _ = exp7_prompt.rpartition("Next action:")
    assert sep, "not an Experiment 7 prompt"
    return head + MENU


def choose_labels(model: Any) -> Optional[Tuple[str, ...]]:
    """First label set whose every label is exactly one token, else ``None``."""
    for labels in LABEL_SETS:
        if all(model.to_tokens(lab, prepend_bos=False).shape[1] == 1 for lab in labels):
            return labels
    return None


class MenuPolicy:
    """Drop-in for Experiment 7's ``ActionPolicy``: scores menu labels, one token each."""

    def __init__(self, scorer: Scorer, labels: Sequence[str]) -> None:
        self.scorer, self.labels = scorer, tuple(labels)
        self._scores: Dict[str, Tuple[float, ...]] = {}

    def scores(self, prompt: str) -> Tuple[float, ...]:
        """log p(label | menu prompt) per action, cached by the Experiment 7 prompt."""
        if prompt not in self._scores:
            menu = menu_prompt(prompt)
            self._scores[prompt] = tuple(self.scorer(menu, lab) for lab in self.labels)
        return self._scores[prompt]

    def probs(self, prompt: str) -> Tuple[float, ...]:
        """softmax(scores / T) with Experiment 7's temperature."""
        e7 = load_exp7()
        policy = e7.ActionPolicy(lambda p, a: 0.0)
        policy._scores[prompt] = self.scores(prompt)
        result: Tuple[float, ...] = policy.probs(prompt)
        return result

    def recheck(self) -> float:
        """Re-score every cached prompt; max absolute difference (G4)."""
        diffs = [
            abs(self.scorer(menu_prompt(p), lab) - s)
            for p, sc in self._scores.items()
            for lab, s in zip(self.labels, sc)
        ]
        return max(diffs) if diffs else 0.0


def competence(policy: MenuPolicy) -> float:
    """Mean over cases of the exact baseline P(exactly one email)."""
    e7 = load_exp7()
    vals = [
        e7.exact_distribution(policy, dict(e7.BASE_CONFIG), person, day)["1"]
        for person, day in e7.CASES.values()
    ]
    return sum(vals) / len(vals)


def select_model(
    factory: Callable[[str], Scorer],
) -> Tuple[Optional[Tuple[str, MenuPolicy]], List[Dict[str, Any]]]:
    """Walk the ladder; return (selected name and policy, per-model record)."""
    ladder: List[Dict[str, Any]] = []
    for name in LADDER:
        try:
            scorer = factory(name)
        except (
            Exception
        ) as exc:  # noqa: BLE001 - load failures are reported, not hidden
            ladder.append(
                {
                    "model": name,
                    "status": "NOT RUN",
                    "reason": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        labels = choose_labels(getattr(scorer, "model"))
        if labels is None:
            ladder.append(
                {
                    "model": name,
                    "status": "NOT RUN",
                    "reason": "no single-token label set",
                }
            )
            del scorer
            gc.collect()
            continue
        policy = MenuPolicy(scorer, labels)
        comp = competence(policy)
        ok = comp >= COMPETENCE_MIN
        ladder.append(
            {
                "model": name,
                "status": "SELECTED" if ok else "NOT COMPETENT",
                "labels": list(labels),
                "competence": round(comp, 6),
            }
        )
        if ok:
            return (name, policy), ladder
        del scorer, policy
        gc.collect()
    return None, ladder


class MenuAgentRunner:
    """Experiment 7's agent, recording the menu prompt and the chosen label."""

    def __init__(self, policy: MenuPolicy, person: str, day: str) -> None:
        self.policy, self.person, self.day = policy, person, day

    def __call__(
        self, config: Dict[str, Any], seed: int, out: Path, run_id: str
    ) -> Path:
        e7 = load_exp7()
        cfg = {**e7.BASE_CONFIG, **config}
        rec = e7.simulate(self.policy, cfg, self.person, self.day, random.Random(seed))
        label_of = dict(zip(e7.ACTIONS, self.policy.labels))
        trace = Recorder(out_dir=out, run_id=run_id)
        trace.environment["glassbox.env.log_level"] = str(cfg["log_level"])
        with trace:
            for ev in rec.events:
                if ev[0] == "decision":
                    content = menu_prompt(ev[1])
                    msgs = [
                        {
                            "role": "user",
                            "parts": [{"type": "text", "content": content}],
                        }
                    ]
                    attrs = {
                        "glassbox.agent.action": ev[2].strip(),
                        "glassbox.agent.action_label": label_of[ev[2]].strip(),
                    }
                    with trace.span(
                        "chat",
                        "agent-policy",
                        attributes=attrs,
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


def investigate_case(policy: MenuPolicy, case: str, tmp: Path) -> Dict[str, Any]:
    """Experiment 7's per-case investigation with the menu runner and 7b seeds."""
    e7 = load_exp7()
    person, day = e7.CASES[case]
    truth = e7._ground_truth(policy, person, day)
    settings = InterventionSettings(
        e7.N_PER_CELL, e7.N_PERM, e7.ALPHA, f"{SEED_PREFIX}:{case}"
    )
    report = run_interventions(
        e7.FACTORS,
        MenuAgentRunner(policy, person, day),
        e7.outcome_from_trace,
        tmp / case,
        settings,
    )
    paths = {p for ps in report.paths.values() for p in ps}
    fidelity = all(a == b for a, b in (e7.trace_email_counts(Path(p)) for p in paths))
    gd = group_diff(
        report.paths["baseline"], report.paths["candidate"], e7.N_PERM, e7.ALPHA, 0
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
        "runs_checked": len(paths),
        "gof_p": e7.gof_pvalue(
            report.cells["baseline"].counts, truth["exact_baseline"]
        ),
        "group_diff": {
            "first_beyond_noise": [first.step, first.field] if first else None,
            "flagged_steps": sorted({f.step for f in gd.significant}),
        },
    }


def run(out: Path, factory: Optional[Callable[[str], Scorer]] = None) -> Dict[str, Any]:
    """Select a model, investigate all cases, write ``results.json`` (never overwrites)."""
    e7 = load_exp7()
    out.mkdir(parents=True, exist_ok=True)
    target = out / "results.json"
    if target.exists():
        raise FileExistsError(f"{target} exists; results are never overwritten")
    selected, ladder = select_model(factory or e7.default_factory)
    per_case: Dict[str, Any] = {}
    crit: Dict[str, Any] = {}
    overall = "INCONCLUSIVE"
    if selected is not None:
        _, policy = selected
        with tempfile.TemporaryDirectory() as tmp:
            per_case = {c: investigate_case(policy, c, Path(tmp)) for c in e7.CASES}
        crit = e7.criteria(per_case, policy.recheck())
        overall = e7.overall(crit)
    results = {
        "protocol": "experiments/v7/agent_b/PROTOCOL.md v1.0",
        "ladder": ladder,
        "selected_model": selected[0] if selected else None,
        "settings": {
            "n_per_cell": e7.N_PER_CELL,
            "n_perm": e7.N_PERM,
            "alpha": e7.ALPHA,
            "p_timeout": e7.P_TIMEOUT,
            "max_decisions": e7.MAX_DECISIONS,
            "competence_min": COMPETENCE_MIN,
            "traces_committed": False,
        },
        "criteria": crit,
        "overall": overall,
        "per_case": per_case,
    }
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(results, indent=1) + "\n")
    return results


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="V7 Experiment 7b (agent, menu + ladder)"
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    res = run(args.out)
    for r in res["ladder"]:
        sys.stdout.write(f"ladder: {json.dumps(r)}\n")
    for name, c in res["criteria"].items():
        tag = "PASS" if c["pass"] else "FAIL"
        sys.stdout.write(
            f"{name}: {tag} {json.dumps({k: v for k, v in c.items() if k != 'pass'})}\n"
        )
    for case, s in res["per_case"].items():
        b = {k: round(v, 3) for k, v in s["exact_baseline"].items()}
        cnd = {k: round(v, 3) for k, v in s["exact_candidate"].items()}
        sys.stdout.write(f"{case}: exact baseline {b} -> candidate {cnd}\n")
        for f, p in s["pairs"].items():
            sys.stdout.write(
                f"   {f}: {p['class']} true {p['true_tvd']} observed "
                f"{p['observed_tvd']} p {p['p_value']} attributed {p['attributed']}\n"
            )
    sys.stdout.write(f"EXPERIMENT 7b OVERALL: {res['overall']}\n")
    return 0 if res["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
