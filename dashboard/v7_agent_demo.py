# SPDX-License-Identifier: BUSL-1.1
# Copyright (C) 2026 Ajay Pravin Mahale <mahale.ajay01@gmail.com>
# Licensed under the Business Source License 1.1 (see LICENSE-COMMERCIAL).
# Free for non-production use and for production use inside your own organisation.
# Offering it as a commercial service or product to third parties needs a license.
"""Agent-trajectory investigation demo for the HuggingFace Space.

A *simulated* tool-using booking agent (no language model): at each step it picks an
action (check the calendar, send the confirmation email, finish) with probabilities
set by its configuration, and the email tool sometimes times out. This is the same
agent family as V7 Experiment 10 (``experiments/v7/benchmark/families.py``, family S).

Because the agent is simulated, the true effect of every change is known exactly, so
the page can show Glassbox's answer next to the ground truth. The investigation itself
(``glassbox.v7.intervene.run_interventions`` on traced runs) is the same one you would
run on a real agent. Gradio is passed in by the caller, so this module is testable
without it.
"""

from __future__ import annotations

import html
import json
import random
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from glassbox.v7.diff import diff_traces
from glassbox.v7.intervene import Factor, InterventionSettings, run_interventions
from glassbox.v7.trace import Recorder, read_trace

MAX_DECISIONS = 4
TIMEOUT_P = 0.7  # the email tool times out on 70% of calls this week
RESEND_AFTER_TIMEOUT = 0.4
SEED = "space-agent-demo"
TMP_PREFIX = "glassbox_agent_"
STALE_AFTER_S = 3600

BASE: Dict[str, Any] = {
    "check_weight": 0.95,
    "resend_bias": 0.02,
    "framework_retry": "v1",
    "log_level": "info",
}

#: UI label -> (factor name, candidate value).
CHANGES: Dict[str, Tuple[str, Any]] = {
    "Upgraded the agent framework (v2 silently retries timed-out tool calls)": (
        "framework_retry",
        "v2",
    ),
    "Edited the system prompt (agent now tends to re-send after a success)": (
        "resend_bias",
        0.6,
    ),
    "Edited the planner (agent checks the calendar less often)": (
        "check_weight",
        0.2,
    ),
    "Raised the log level (info → debug)": ("log_level", "debug"),
}

INTRO = """
**An agent changed its behaviour. Which change caused it?** *Research preview,
simulated agent.*

A booking assistant checks a calendar and sends one confirmation email per booking
through a tool. This week several things changed and customers report **duplicate
or missing emails**. Glassbox records every run as a trace (each decision and tool
call), compares many runs before and after, and re-runs with **one change at a time**.

The agent here is **simulated** (no language model), so the true effect of every
change is known and shown next to Glassbox's answer. The investigation method is
the one you would run on a real agent.
"""

Dist = Dict[str, float]


def _cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    return {**BASE, **config}


def _weights(state: str, cfg: Dict[str, Any]) -> Dict[str, float]:
    if state == "start":
        w = {"check": cfg["check_weight"], "send": 0.03, "finish": 0.02}
    elif state == "checked":
        w = {"check": 0.02, "send": 0.96, "finish": 0.02}
    elif state == "timeout":
        w = {"send": RESEND_AFTER_TIMEOUT, "finish": 1.0 - RESEND_AFTER_TIMEOUT}
    else:
        w = {"send": cfg["resend_bias"], "finish": 1.0 - cfg["resend_bias"]}
    total = sum(w.values())
    return {a: v / total for a, v in w.items()}


def _label(emails: int) -> str:
    return "2+" if emails >= 2 else str(emails)


def exact(config: Dict[str, Any]) -> Dist:
    """Exact distribution of emails sent (``0`` / ``1`` / ``2+``)."""
    cfg = _cfg(config)
    v2 = cfg["framework_retry"] == "v2"
    out = {"0": 0.0, "1": 0.0, "2+": 0.0}

    def rec(state: str, depth: int, emails: int, p: float) -> None:
        if depth == MAX_DECISIONS:
            out[_label(emails)] += p
            return
        for action, pa in _weights(state, cfg).items():
            if action == "finish":
                out[_label(emails)] += p * pa
            elif action == "check":
                rec("checked", depth + 1, emails, p * pa)
            else:
                rec("ok", depth + 1, emails + 1, p * pa * (1 - TIMEOUT_P))
                if v2:
                    rec("ok", depth + 1, emails + 2, p * pa * TIMEOUT_P)
                else:
                    rec("timeout", depth + 1, emails + 1, p * pa * TIMEOUT_P)

    rec("start", 0, 0, 1.0)
    return out


