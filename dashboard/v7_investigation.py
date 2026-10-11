"""Glassbox V7 investigation tab: "what changed this week, and which change matters?"

Wraps :mod:`glassbox.v7.investigate` and the built-in RAG demo
(:mod:`glassbox.v7.demo_rag`) for the HuggingFace Space. Gradio is passed in by the
caller (``build_tab(gr)``), so the logic below is importable and testable without it.

Standalone:
    python dashboard/v7_investigation.py
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from glassbox.v7 import demo_rag
from glassbox.v7.intervene import InterventionSettings
from glassbox.v7.investigate import investigate

logger = logging.getLogger(__name__)

#: UI label → factor name in :data:`glassbox.v7.demo_rag.FACTORS`.
CHANGES: Dict[str, str] = {
    "Re-indexed the knowledge base (the re-index dropped 4 documents)": "index",
    "Edited the prompt template (question before context)": "template",
    "Raised the log level (info → debug)": "log_level",
}
SCORERS: Dict[str, str] = {
    "GPT-2 small (real model)": "gpt2",
    "Toy heuristic (instant, not a language model)": "toy",
}
SEED = "space-demo"
INTRO = """
### What changed this week, and which change matters?

A small RAG assistant answers 8 questions about fictional companies. This week, several
things changed at once, and users now report wrong answers.

Glassbox runs every test question **repeatedly** before and after, compares the runs
**beyond run-to-run noise** (where do they differ?), then re-runs with **one change at
a time** (which change actually alters the answers?).

You get a plain-language report and an evidence package anyone can verify with
`python -m glassbox.v7.evidence verify <folder>`.

*The method's evidence: pre-registered Experiments 3b, 4 and 5 in the repository
(`ASSURANCE.md` rows V2.9, V3.1, V3.3). A run here is a demonstration, not new evidence.*
"""

_SCORER_CACHE: Dict[str, demo_rag.Scorer] = {}


def _scorer(kind: str) -> demo_rag.Scorer:
    if kind not in _SCORER_CACHE:
        _SCORER_CACHE[kind] = demo_rag.make_scorer(kind)
    return _SCORER_CACHE[kind]


def run_investigation(
    selected: Sequence[str],
    runs: int,
    scorer_label: str,
    workdir: Optional[Path] = None,
) -> Tuple[str, Optional[str]]:
    """Run the demo investigation; return ``(report_markdown, evidence_zip_path)``.

    Invalid input returns a message and ``None`` instead of raising, so the UI can
    show it.
    """
    changes = [CHANGES[label] for label in selected if label in CHANGES]
    if not changes:
        return "Select at least one change.", None
    if scorer_label not in SCORERS:
        return f"Unknown model choice: {scorer_label!r}", None
    runs = int(runs)
    if not 5 <= runs <= 100:
        return "Runs per configuration must be between 5 and 100.", None
    base = Path(workdir) if workdir else Path(tempfile.mkdtemp(prefix="glassbox_v7_"))
    try:
        scorer = _scorer(SCORERS[scorer_label])
    except (ImportError, OSError, RuntimeError) as exc:
        logger.exception("could not load the model")
        return (
            f"Could not load the model ({type(exc).__name__}: {exc}). "
            "If this mentions pyarrow and NumPy, install the pinned stack: "
            '`pip install "pyarrow==23.0.0" "datasets==4.5.0"`.',
            None,
        )
    incident = demo_rag.make_incident(scorer, changes)
    settings = InterventionSettings(runs, 999, 0.05, SEED)
    inv = investigate(incident, base / "work", settings)
    pkg = inv.export_evidence(base / "evidence", "investigation")
    archive = shutil.make_archive(str(base / "glassbox_evidence"), "zip", pkg)
    report = inv.report_markdown()
    if SCORERS[scorer_label] == "toy":
        report = "> **Toy heuristic, not a language model.**\n\n" + report
    logger.info("investigation complete: %s", archive)
    return report, archive


def build_tab(gr: Any) -> None:
    """Add the investigation UI inside the caller's ``gr.Blocks`` / ``gr.Tab``."""
    gr.Markdown(INTRO)
    labels: List[str] = list(CHANGES)
    changes = gr.CheckboxGroup(
        choices=labels, value=labels, label="What changed this week?"
    )
    runs = gr.Slider(
        minimum=10, maximum=50, value=30, step=10, label="Runs per configuration"
    )
    scorer = gr.Radio(
        choices=list(SCORERS),
        value=list(SCORERS)[0],
        label="Model behind the assistant",
    )
    button = gr.Button("Investigate", variant="primary")
    report = gr.Markdown()
    evidence = gr.File(label="Evidence package (zip)")
    button.click(
        fn=run_investigation,
        inputs=[changes, runs, scorer],
        outputs=[report, evidence],
    )


if __name__ == "__main__":  # pragma: no cover - manual launch
    import gradio

    with gradio.Blocks(title="Glassbox V7 investigation") as app:
        build_tab(gradio)
    app.launch()
