#!/usr/bin/env python3
"""V7 Experiment 6: the investigation across model families (PROTOCOL.md, 74f1958).

Repeats Experiment 5's design unchanged on Pythia-160m, OPT-125m and Qwen2.5-0.5B
(fallback Qwen2-0.5B), one model at a time. Experiment 5's ``RagRunner``,
``MarginCache``, ``FACTORS`` and ``label_outcome`` and Experiment 1's corpus,
retriever and teacher-forced scorer (``GPT2Scorer(model_name)``, which accepts any
TransformerLens model) are reused by import.

Because each model's margins are deterministic, the true effect of every factor on
every question is computed exactly before the runs and the gates (X1–X3) are defined
against it.

Note: Experiment 5's runner labels the chat span target ``"gpt2"`` regardless of the
model. Traces are not committed here; ``results.json`` records the real model name.

Usage (owner's machine; downloads the three models on first use):
    python3 experiments/v7/cross_model/run.py --out experiments/v7/cross_model/results
"""

from __future__ import annotations

import argparse
import gc
import importlib.util
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from glassbox.v7.groupdiff import group_diff
from glassbox.v7.intervene import InterventionSettings, run_interventions

HERE = Path(__file__).resolve().parent
EXP5 = HERE.parent / "real_intervention" / "run.py"
N_PER_CELL = 30
N_PERM = 999
ALPHA = 0.05
LARGE = 0.5
X2_MAX = 1
X3_TOL = 1e-6
ZERO_INDEX_QUESTIONS = ("q5", "q6", "q7", "q8")

Scorer = Callable[[str, str], float]
ScorerFactory = Callable[[str], Scorer]


@dataclass(frozen=True)
class ModelSpec:
    """A model family entry: primary TransformerLens name plus declared fallbacks."""

    family: str
    name: str
    fallbacks: Tuple[str, ...] = ()


MODELS = (
    ModelSpec("Pythia", "EleutherAI/pythia-160m"),
    ModelSpec("OPT", "facebook/opt-125m"),
    ModelSpec("Qwen 2.5", "Qwen/Qwen2.5-0.5B", ("Qwen/Qwen2-0.5B",)),
)


def load_exp5() -> ModuleType:
    """Load Experiment 5's ``run.py`` by path."""
    spec = importlib.util.spec_from_file_location("exp5_run_e6", EXP5)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def default_factory(name: str) -> Scorer:
    """Experiment 1's teacher-forced scorer for any TransformerLens model name."""
    scorer: Scorer = load_exp5().load_exp1().GPT2Scorer(name)
    return scorer


def load_model(
    spec: ModelSpec, factory: ScorerFactory
) -> Tuple[Optional[str], Optional[Scorer], List[str]]:
    """Try the primary name, then declared fallbacks; return (name, scorer, errors)."""
    errors: List[str] = []
    for name in (spec.name, *spec.fallbacks):
        try:
            return name, factory(name), errors
        except (
            Exception
        ) as exc:  # noqa: BLE001 - any load failure is reported, not hidden
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    return None, None, errors


def _p(margin: float) -> float:
    return float(load_exp5_cached().p_correct(margin))


_EXP5_CACHE: Dict[str, ModuleType] = {}


def load_exp5_cached() -> ModuleType:
    """Experiment 5 module, loaded once per process."""
    if "m" not in _EXP5_CACHE:
        _EXP5_CACHE["m"] = load_exp5()
    return _EXP5_CACHE["m"]


def true_effects(margins: Dict[str, float], qid: str) -> Dict[str, Dict[str, Any]]:
    """Exact true TVD of switching each factor alone, with its ground-truth class."""
    base = _p(margins["full|context_first"])
    tvd = {
        "index": abs(base - _p(margins["stale|context_first"])),
        "template": abs(base - _p(margins["full|question_first"])),
        "log_level": 0.0,
    }
    out: Dict[str, Dict[str, Any]] = {}
    for factor, value in tvd.items():
        by_construction_zero = factor == "log_level" or (
            factor == "index" and qid in ZERO_INDEX_QUESTIONS
        )
        if by_construction_zero:
            cls = "zero"
        elif value >= LARGE:
            cls = "large"
        else:
            cls = "small"
        out[factor] = {"true_tvd": round(value, 6), "class": cls}
    return out


def _investigate_question(
    exp5: ModuleType, runner: Any, q: Dict[str, str], model: str, tmp: Path
) -> Dict[str, Any]:
    margins = {
        f"{i}|{t}": round(runner.cache.margin(runner.prompt_and_hits(i, t)[0], q), 6)
        for i in ("full", "stale")
        for t in ("context_first", "question_first")
    }
    settings = InterventionSettings(
        N_PER_CELL, N_PERM, ALPHA, f"exp6-{model}:{q['id']}"
    )
    report = run_interventions(exp5.FACTORS, runner, exp5.label_outcome, tmp, settings)
    gd = group_diff(
        report.paths["baseline"], report.paths["candidate"], N_PERM, ALPHA, 0
    )
    first = gd.first_beyond_noise
    truth = true_effects(margins, q["id"])
    suff = {t.factor: t for t in report.sufficiency}
    pairs = {
        f: {
            **truth[f],
            "observed_tvd": round(suff[f].tvd, 6),
            "p_value": suff[f].p_value,
            "attributed": suff[f].significant,
        }
        for f in truth
    }
    return {
        "margins": margins,
        "baseline_p_correct": round(_p(margins["full|context_first"]), 6),
        "pairs": pairs,
        "cell_counts": {k: v.counts for k, v in report.cells.items()},
        "group_diff": {
            "first_beyond_noise": [first.step, first.field] if first else None,
            "flagged_steps": sorted({f.step for f in gd.significant}),
        },
    }


