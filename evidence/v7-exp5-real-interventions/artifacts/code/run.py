#!/usr/bin/env python3
"""V7 Experiment 5: controlled interventions on GPT-2 RAG (PROTOCOL.md, commit 47ce955).

Incident: in one week the knowledge base was re-indexed (stale index), the prompt
template was edited, and a logging setting changed; answers got worse. For each of
Experiment 1's 8 questions, ``glassbox.v7.intervene.run_interventions`` (unchanged)
re-runs the RAG system one change at a time to find which change matters.

The system samples its answer from GPT-2's own two-option distribution:
P(correct) = sigmoid(margin / T), margin = log p(correct) − log p(distractor) from
Experiment 1's teacher-forced scorer (deterministic, cached per distinct prompt).

Usage (owner's machine; needs torch + transformer_lens + GPT-2 weights):
    python3 experiments/v7/real_intervention/run.py --out experiments/v7/real_intervention/results
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import random
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from glassbox.v7.groupdiff import group_diff
from glassbox.v7.intervene import Factor, InterventionSettings, run_interventions
from glassbox.v7.trace import Recorder, read_trace

HERE = Path(__file__).resolve().parent
EXP1_DIR = HERE.parent / "rag_fault"
MASTER_SEED = "exp5-20261011"
N_PER_CELL = 30
N_PERM = 999
ALPHA = 0.05
TEMPERATURE = 1.0
FACTORS = [
    Factor("index", base="full", candidate="stale"),
    Factor("template", base="context_first", candidate="question_first"),
    Factor("log_level", base="info", candidate="debug"),
]
AFFECTED = ("q1", "q2", "q3", "q4")
UNAFFECTED = ("q5", "q6", "q7", "q8")

#: ``scorer(prompt, answer) -> log p(answer | prompt)``.
Scorer = Callable[[str, str], float]


def load_exp1() -> ModuleType:
    """Load Experiment 1's ``run.py`` by path (corpus, retriever, prompt, scorer)."""
    spec = importlib.util.spec_from_file_location("exp1_run_e5", EXP1_DIR / "run.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_prompt(template: str, context: Sequence[str], question: str) -> str:
    """``context_first`` is Experiment 1's prompt; ``question_first`` is the edit."""
    if template == "context_first":
        return "Context:\n" + "\n".join(context) + f"\nQuestion: {question}\nAnswer:"
    if template == "question_first":
        return f"Question: {question}\nContext:\n" + "\n".join(context) + "\nAnswer:"
    raise ValueError(f"unknown template {template!r}")


def p_correct(margin: float, temperature: float = TEMPERATURE) -> float:
    """Two-option sampling probability, numerically safe for large |margin|."""
    z = margin / temperature
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


class MarginCache:
    """Deterministic margins, scored once per (prompt, correct, distractor)."""

    def __init__(self, scorer: Scorer) -> None:
        self.scorer = scorer
        self._cache: Dict[Tuple[str, str, str], float] = {}

    def margin(self, prompt: str, q: Dict[str, str]) -> float:
        """log p(correct) − log p(distractor) for ``prompt``."""
        key = (prompt, q["correct"], q["distractor"])
        if key not in self._cache:
            self._cache[key] = self.scorer(prompt, q["correct"]) - self.scorer(
                prompt, q["distractor"]
            )
        return self._cache[key]

    def recheck(self) -> float:
        """Re-score every cached prompt; return the max absolute difference (E4)."""
        diffs = [
            abs((self.scorer(p, c) - self.scorer(p, d)) - m)
            for (p, c, d), m in self._cache.items()
        ]
        return max(diffs) if diffs else 0.0


class RagRunner:
    """Runner for one question: retrieval → prompt → sampled two-option answer."""

    def __init__(
        self,
        exp1: ModuleType,
        docs: List[Dict[str, str]],
        q: Dict[str, str],
        cache: MarginCache,
    ) -> None:
        self.exp1, self.q, self.cache = exp1, q, cache
        self.docs_by_id = {d["id"]: d["text"] for d in docs}
        self.retrievers = {
            "full": exp1.BowRetriever(docs),
            "stale": exp1.BowRetriever(docs, exclude=exp1.FAULT_EXCLUDED),
        }

    def prompt_and_hits(self, index: str, template: str) -> Tuple[str, List[Any]]:
        """Deterministic retrieval and prompt for an (index, template) pair."""
        hits = self.retrievers[index].search(self.q["question"], self.exp1.TOP_K)
        context = [self.docs_by_id[d] for d, _ in hits]
        return build_prompt(template, context, self.q["question"]), hits

    def __call__(
        self, config: Dict[str, Any], seed: int, out: Path, run_id: str
    ) -> Path:
        prompt, hits = self.prompt_and_hits(config["index"], config["template"])
        p = p_correct(self.cache.margin(prompt, self.q))
        label = "correct" if random.Random(seed).random() < p else "distractor"
        rec = Recorder(out_dir=out, run_id=run_id)
        rec.environment["glassbox.env.log_level"] = str(config["log_level"])
        with rec:
            with rec.span(
                "retrieval",
                "kb",
                attributes={"gen_ai.retrieval.top_k": self.exp1.TOP_K},
            ) as s:
                rec.add_content(
                    s,
                    {
                        "gen_ai.retrieval.query.text": self.q["question"],
                        "gen_ai.retrieval.documents": [
                            {"id": d, "score": sc} for d, sc in hits
                        ],
                    },
                )
            msgs = [{"role": "user", "parts": [{"type": "text", "content": prompt}]}]
            with rec.span(
                "chat",
                "gpt2",
                attributes={
                    "gen_ai.request.temperature": TEMPERATURE,
                    "glassbox.answer.label": label,
                },
                content={"gen_ai.input.messages": msgs},
            ):
                pass
        return Path(rec.path)


def label_outcome(path: Path) -> str:
    """The ``chat`` span's answer label."""
    spans, _ = read_trace(path)
    chat = [s for s in spans if s["attributes"].get("gen_ai.operation.name") == "chat"]
    return str(chat[0]["attributes"]["glassbox.answer.label"])


def investigate(
    exp1: ModuleType,
    docs: List[Dict[str, str]],
    q: Dict[str, str],
    cache: MarginCache,
    tmp: Path,
) -> Dict[str, Any]:
    """Run the interventions and the group diff for one question; return a summary."""
    runner = RagRunner(exp1, docs, q, cache)
    margins = {
        f"{i}|{t}": round(cache.margin(runner.prompt_and_hits(i, t)[0], q), 6)
        for i in ("full", "stale")
        for t in ("context_first", "question_first")
    }
    settings = InterventionSettings(
        N_PER_CELL, N_PERM, ALPHA, f"{MASTER_SEED}:{q['id']}"
    )
    report = run_interventions(FACTORS, runner, label_outcome, tmp / q["id"], settings)
    gd = group_diff(
        report.paths["baseline"],
        report.paths["candidate"],
        N_PERM,
        ALPHA,
        0,
        merge_redundant=True,
    )
    first = gd.first_beyond_noise
    d = report.to_dict()
    return {
        "attributed": report.attributed,
        "sufficiency": d["sufficiency"],
        "necessity": d["necessity"],
        "total": d["total"],
        "p_correct": {
            name: c.counts.get("correct", 0) / N_PER_CELL
            for name, c in report.cells.items()
        },
        "margins": margins,
        "group_diff": {
            "first_beyond_noise": [first.step, first.field] if first else None,
            "flagged_steps": sorted({f.step for f in gd.significant}),
        },
    }


def evaluate(
    per_q: Dict[str, Dict[str, Any]],
    recheck_max_diff: float,
    exp1_margins: Dict[str, Dict[str, float]],
) -> Dict[str, Any]:
    """Apply PROTOCOL.md §4 criteria."""
    e1 = {q: "index" in per_q[q]["attributed"] for q in AFFECTED}
    e2 = {q: "index" not in per_q[q]["attributed"] for q in UNAFFECTED}
    e3 = {q: "log_level" in s["attributed"] for q, s in per_q.items()}
    d4 = max(
        abs(per_q[q]["margins"][f"{idx}|context_first"] - exp1_margins[cond][q])
        for q in per_q
        for idx, cond in (("full", "baseline"), ("stale", "fault"))
    )
    return {
        "E1_real_fault_attributed": {
            "per_question": e1,
            "rule": "4/4",
            "pass": all(e1.values()),
        },
        "E2_no_false_index_blame": {
            "per_question": e2,
            "rule": ">= 3/4",
            "pass": sum(e2.values()) >= 3,
        },
        "E3_inert_never_blamed": {
            "per_question": e3,
            "rule": "<= 1/8",
            "pass": sum(e3.values()) <= 1,
        },
        "E4_scorer_determinism": {
            "max_abs_diff": recheck_max_diff,
            "rule": "<= 1e-9",
            "pass": recheck_max_diff <= 1e-9,
        },
        "D1_template": {
            q: {
                "attributed": "template" in s["attributed"],
                "p_correct_baseline": s["p_correct"].get("baseline"),
                "p_correct_only_template": s["p_correct"].get("only_template"),
            }
            for q, s in per_q.items()
        },
        "D4_exp1_crosscheck": {"max_abs_diff": d4},
    }


GATED = (
    "E1_real_fault_attributed",
    "E2_no_false_index_blame",
    "E3_inert_never_blamed",
    "E4_scorer_determinism",
)


def overall(criteria: Dict[str, Any]) -> str:
    """PASS iff every gated criterion passes."""
    return "PASS" if all(criteria[g]["pass"] for g in GATED) else "FAIL"


def run(out: Path, scorer: Scorer, model_name: str = "gpt2") -> Dict[str, Any]:
    """Investigate all 8 questions; write ``results.json`` (never overwrites)."""
    out.mkdir(parents=True, exist_ok=True)
    target = out / "results.json"
    if target.exists():
        raise FileExistsError(f"{target} exists; results are never overwritten")
    exp1 = load_exp1()
    docs, questions = exp1.load_corpus(EXP1_DIR / "corpus.json")
    cache = MarginCache(scorer)
    with tempfile.TemporaryDirectory() as tmp:
        per_q = {
            q["id"]: investigate(exp1, docs, q, cache, Path(tmp)) for q in questions
        }
    exp1_res = json.loads((EXP1_DIR / "results" / "results.json").read_text())
    exp1_margins = {
        c: {q: v["margin"] for q, v in exp1_res["outcomes"][c].items()}
        for c in ("baseline", "fault")
    }
    criteria = evaluate(per_q, cache.recheck(), exp1_margins)
    results = {
        "protocol": "experiments/v7/real_intervention/PROTOCOL.md v1.0",
        "model": model_name,
        "settings": {
            "master_seed": MASTER_SEED,
            "n_per_cell": N_PER_CELL,
            "n_perm": N_PERM,
            "alpha": ALPHA,
            "temperature": TEMPERATURE,
            "factors": [f.__dict__ for f in FACTORS],
            "traces_committed": False,
        },
        "criteria": criteria,
        "overall": overall(criteria),
        "per_question": per_q,
    }
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(results, indent=1) + "\n")
    return results


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point; loads GPT-2 via Experiment 1's scorer."""
    parser = argparse.ArgumentParser(
        description="V7 Experiment 5 (GPT-2 interventions)"
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--model", default="gpt2")
    args = parser.parse_args(argv)
    scorer = load_exp1().GPT2Scorer(args.model)
    results = run(args.out, scorer, args.model)
    for name, c in results["criteria"].items():
        tag = "" if "pass" not in c else ("PASS " if c["pass"] else "FAIL ")
        rest = {k: v for k, v in c.items() if k != "pass"}
        sys.stdout.write(f"{name}: {tag}{json.dumps(rest)}\n")
    for q, s in results["per_question"].items():
        sys.stdout.write(
            f"{q}: attributed {s['attributed']}  p(correct) {s['p_correct']}\n"
        )
    sys.stdout.write(f"EXPERIMENT 5 OVERALL: {results['overall']}\n")
    return 0 if results["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
