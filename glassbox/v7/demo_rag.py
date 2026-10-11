"""Built-in demo incident: a small RAG assistant whose answers got worse.

Story: in one week the knowledge base was re-indexed (and the re-index silently
dropped four documents), the prompt template was edited, and a logging setting was
changed. Which change matters?

The system mirrors V7 Experiment 5 (``experiments/v7/real_intervention``): Experiment
1's fictional corpus, a bag-of-words retriever (top_k = 1), and an answer sampled from
the scorer's own two-option distribution, P(correct) = sigmoid(margin / T). With
``--scorer gpt2`` the margin comes from GPT-2 small (log p(correct) − log p(distractor));
with ``--scorer toy`` it comes from a transparent heuristic that is **not a language
model**, for fast offline demos and tests.

The corpus is embedded so the demo works from an installed package. All entities are
fictional.
"""

from __future__ import annotations

import math
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from glassbox.v7.intervene import Factor, Runner
from glassbox.v7.investigate import Incident
from glassbox.v7.trace import Recorder, read_trace

TOP_K = 1
TEMPERATURE = 1.0
STALE_DROPPED = frozenset({"d1", "d2", "d3", "d4"})
STOPWORDS = frozenset(
    "a an the of in on at by for from is was which who what where when to every".split()
)
DOCUMENTS: Dict[str, str] = {
    "d1": "Order 4417 from Brindle Tools was shipped by Kestrel Freight on Monday.",
    "d2": "The Vellmar research lab is located in the city of Oberstadt.",
    "d3": "The Aldwyn project review meeting is held every Tuesday.",
    "d4": "The support team at Pellan Labs is led by Marisol Venn.",
    "d5": "Order 9023 from Mossgate Supplies was shipped by Halcyon Couriers on Friday.",
    "d6": "The Tarrow design studio is located in the city of Quillport.",
    "d7": "The Corvane budget meeting is held every Thursday.",
    "d8": "The finance team at Rookwell Bank is led by Dorian Hale.",
}
QUESTIONS: Dict[str, Tuple[str, str, str]] = {
    "q1": ("Which company shipped order 4417?", " Kestrel", " Halcyon"),
    "q2": (
        "In which city is the Vellmar research lab located?",
        " Oberstadt",
        " Quillport",
    ),
    "q3": (
        "On which day is the Aldwyn project review meeting held?",
        " Tuesday",
        " Thursday",
    ),
    "q4": ("Who leads the support team at Pellan Labs?", " Marisol", " Dorian"),
    "q5": ("Which company shipped order 9023?", " Halcyon", " Kestrel"),
    "q6": (
        "In which city is the Tarrow design studio located?",
        " Quillport",
        " Oberstadt",
    ),
    "q7": ("On which day is the Corvane budget meeting held?", " Thursday", " Tuesday"),
    "q8": ("Who leads the finance team at Rookwell Bank?", " Dorian", " Marisol"),
}
FACTORS = (
    Factor("index", base="full", candidate="stale"),
    Factor("template", base="context_first", candidate="question_first"),
    Factor("log_level", base="info", candidate="debug"),
)

BASE_CONFIG: Dict[str, Any] = {f.name: f.base for f in FACTORS}
CHANGE_LABELS: Dict[str, str] = {
    "index": "the knowledge base was re-indexed",
    "template": "the prompt template was edited",
    "log_level": "the log level was raised",
}

#: ``scorer(prompt, answer) -> log-probability-like score``.
Scorer = Callable[[str, str], float]


