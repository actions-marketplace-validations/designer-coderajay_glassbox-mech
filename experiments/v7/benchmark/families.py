"""The two incident families of V7 Experiment 10 (PROTOCOL.md §1, Addendum 1 items 4–5).

* Family R: GPT-2 small RAG (Experiment 5's pipeline plus ``top_k`` and ``preamble``).
* Family S: a synthetic tool-using agent whose action probabilities come from the
  configuration (no language model), with an exact enumerator.

Each family provides a Glassbox-traced runner, an outcome reader and an exact outcome
distribution for any configuration.
"""

from __future__ import annotations

import importlib.util
import math
import random
import sys
from collections import Counter
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Sequence, Tuple

from glassbox.v7.demo_rag import (
    DOCUMENTS,
    QUESTIONS,
    STALE_DROPPED,
    STOPWORDS,
    build_prompt,
    p_correct,
)
from glassbox.v7.trace import Recorder, read_trace

HERE = Path(__file__).resolve().parent


def _sibling(name: str) -> ModuleType:
    key = f"exp10_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


_GEN = _sibling("generate")
R_BASE: Dict[str, Any] = dict(_GEN.R_BASE)
S_BASE: Dict[str, Any] = dict(_GEN.S_BASE)
PREAMBLE = "Answer with one word.\n"
MAX_DECISIONS = 4
S_ITEMS: Dict[str, Tuple[float, float]] = {
    "c1": (0.5, 0.5),
    "c2": (0.3, 0.6),
    "c3": (0.7, 0.4),
    "c4": (0.4, 0.3),
}
Scorer = Callable[[str, str], float]
Dist = Dict[str, float]


def tvd(a: Dist, b: Dist) -> float:
    """Total-variation distance between two exact distributions."""
    keys = set(a) | set(b)
    return 0.5 * sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)


# --- Family R ---------------------------------------------------------------------


def _tokens(text: str) -> List[str]:
    import re

    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


def retrieve(question: str, index: str, top_k: int) -> List[Tuple[str, float]]:
    """Experiment 5's bag-of-words cosine retrieval with a configurable ``top_k``."""
    q = Counter(_tokens(question))
    hits = []
    for doc_id, text in DOCUMENTS.items():
        if index == "stale" and doc_id in STALE_DROPPED:
            continue
        d = Counter(_tokens(text))
        dot = sum(q[t] * d[t] for t in q)
        norm = math.sqrt(sum(v * v for v in q.values())) * math.sqrt(
            sum(v * v for v in d.values())
        )
        hits.append((doc_id, round(dot / norm, 6) if norm else 0.0))
    hits.sort(key=lambda x: (-x[1], x[0]))
    return hits[: int(top_k)]


def _r_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    return {**R_BASE, **config}


def r_prompt(config: Dict[str, Any], qid: str) -> str:
    """The prompt GPT-2 sees for question ``qid`` under ``config``."""
    cfg = _r_cfg(config)
    question = QUESTIONS[qid][0]
    hits = retrieve(question, cfg["index"], cfg["top_k"])
    prompt = build_prompt(cfg["template"], [DOCUMENTS[d] for d, _ in hits], question)
    return PREAMBLE + prompt if cfg["preamble"] == "one_word" else prompt


class Margins:
    """Cached teacher-forced margin log p(correct) − log p(distractor)."""

    def __init__(self, scorer: Scorer) -> None:
        self.scorer = scorer
        self.cache: Dict[Tuple[str, str, str], float] = {}

    def __call__(self, prompt: str, correct: str, distractor: str) -> float:
        key = (prompt, correct, distractor)
        if key not in self.cache:
            self.cache[key] = self.scorer(prompt, correct) - self.scorer(
                prompt, distractor
            )
        return self.cache[key]


def r_p_correct(config: Dict[str, Any], qid: str, margins: Margins) -> float:
    """P(correct) = sigmoid(margin) for question ``qid`` under ``config``."""
    _, correct, distractor = QUESTIONS[qid]
    return p_correct(margins(r_prompt(config, qid), correct, distractor))


def r_exact(config: Dict[str, Any], qid: str, margins: Margins) -> Dist:
    """Exact two-outcome distribution."""
    p = r_p_correct(config, qid, margins)
    return {"correct": p, "wrong": 1.0 - p}


def r_runner(qid: str, margins: Margins) -> Callable[..., Path]:
    """Glassbox-traced runner for question ``qid``."""
    question = QUESTIONS[qid][0]

    def run(config: Dict[str, Any], seed: int, out: Path, run_id: str) -> Path:
        cfg = _r_cfg(config)
        hits = retrieve(question, cfg["index"], cfg["top_k"])
        prompt = r_prompt(cfg, qid)
        p = r_p_correct(cfg, qid, margins)
        label = "correct" if random.Random(seed).random() < p else "wrong"
        rec = Recorder(out_dir=out, run_id=run_id)
        rec.environment["glassbox.env.log_level"] = str(cfg["log_level"])
        rec.environment["glassbox.env.cache_mode"] = str(cfg["cache_mode"])
        with rec:
            with rec.span(
                "retrieval",
                "kb",
                attributes={"gen_ai.retrieval.top_k": int(cfg["top_k"])},
            ) as s:
                rec.add_content(
                    s,
                    {
                        "gen_ai.retrieval.query.text": question,
                        "gen_ai.retrieval.documents": [
                            {"id": d, "score": x} for d, x in hits
                        ],
                    },
                )
            msgs = [{"role": "user", "parts": [{"type": "text", "content": prompt}]}]
            with rec.span(
                "chat",
                "assistant",
                attributes={"glassbox.answer.label": label},
                content={"gen_ai.input.messages": msgs},
            ):
                pass
        return Path(rec.path)

    return run