def investigate_model(
    exp5: ModuleType, scorer: Scorer, model: str, tmp: Path
) -> Dict[str, Any]:
    """Run all 8 questions for one model; return per-question results and recheck."""
    exp1 = exp5.load_exp1()
    docs, questions = exp1.load_corpus(exp5.EXP1_DIR / "corpus.json")
    cache = exp5.MarginCache(scorer)
    per_q = {}
    for q in questions:
        runner = exp5.RagRunner(exp1, docs, q, cache)
        per_q[q["id"]] = _investigate_question(exp5, runner, q, model, tmp / q["id"])
    return {"per_question": per_q, "recheck_max_diff": cache.recheck()}


def model_criteria(summary: Dict[str, Any]) -> Dict[str, Any]:
    """X1 sensitivity, X2 specificity, X3 determinism for one model that ran."""
    pairs = [p for q in summary["per_question"].values() for p in q["pairs"].values()]
    large = [p for p in pairs if p["class"] == "large"]
    zero_hits = sum(1 for p in pairs if p["class"] == "zero" and p["attributed"])
    x1_ok = all(p["attributed"] for p in large)
    x3 = summary["recheck_max_diff"]
    crit = {
        "X1_sensitivity": {
            "applicable": bool(large),
            "large_pairs": len(large),
            "attributed": sum(1 for p in large if p["attributed"]),
            "pass": x1_ok,
        },
        "X2_specificity": {
            "zero_pairs": sum(1 for p in pairs if p["class"] == "zero"),
            "attributed": zero_hits,
            "rule": f"<= {X2_MAX}",
            "pass": zero_hits <= X2_MAX,
        },
        "X3_determinism": {
            "max_abs_diff": x3,
            "rule": f"<= {X3_TOL}",
            "pass": x3 <= X3_TOL,
        },
    }
    crit["pass"] = all(c["pass"] for c in crit.values() if isinstance(c, dict))
    return crit


def overall(models: Sequence[Dict[str, Any]]) -> str:
    """PASS iff >= 2 models ran and every model that ran passed."""
    ran = [m for m in models if m["status"] == "RUN"]
    if len(ran) < 2:
        return "FAIL"
    return "PASS" if all(m["criteria"]["pass"] for m in ran) else "FAIL"


def _run_one(
    spec: ModelSpec, factory: ScorerFactory, exp5: ModuleType, tmp: Path
) -> Dict[str, Any]:
    name, scorer, errors = load_model(spec, factory)
    entry: Dict[str, Any] = {
        "family": spec.family,
        "requested": spec.name,
        "errors": errors,
    }
    if scorer is None or name is None:
        entry["status"] = "NOT RUN"
        return entry
    summary = investigate_model(exp5, scorer, name, tmp / spec.family.replace(" ", "_"))
    del scorer
    gc.collect()
    entry.update({"status": "RUN", "model": name, **summary})
    entry["criteria"] = model_criteria(summary)
    return entry


def run(out: Path, factory: ScorerFactory = default_factory) -> Dict[str, Any]:
    """Run all models; write ``results.json`` (never overwrites)."""
    out.mkdir(parents=True, exist_ok=True)
    target = out / "results.json"
    if target.exists():
        raise FileExistsError(f"{target} exists; results are never overwritten")
    exp5 = load_exp5()
    with tempfile.TemporaryDirectory() as tmp:
        models = [_run_one(spec, factory, exp5, Path(tmp)) for spec in MODELS]
    exp5_res = exp5.EXP1_DIR.parent / "real_intervention" / "results" / "results.json"
    gpt2 = (
        {
            q: s["margins"]
            for q, s in json.loads(exp5_res.read_text())["per_question"].items()
        }
        if exp5_res.exists()
        else None
    )
    results = {
        "protocol": "experiments/v7/cross_model/PROTOCOL.md v1.0",
        "settings": {
            "n_per_cell": N_PER_CELL,
            "n_perm": N_PERM,
            "alpha": ALPHA,
            "large_threshold": LARGE,
            "x2_max": X2_MAX,
            "x3_tolerance": X3_TOL,
            "traces_committed": False,
        },
        "models": models,
        "overall": overall(models),
        "D4_gpt2_margins_from_experiment5": gpt2,
    }
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(json.dumps(results, indent=1) + "\n")
    return results


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point; prints per-model criteria and the overall result."""
    parser = argparse.ArgumentParser(description="V7 Experiment 6 (cross-model)")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    res = run(args.out)
    for m in res["models"]:
        if m["status"] != "RUN":
            sys.stdout.write(f"{m['family']}: NOT RUN {m['errors']}\n")
            continue
        c = m["criteria"]
        sys.stdout.write(
            f"{m['family']} ({m['model']}): "
            f"X1 {'PASS' if c['X1_sensitivity']['pass'] else 'FAIL'} "
            f"{c['X1_sensitivity']['attributed']}/{c['X1_sensitivity']['large_pairs']} large | "
            f"X2 {'PASS' if c['X2_specificity']['pass'] else 'FAIL'} "
            f"{c['X2_specificity']['attributed']}/{c['X2_specificity']['zero_pairs']} zero blamed | "
            f"X3 {'PASS' if c['X3_determinism']['pass'] else 'FAIL'} "
            f"{c['X3_determinism']['max_abs_diff']}\n"
        )
        for q, s in m["per_question"].items():
            row = {
                f: (p["class"], p["true_tvd"], p["attributed"])
                for f, p in s["pairs"].items()
            }
            sys.stdout.write(
                f"   {q} base P(correct) {s['baseline_p_correct']} {row}\n"
            )
    sys.stdout.write(f"EXPERIMENT 6 OVERALL: {res['overall']}\n")
    return 0 if res["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
