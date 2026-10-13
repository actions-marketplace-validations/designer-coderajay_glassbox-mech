"""Tests for dashboard/space_ui.py: pure helpers behind the HuggingFace Space.

No gradio, torch or model needed: the module must stay importable without them.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

MOD_PATH = Path(__file__).resolve().parent.parent / "dashboard" / "space_ui.py"


@pytest.fixture(scope="module")
def ui():
    spec = importlib.util.spec_from_file_location("space_ui", MOD_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _result(suff=1.0, comp=0.543, f1=0.704, circuit=((9, 9),), approx=True):
    attrs = {str((l, h)): 0.0 for l in range(12) for h in range(12)}
    attrs[str((9, 9))] = 0.5
    attrs[str((3, 0))] = -0.2
    return {
        "circuit": list(circuit),
        "attributions": attrs,
        "clean_ld": 3.2,
        "faithfulness": {
            "sufficiency": suff,
            "comprehensiveness": comp,
            "f1": f1,
            "category": "faithful",
            "suff_is_approx": approx,
        },
        "evidence_tier": {"tier": "C", "label": "behavioral", "disclosure": "Tier C."},
    }


# --- module hygiene -----------------------------------------------------------


def test_no_heavy_imports_at_top_level():
    tree = ast.parse(MOD_PATH.read_text())
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {
        n.module.split(".")[0]
        for n in top
        if isinstance(n, ast.ImportFrom) and n.module
    }
    assert not names & {"gradio", "torch", "transformer_lens", "glassbox"}


def test_copy_has_no_known_overclaims(ui):
    text = " ".join(
        str(getattr(ui, name)) for name in dir(ui) if name.isupper()
    ).lower()
    for phrase in (
        "regulator-ready",
        "any model. any prompt",
        "9/9",
        "all 9 sections",
        "fully compliant",
        "21/21",
        "v4.3.0",
        "pricing",
    ):
        assert phrase not in text, phrase
    assert "not legal advice" in text
    assert "declaration of conformity" in text


def test_version_matches_package(ui):
    pyproject = (MOD_PATH.parent.parent / "pyproject.toml").read_text()
    version = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M).group(1)
    assert ui.VERSION == version
    assert version in ui.header_html("ready")


# --- grading --------------------------------------------------------------------


@pytest.mark.parametrize(
    "suff,comp,f1,grade",
    [
        (1.0, 0.543, 0.704, "B"),  # canonical IOI result
        (0.9, 0.7, 0.85, "A"),
        (0.5, 0.3, 0.55, "C"),
        (0.11, 0.26, 0.156, "D"),
        (0.9, 0.1, 0.70, "C"),  # comprehensiveness too low for B
    ],
)
def test_grade_matches_library_thresholds(ui, suff, comp, f1, grade):
    assert ui.grade(suff, comp, f1)[0] == grade


# --- input validation -------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt,correct,incorrect,ok",
    [
        (
            "When Mary and John went to the store, John gave a drink to",
            " Mary",
            " John",
            True,
        ),
        ("", " Mary", " John", False),
        ("Hello", "", " John", False),
        ("Hello", " same", " same", False),
        ("x" * 2000, " a", " b", False),
    ],
)
def test_validate_inputs(ui, prompt, correct, incorrect, ok):
    err = ui.validate_inputs(prompt, correct, incorrect)
    assert (err is None) is ok


# --- renderers ------------------------------------------------------------------


def test_metric_cards_show_values_and_grade(ui):
    html = ui.metric_cards_html(_result())
    assert "70%" in html and "100%" in html and "54%" in html
    assert ">B<" in html
    assert "first-order estimate" in html


def test_head_grid_marks_circuit_and_escapes(ui):
    html = ui.head_grid_html(_result()["attributions"], [(9, 9)], 12, 12)
    assert html.count('class="gb-cell') == 144
    assert html.count("gb-in-circuit") == 1
    assert "L9 H9" in html


def test_logit_lens_rows(ui):
    rows = [(i, 0.01 * i, 100 - i) for i in range(12)]
    html = ui.logit_lens_html(rows, " Mary")
    assert html.count('class="gb-ll-row"') == 12
    assert "&#x27; Mary&#x27;" in html or "' Mary'" in html or "Mary" in html


def test_attention_matrix_escapes_tokens(ui):
    toks = ["<script>", "b", "c"]
    pattern = [[1.0, 0, 0], [0.5, 0.5, 0], [0.2, 0.3, 0.5]]
    html = ui.attention_html(toks, pattern, 9, 9)
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_error_html_is_escaped(ui):
    html = ui.message_html("bad <b>input</b>", kind="error")
    assert "<b>input" not in html and "&lt;b&gt;" in html


def test_example_rows_are_valid(ui):
    assert len(ui.EXAMPLES) >= 3
    for prompt, correct, incorrect in ui.EXAMPLES:
        assert ui.validate_inputs(prompt, correct, incorrect) is None


def test_annex_sections_counts_placeholders(ui):
    sections = {
        "1_general_description": {"system_name": "gpt2", "_regulation_ref": "x"},
        "8_declaration": {
            "declaration_reference": "GDOC-1",
            "signatory_name": "[PROVIDER TO COMPLETE — name]",
        },
    }
    html = ui.annex_sections_html(sections)
    assert html.count("<tr><td>") == 9
    assert "needs your input" in html and "drafted" in html
    assert ui._count_fields(sections["8_declaration"]) == (1, 1)


@pytest.mark.parametrize(
    "kwargs,needle",
    [
        ({}, "grade B. The circuit explains most"),
        (
            {
                "suff": 0.11,
                "comp": 0.26,
                "f1": 0.156,
                "circuit": ((6, 1), (10, 0), (9, 3), (3, 11)),
            },
            "should not be relied on",
        ),
    ],
)
def test_summary_text_is_built_from_numbers(ui, kwargs, needle):
    text = ui.summary_text(_result(**kwargs), " Mary", " John")
    assert needle in text
    assert "' Mary'" in text and "' John'" in text
    assert "first-order estimate" in text


def test_app_serialises_model_access_and_stores_no_prompts():
    src = (MOD_PATH.parent / "app.py").read_text()
    assert '"concurrency_id": "model"' in src and '"concurrency_limit": 1' in src
    assert "AuditLog" not in src  # the old demo wrote every prompt to disk
    for phrase in ("regulator-ready", "Compliant", "v4.3.0", "21/21"):
        assert phrase not in src, phrase


def test_space_requirements_are_pinned():
    wf = (
        MOD_PATH.parent.parent / ".github" / "workflows" / "deploy_hf.yml"
    ).read_text()
    block = wf.split("cat > hf_payload/requirements.txt << 'REQS'", 1)[1].split(
        "REQS", 1
    )[0]
    reqs = [
        line.strip()
        for line in block.splitlines()
        if line.strip() and not line.strip().startswith(("#", "--"))
    ]
    assert reqs and all("==" in r for r in reqs), reqs
    assert "pyarrow==23.0.0" in reqs and "numpy==1.26.4" in reqs
    assert (
        'sdk_version: "5.50.0"' in wf
        and "space_ui.py" in wf
        and "v7_agent_demo.py" in wf
    )
