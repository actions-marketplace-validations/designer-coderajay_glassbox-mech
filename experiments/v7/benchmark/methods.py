"""The three methods of V7 Experiment 10 on one unit (PROTOCOL.md §3, Addendum 1 item 6).

GB (Glassbox), B0 (revert everything) and B1 (one-pair first divergence) share one
budget: the cells of ``run_interventions``. B1 reuses run 0 of baseline and candidate.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional

from glassbox.v7.diff import diff_traces
from glassbox.v7.intervene import Factor, InterventionSettings, run_interventions
from glassbox.v7.trace import read_trace

HERE = Path(__file__).resolve().parent
R_RETRIEVAL = ("index", "top_k")
R_PROMPT = ("template", "preamble")
S_POLICY = ("skip_check", "early_stop", "wrong_order", "resend_bias")


def _sibling(name: str) -> ModuleType:
    key = f"exp10_{name}"
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, HERE / f"{name}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


FAM = _sibling("families")
_MARGINS: Dict[int, Any] = {}


def margins_for(scorer: Any) -> Any:
    """One shared margin cache per scorer, so GPT-2 scores each prompt once."""
    if id(scorer) not in _MARGINS:
        _MARGINS[id(scorer)] = FAM.Margins(scorer)
    return _MARGINS[id(scorer)]


def _span_at(path: str, index: Optional[int]) -> Dict[str, Any]:
    spans, _ = read_trace(path)
    for s in spans:
        if s["attributes"].get("glassbox.step.index") == index:
            return s
    return {"attributes": {}}


def b1_blame(
    family: str, changed: List[str], base_run: str, cand_run: str
) -> Dict[str, Any]:
    """B1: blame by the owner of the first divergent step of one run pair."""
    first = diff_traces(base_run, cand_run).first_divergence
    if first is None:
        return {"detected": False, "blamed": []}
    sa = _span_at(base_run, first.step_a) if first.step_a is not None else {}
    sb = _span_at(cand_run, first.step_b) if first.step_b is not None else {}
    attrs_a = sa.get("attributes", {})
    attrs_b = sb.get("attributes", {})
    if family == "R":
        op = attrs_a.get("gen_ai.operation.name") or attrs_b.get(
            "gen_ai.operation.name"
        )
        owners = R_RETRIEVAL if op == "retrieval" else R_PROMPT if op == "chat" else ()
    elif attrs_a.get("glassbox.tool.framework_retry") or attrs_b.get(
        "glassbox.tool.framework_retry"
    ):
        owners = ("framework_retry",)
    else:
        owners = S_POLICY
    return {"detected": True, "blamed": [f for f in changed if f in owners]}


def _exact_fn(family: str, item: str, scorer: Any) -> Callable[[Dict[str, Any]], Any]:
    if family == "R":
        margins = margins_for(scorer)
        return lambda cfg: FAM.r_exact(cfg, item, margins)
    return lambda cfg: FAM.s_exact(cfg, item)


def _runner(family: str, item: str, scorer: Any) -> Any:
    if family == "R":
        return FAM.r_runner(item, margins_for(scorer)), FAM.r_outcome
    return FAM.s_runner(item), FAM.s_outcome


def run_unit(
    incident: Dict[str, Any],
    item: str,
    workdir: Path,
    settings: InterventionSettings,
    scorer: Any = None,
) -> Dict[str, Any]:
    """Run GB, B0 and B1 on one (incident, item) and attach exact ground truth."""
    family = incident["family"]
    factors = [
        Factor(f["name"], f["base"], f["candidate"]) for f in incident["factors"]
    ]
    names = [f.name for f in factors]
    runner, outcome = _runner(family, item, scorer)
    report = run_interventions(factors, runner, outcome, workdir, settings)
    exact = _exact_fn(family, item, scorer)
    base = {f.name: f.base for f in factors}
    cand = {f.name: f.candidate for f in factors}
    d_base = exact(base)
    truth = {
        f.name: round(FAM.tvd(d_base, exact({**base, f.name: f.candidate})), 6)
        for f in factors
    }
    detected = report.total.significant
    methods = {
        "GB": {"detected": detected, "blamed": report.attributed if detected else []},
        "B0": {"detected": detected, "blamed": list(names) if detected else []},
        "B1": b1_blame(
            family, names, report.paths["baseline"][0], report.paths["candidate"][0]
        ),
    }
    for m in methods.values():
        fixed = {**cand, **{n: base[n] for n in m["blamed"]}}
        m["fix_tvd"] = round(FAM.tvd(d_base, exact(fixed)), 6)
    distinct = {p for ps in report.paths.values() for p in ps}
    return {
        "incident": incident["id"],
        "family": family,
        "negative": incident["negative"],
        "item": item,
        "truth": truth,
        "candidate_total_tvd": round(FAM.tvd(d_base, exact(cand)), 6),
        "methods": methods,
        "total_test": {"tvd": report.total.tvd, "p_value": report.total.p_value},
        "sufficiency": {
            t.factor: {"tvd": t.tvd, "p_value": t.p_value, "significant": t.significant}
            for t in report.sufficiency
        },
        "runs": len(distinct),
    }
