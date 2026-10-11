"""Tests for the V7 investigation tab (dashboard/v7_investigation.py), toy scorer only.

Gradio is not required: ``build_tab`` is exercised with a mock ``gr`` module.
"""

from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from glassbox.v7.evidence import verify_package

MOD_PATH = Path(__file__).resolve().parent.parent / "dashboard" / "v7_investigation.py"
TOY = "Toy heuristic (instant, not a language model)"


@pytest.fixture(scope="module")
def tab():
    spec = importlib.util.spec_from_file_location("v7_investigation", MOD_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_investigation_toy_returns_report_and_verifiable_zip(tab, tmp_path):
    report, archive = tab.run_investigation(list(tab.CHANGES), 10, TOY, tmp_path)
    assert report.startswith("> **Toy heuristic, not a language model.**")
    assert "Switching index alone changed the outcome in 4/8 test cases" in report
    assert archive is not None and archive.endswith(".zip")
    out = tmp_path / "unzipped"
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(out)
    assert verify_package(out) == []


def test_subset_of_changes(tab, tmp_path):
    labels = [k for k, v in tab.CHANGES.items() if v != "index"]
    report, archive = tab.run_investigation(labels, 10, TOY, tmp_path)
    assert "`index`" not in report and archive is not None
    assert "No outcome change was detected from template, log_level alone" in report


@pytest.mark.parametrize(
    "selected,runs,scorer,message",
    [
        ([], 30, TOY, "Select at least one change."),
        (
            ["Re-indexed the knowledge base (the re-index dropped 4 documents)"],
            2,
            TOY,
            "between 5 and 100",
        ),
        (
            ["Re-indexed the knowledge base (the re-index dropped 4 documents)"],
            30,
            "nope",
            "Unknown model",
        ),
    ],
)
def test_invalid_input_returns_message(tab, selected, runs, scorer, message):
    report, archive = tab.run_investigation(selected, runs, scorer)
    assert message in report and archive is None


def test_build_tab_wires_button(tab):
    gr = MagicMock()
    tab.build_tab(gr)
    gr.Markdown.assert_any_call(tab.INTRO)
    kwargs = gr.Button.return_value.click.call_args.kwargs
    assert kwargs["fn"] is tab.run_investigation
    assert kwargs["inputs"] == [
        gr.CheckboxGroup.return_value,
        gr.Slider.return_value,
        gr.Radio.return_value,
    ]
    assert kwargs["outputs"] == [gr.Markdown.return_value, gr.File.return_value]


def test_module_does_not_import_gradio_at_top_level():
    import ast

    tree = ast.parse(MOD_PATH.read_text())
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top for a in n.names} | {
        n.module for n in top if isinstance(n, ast.ImportFrom) and n.module
    }
    assert "gradio" not in names