def tvd(a: Dist, b: Dist) -> float:
    """Total-variation distance between two distributions."""
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def simulate(
    config: Dict[str, Any], rng: random.Random
) -> Tuple[List[Tuple[Any, ...]], str]:
    """One episode: the event list and the outcome label."""
    cfg = _cfg(config)
    state, emails, events = "start", 0, []
    for _ in range(MAX_DECISIONS):
        r, acc, action = rng.random(), 0.0, "finish"
        for a, pa in _weights(state, cfg).items():
            acc += pa
            if r < acc:
                action = a
                break
        events.append(("decision", state, action))
        if action == "finish":
            break
        if action == "check":
            events.append(("tool", "check_calendar", "free", False))
            state = "checked"
            continue
        emails += 1
        timeout = rng.random() < TIMEOUT_P
        retry = timeout and cfg["framework_retry"] == "v2"
        events.append(
            ("tool", "send_confirmation", "timeout" if timeout else "ok", retry)
        )
        if retry:
            emails += 1
        state = "timeout" if timeout and not retry else "ok"
    return events, _label(emails)


def runner(config: Dict[str, Any], seed: int, out: Path, run_id: str) -> Path:
    """Glassbox-traced run of the simulated agent."""
    cfg = _cfg(config)
    events, label = simulate(cfg, random.Random(seed))
    rec = Recorder(out_dir=out, run_id=run_id)
    rec.environment["glassbox.env.log_level"] = str(cfg["log_level"])
    with rec:
        for ev in events:
            if ev[0] == "decision":
                attrs = {"glassbox.agent.state": ev[1], "glassbox.agent.action": ev[2]}
                with rec.span("chat", "agent-policy", attributes=attrs):
                    pass
                continue
            attrs = {"gen_ai.tool.name": ev[1], "glassbox.tool.result": ev[2]}
            if ev[3]:
                attrs["glassbox.tool.framework_retry"] = True
            with rec.span("execute_tool", ev[1], kind="INTERNAL", attributes=attrs):
                pass
        with rec.step("outcome", attributes={"glassbox.agent.emails": label}):
            pass
    return Path(rec.path)


def outcome(path: Path) -> str:
    """Emails sent in a traced run."""
    spans, _ = read_trace(path)
    step = [s for s in spans if s["attributes"].get("glassbox.step.kind") == "outcome"]
    return str(step[0]["attributes"]["glassbox.agent.emails"])


def trajectory(path: Path) -> List[str]:
    """Human-readable steps of one traced run."""
    spans, _ = read_trace(path)
    rows = []
    for s in spans:
        a = s["attributes"]
        if "glassbox.agent.action" in a:
            rows.append(
                f"decide: {a['glassbox.agent.action']} (state {a['glassbox.agent.state']})"
            )
        elif "gen_ai.tool.name" in a:
            extra = (
                " + framework retry" if a.get("glassbox.tool.framework_retry") else ""
            )
            rows.append(
                f"tool {a['gen_ai.tool.name']}: {a['glassbox.tool.result']}{extra}"
            )
        elif "glassbox.agent.emails" in a:
            rows.append(f"emails sent: {a['glassbox.agent.emails']}")
    return rows


def cleanup_stale(root: Path, max_age_s: float = STALE_AFTER_S) -> int:
    """Delete earlier demo folders in ``root`` older than ``max_age_s``."""
    removed, cutoff = 0, time.time() - max_age_s
    for path in root.glob(f"{TMP_PREFIX}*"):
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
        except OSError:
            continue
    return removed


def _fmt(d: Dist) -> str:
    return " · ".join(
        f"{k} email{'s' if k != '1' else ''}: {d.get(k, 0.0):.0%}"
        for k in ("0", "1", "2+")
    )


def _first_divergent_pair(report: Any) -> Tuple[str, str]:
    """A baseline/candidate run pair whose outcomes differ, else the first pair."""
    base, cand = report.paths["baseline"], report.paths["candidate"]
    for a, b in zip(base, cand):
        if outcome(Path(a)) != outcome(Path(b)):
            return a, b
    return base[0], cand[0]