def r_outcome(path: Path) -> str:
    """Sampled answer label of a Family R trace."""
    spans, _ = read_trace(path)
    chat = [s for s in spans if s["attributes"].get("gen_ai.operation.name") == "chat"]
    return str(chat[0]["attributes"]["glassbox.answer.label"])


# --- Family S ---------------------------------------------------------------------


def _s_cfg(config: Dict[str, Any]) -> Dict[str, Any]:
    return {**S_BASE, **config}


def s_weights(state: str, cfg: Dict[str, Any], q_t: float) -> Dict[str, float]:
    """Normalised action probabilities in ``state`` (Addendum 1, item 4)."""
    if state == "start":
        w = {
            "check": cfg["skip_check"],
            "send": cfg["wrong_order"],
            "finish": cfg["early_stop"],
        }
    elif state == "checked":
        w = {"check": 0.02, "send": 0.96, "finish": cfg["early_stop"]}
    elif state == "timeout":
        w = {"send": q_t, "finish": 1.0 - q_t}
    else:
        w = {"send": cfg["resend_bias"], "finish": 1.0 - cfg["resend_bias"]}
    total = sum(w.values())
    return {a: v / total for a, v in w.items()}


def _label(emails: int) -> str:
    return "2+" if emails >= 2 else str(emails)


def s_exact(config: Dict[str, Any], item: str) -> Dist:
    """Exact distribution of emails sent (0 / 1 / 2+) by enumerating the tree."""
    cfg = _s_cfg(config)
    p_t, q_t = S_ITEMS[item]
    v2 = cfg["framework_retry"] == "v2"
    out = {"0": 0.0, "1": 0.0, "2+": 0.0}

    def rec(state: str, d: int, emails: int, p: float) -> None:
        if d == MAX_DECISIONS:
            out[_label(emails)] += p
            return
        for action, pa in s_weights(state, cfg, q_t).items():
            if pa == 0.0:
                continue
            if action == "finish":
                out[_label(emails)] += p * pa
            elif action == "check":
                rec("checked", d + 1, emails, p * pa)
            else:
                rec("ok", d + 1, emails + 1, p * pa * (1.0 - p_t))
                if v2:
                    rec("ok", d + 1, emails + 2, p * pa * p_t)
                else:
                    rec("timeout", d + 1, emails + 1, p * pa * p_t)

    rec("start", 0, 0, 1.0)
    return out


def s_simulate(
    config: Dict[str, Any], item: str, rng: random.Random
) -> Tuple[List[Tuple[Any, ...]], str]:
    """One sampled episode: events and the outcome label."""
    cfg = _s_cfg(config)
    p_t, q_t = S_ITEMS[item]
    state, emails, events = "start", 0, []
    for _ in range(MAX_DECISIONS):
        weights = s_weights(state, cfg, q_t)
        r, acc, action = rng.random(), 0.0, "finish"
        for a, pa in weights.items():
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
        timeout = rng.random() < p_t
        retry = timeout and cfg["framework_retry"] == "v2"
        events.append(
            ("tool", "send_confirmation", "timeout" if timeout else "ok", retry)
        )
        if retry:
            emails += 1
        state = "timeout" if timeout and not retry else "ok"
    return events, _label(emails)


def s_runner(item: str) -> Callable[..., Path]:
    """Glassbox-traced runner for agent test item ``item``."""

    def run(config: Dict[str, Any], seed: int, out: Path, run_id: str) -> Path:
        cfg = _s_cfg(config)
        events, label = s_simulate(cfg, item, random.Random(seed))
        rec = Recorder(out_dir=out, run_id=run_id)
        rec.environment["glassbox.env.log_level"] = str(cfg["log_level"])
        rec.environment["glassbox.env.trace_sampling"] = str(cfg["trace_sampling"])
        with rec:
            for ev in events:
                if ev[0] == "decision":
                    attrs = {
                        "glassbox.agent.state": ev[1],
                        "glassbox.agent.action": ev[2],
                    }
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

    return run


def s_outcome(path: Path) -> str:
    """Emails label of a Family S trace."""
    spans, _ = read_trace(path)
    step = [s for s in spans if s["attributes"].get("glassbox.step.kind") == "outcome"]
    return str(step[0]["attributes"]["glassbox.agent.emails"])


def items(family: str) -> Sequence[str]:
    """Test items of a family."""
    return tuple(QUESTIONS) if family == "R" else tuple(S_ITEMS)
