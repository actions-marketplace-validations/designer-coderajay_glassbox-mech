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


def test_model_load_failure_returns_readable_message(tab, monkeypatch):
    def broken(kind):
        raise ImportError("pyarrow requires NumPy 2.0 or newer, found 1.26.4")

    monkeypatch.setattr(tab, "_scorer", broken)
    report, archive = tab.run_investigation(
        list(tab.CHANGES), 10, "GPT-2 small (real model)"
    )
    assert archive is None
    assert "Could not load the model (ImportError" in report
    assert "pyarrow==23.0.0" in report


def test_evidence_package_records_toy_scorer(tab, tmp_path):
    import json

    _, archive = tab.run_investigation(list(tab.CHANGES), 10, TOY, tmp_path)
    out = tmp_path / "unz"
    with zipfile.ZipFile(archive) as zf:
        zf.extractall(out)
    prov = json.loads((out / "provenance.json").read_text())
    assert "toy heuristic (NOT a language model)" in json.dumps(prov)


def test_cleanup_stale_removes_only_old_demo_folders(tab, tmp_path):
    import os
    import time

    old = tmp_path / f"{tab.TMP_PREFIX}old"
    new = tmp_path / f"{tab.TMP_PREFIX}new"
    other = tmp_path / "unrelated"
    for d in (old, new, other):
        d.mkdir()
    past = time.time() - 2 * tab.STALE_AFTER_S
    os.utime(old, (past, past))
    os.utime(other, (past, past))
    assert tab.cleanup_stale(tmp_path) == 1
    assert not old.exists() and new.exists() and other.exists()