def _tokens(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


def retrieve(question: str, index: str) -> List[Tuple[str, float]]:
    """Top-``TOP_K`` (doc id, cosine) from the full or stale index; ties by id."""
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
    return hits[:TOP_K]


def build_prompt(template: str, context: Sequence[str], question: str) -> str:
    """``context_first`` (original) or ``question_first`` (the edit)."""
    ctx = "\n".join(context)
    if template == "context_first":
        return f"Context:\n{ctx}\nQuestion: {question}\nAnswer:"
    if template == "question_first":
        return f"Question: {question}\nContext:\n{ctx}\nAnswer:"
    raise ValueError(f"unknown template {template!r}")


def p_correct(margin: float, temperature: float = TEMPERATURE) -> float:
    """sigmoid(margin / T), numerically safe."""
    z = margin / temperature
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def toy_scorer(prompt: str, answer: str) -> float:
    """NOT a language model: +3 if the answer word is in the prompt, else −3."""
    return 3.0 if answer.strip() in prompt else -3.0


class GPT2Scorer:
    """Teacher-forced log p(answer | prompt) under GPT-2 (loads torch lazily)."""

    def __init__(self, model_name: str = "gpt2") -> None:
        import torch
        from transformer_lens import HookedTransformer

        self._torch = torch
        self.model = HookedTransformer.from_pretrained(model_name, device="cpu")
        self.model.eval()

    def __call__(self, prompt: str, answer: str) -> float:
        torch = self._torch
        p_tok = self.model.to_tokens(prompt, prepend_bos=True)
        a_tok = self.model.to_tokens(answer, prepend_bos=False)
        tokens = torch.cat([p_tok, a_tok], dim=1)
        with torch.no_grad():
            logp = torch.log_softmax(self.model(tokens)[0].double(), dim=-1)
        n = p_tok.shape[1]
        return float(sum(logp[n - 1 + i, a_tok[0, i]] for i in range(a_tok.shape[1])))


def make_scorer(kind: str) -> Scorer:
    """``toy`` (heuristic, instant) or ``gpt2`` (GPT-2 small on CPU)."""
    if kind == "toy":
        return toy_scorer
    if kind == "gpt2":
        return GPT2Scorer()
    raise ValueError(f"unknown scorer {kind!r}")


class _Margins:
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


def make_runner(case: str, margins: Callable[[str, str, str], float]) -> Runner:
    """Runner for one question: retrieve → prompt → sample a two-option answer."""
    question, correct, distractor = QUESTIONS[case]

    def run(config: Dict[str, Any], seed: int, out: Path, run_id: str) -> Path:
        config = {**BASE_CONFIG, **config}  # factors not under test stay at base
        hits = retrieve(question, config["index"])
        prompt = build_prompt(
            config["template"], [DOCUMENTS[d] for d, _ in hits], question
        )
        p = p_correct(margins(prompt, correct, distractor))
        label = "correct" if random.Random(seed).random() < p else "wrong"
        rec = Recorder(out_dir=out, run_id=run_id)
        rec.environment["glassbox.env.log_level"] = str(config["log_level"])
        with rec:
            with rec.span(
                "retrieval", "kb", attributes={"gen_ai.retrieval.top_k": TOP_K}
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


def answer_label(path: Path) -> str:
    """Outcome: was the sampled answer correct?"""
    spans, _ = read_trace(path)
    chat = [s for s in spans if s["attributes"].get("gen_ai.operation.name") == "chat"]
    return str(chat[0]["attributes"]["glassbox.answer.label"])


def make_incident(scorer: Scorer, changes: Optional[Sequence[str]] = None) -> Incident:
    """The demo incident with all 8 questions as test cases.

    Args:
        scorer: ``toy_scorer`` or a :class:`GPT2Scorer`.
        changes: Which factor names changed (default: all three). Factors not listed
            stay at their base value and are not tested.

    Raises:
        ValueError: If ``changes`` is empty or names an unknown factor.
    """
    names = [f.name for f in FACTORS]
    chosen = list(names if changes is None else changes)
    unknown = sorted(set(chosen) - set(names))
    if not chosen or unknown:
        raise ValueError(f"choose one or more of {names}; got {chosen}")
    factors = tuple(f for f in FACTORS if f.name in chosen)
    margins = _Margins(scorer)
    return Incident(
        name="RAG assistant answers got worse after a busy week",
        description=(
            "In one week: "
            + "; ".join(CHANGE_LABELS[f.name] for f in factors)
            + ". Users report wrong answers. Each test question is run repeatedly "
            "before and after, and with one change at a time."
        ),
        factors=factors,
        cases=tuple(QUESTIONS),
        runner_for=lambda case: make_runner(case, margins),
        outcome=answer_label,
    )