def trajectory_html(path_a: str, path_b: str) -> str:
    """Side-by-side trajectories with the first divergent step reported."""
    first = diff_traces(path_a, path_b).first_divergence
    cols = []
    for title, p in (("Before the changes", path_a), ("After the changes", path_b)):
        items = "".join(f"<li>{html.escape(r)}</li>" for r in trajectory(Path(p)))
        cols.append(
            f'<div class="gb-panel"><div class="gb-panel-title">{title}</div><ol class="gb-traj">{items}</ol></div>'
        )
    where = (
        f"First divergence at step {first.step_a if first.step_a is not None else '–'} → "
        f"{first.step_b if first.step_b is not None else '–'}."
        if first
        else "These two runs did not diverge."
    )
    return (
        '<div class="gb-panel"><div class="gb-panel-title">One trajectory pair'
        f'<span class="gb-panel-hint">{html.escape(where)} Single runs are noisy; the '
        "verdict above comes from all runs.</span></div>"
        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">{"".join(cols)}</div></div>'
    )


def run_agent_investigation(
    selected: Sequence[str], runs: int, workdir: Optional[Path] = None
) -> Tuple[str, str, Optional[str]]:
    """Return ``(report_markdown, trajectory_html, json_path)``; never raises on bad input."""
    chosen = [CHANGES[s] for s in selected if s in CHANGES]
    if not chosen:
        return "Select at least one change.", "", None
    runs = int(runs)
    if not 10 <= runs <= 200:
        return "Runs per configuration must be between 10 and 200.", "", None
    if workdir is None:
        cleanup_stale(Path(tempfile.gettempdir()))
    base_dir = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix=TMP_PREFIX))
    factors = [Factor(name, BASE[name], cand) for name, cand in chosen]
    settings = InterventionSettings(runs, 999, 0.05, SEED)
    report = run_interventions(factors, runner, outcome, base_dir / "work", settings)

    base_cfg = {f.name: f.base for f in factors}
    d_base = exact(base_cfg)
    d_cand = exact({f.name: f.candidate for f in factors})
    rows = []
    for f, t in zip(factors, report.sufficiency):
        true = tvd(d_base, exact({**base_cfg, f.name: f.candidate}))
        verdict = "**changed the outcome**" if t.significant else "no detectable change"
        rows.append(
            f"| `{f.name}` | {verdict} | {t.tvd:.2f} | {t.p_value:.3f} | {true:.2f} |"
        )
    blamed = ", ".join(f"`{n}`" for n in report.attributed) or "none"
    md = "\n".join(
        [
            "### Result",
            f"**Glassbox attributes the change to:** {blamed}.",
            "",
            f"- Before ({runs} runs): {_fmt(_counts(report, 'baseline'))}",
            f"- After ({runs} runs): {_fmt(_counts(report, 'candidate'))}",
            f"- Overall change detected: **{'yes' if report.total.significant else 'no'}** "
            f"(TVD {report.total.tvd:.2f}, p {report.total.p_value:.3f})",
            "",
            "| Change | Switched on alone | Measured TVD | p (Holm) | True effect* |",
            "|---|---|---|---|---|",
            *rows,
            "",
            f"*True effect is the exact change in the outcome distribution, computable only "
            f"because this agent is simulated. Exact before: {_fmt(d_base)}; after: {_fmt(d_cand)}. "
            "Small true effects can go undetected at this number of runs; that is a "
            "real limit of the method, measured in V7 Experiment 10.*",
        ]
    )
    pair = _first_divergent_pair(report)
    out = base_dir / "agent_investigation.json"
    out.write_text(
        json.dumps(report.to_dict(), indent=2, default=str), encoding="utf-8"
    )
    return md, trajectory_html(*pair), str(out)


def _counts(report: Any, cell: str) -> Dist:
    counts = report.cells[cell].counts
    n = sum(counts.values()) or 1
    return {k: v / n for k, v in counts.items()}


def build_tab(gr: Any, **click_kwargs: Any) -> None:
    """Add the agent investigation UI inside the caller's ``gr.Blocks`` / ``gr.Tab``."""
    gr.Markdown(INTRO)
    labels = list(CHANGES)
    with gr.Row(equal_height=False):
        with gr.Column(scale=4, min_width=300):
            changes = gr.CheckboxGroup(
                choices=labels,
                value=labels[:2] + labels[3:],
                label="What changed this week?",
            )
            runs = gr.Slider(
                minimum=20,
                maximum=200,
                value=100,
                step=10,
                label="Runs per configuration",
                info="No language model, so even 200 runs take only seconds.",
            )
            button = gr.Button("Investigate the agent", variant="primary")
            evidence = gr.File(label="Full result (JSON)")
        with gr.Column(scale=7, min_width=360):
            report = gr.Markdown(
                "*Pick which changes happened and press **Investigate the agent**.*"
            )
            traj = gr.HTML()
    button.click(
        fn=run_agent_investigation,
        inputs=[changes, runs],
        outputs=[report, traj, evidence],
        **click_kwargs,
    )
