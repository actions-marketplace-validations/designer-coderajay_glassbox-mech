#!/usr/bin/env python3
"""EXPLORATORY diagnosis of Experiment 7's INCONCLUSIVE result. Not evidence.

Experiment 7 (results committed in 0b80753) found that the agent almost never sends an
email: P(0 emails) is about 0.99 in every case. This script checks two post-hoc
hypotheses:

H1 (length bias): an action's score is the SUM of its tokens' log-probabilities, so
   multi-token actions such as `` send_confirmation`` are penalised against short ones
   such as `` finish``.
H2 (base model): Qwen2.5-0.5B is not instruction-tuned and does not follow the task.

It prints, for the baseline prompt at decision 1 and after a successful
check_calendar: the token count of each action, the summed and the per-token-mean
log-probabilities, and the resulting action probabilities.

Usage:
    python3 experiments/v7/agent/diagnose.py
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _load_run():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("exp7_run_diag", HERE / "run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _softmax(xs):  # type: ignore[no-untyped-def]
    top = max(xs)
    e = [math.exp(x - top) for x in xs]
    return [v / sum(e) for v in e]


def main() -> int:
    """Print the per-action diagnosis for two baseline prompts."""
    e7 = _load_run()
    scorer = e7.default_factory(e7.MODEL)
    model = scorer.model
    person, day = e7.CASES["c1"]
    prompts = {
        "decision 1": e7.build_prompt("strict", person, day, []),
        "after check_calendar": e7.build_prompt(
            "strict",
            person,
            day,
            [f"Step 1: check_calendar -> {e7.calendar_output('text', day)}"],
        ),
    }
    for label, prompt in prompts.items():
        sums, means = [], []
        sys.stdout.write(f"\n== {label}\n")
        for action in e7.ACTIONS:
            n_tok = model.to_tokens(action, prepend_bos=False).shape[1]
            s = scorer(prompt, action)
            sums.append(s)
            means.append(s / n_tok)
            sys.stdout.write(
                f"  {action!r:24} tokens={n_tok}  sum_logp={s:8.3f}  "
                f"mean_logp={s / n_tok:8.3f}\n"
            )
        p_sum = ", ".join(
            f"{a.strip()} {p:.3f}" for a, p in zip(e7.ACTIONS, _softmax(sums))
        )
        p_mean = ", ".join(
            f"{a.strip()} {p:.3f}" for a, p in zip(e7.ACTIONS, _softmax(means))
        )
        sys.stdout.write(
            f"  P(action) with summed log-probs (what Exp 7 used): {p_sum}\n"
        )
        sys.stdout.write(
            f"  P(action) with per-token mean (diagnostic only):    {p_mean}\n"
        )
    sys.stdout.write("\nEXPLORATORY: post-hoc diagnosis, not evidence.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
