"""Tests for the V7 end-to-end investigation and the built-in RAG demo (toy scorer)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from glassbox.v7 import demo_rag
from glassbox.v7.evidence import verify_package
from glassbox.v7.intervene import InterventionSettings
from glassbox.v7.investigate import investigate, main, render_report

FAST = InterventionSettings(n_per_cell=8, n_perm=99, alpha=0.05, seed="test")


@pytest.fixture(scope="module")
def toy_investigation(tmp_path_factory):
    out = tmp_path_factory.mktemp("inv")
    inc = demo_rag.make_incident(demo_rag.toy_scorer)
    return investigate(inc, out / "work", FAST)


# --- demo system ------------------------------------------------------------------


def test_retrieval_matches_experiment_1_design():
    for q in ("q1", "q2", "q3", "q4"):
        doc = f"d{q[1]}"
        assert demo_rag.retrieve(demo_rag.QUESTIONS[q][0], "full")[0][0] == doc
        assert demo_rag.retrieve(demo_rag.QUESTIONS[q][0], "stale")[0][0] != doc
    for q in ("q5", "q6", "q7", "q8"):
        question = demo_rag.QUESTIONS[q][0]
        assert demo_rag.retrieve(question, "full") == demo_rag.retrieve(
            question, "stale"
        )


def test_corpus_matches_experiment_1_file():
    root = Path(__file__).resolve().parent.parent
    path = root / "experiments" / "v7" / "rag_fault" / "corpus.json"
    if not path.exists():
        pytest.skip("experiment corpus not present")
    data = json.loads(path.read_text())
    assert {d["id"]: d["text"] for d in data["documents"]} == demo_rag.DOCUMENTS
    assert {
        q["id"]: (q["question"], q["correct"], q["distractor"])
        for q in data["questions"]
    } == demo_rag.QUESTIONS


def test_templates_and_probability():
    assert demo_rag.build_prompt("context_first", ["A."], "Q?") == (
        "Context:\nA.\nQuestion: Q?\nAnswer:"
    )
    assert demo_rag.build_prompt("question_first", ["A."], "Q?") == (
        "Question: Q?\nContext:\nA.\nAnswer:"
    )
    with pytest.raises(ValueError):
        demo_rag.build_prompt("x", [], "Q?")
    assert demo_rag.p_correct(0.0) == 0.5
    assert demo_rag.p_correct(-900.0) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        demo_rag.make_scorer("nope")
    assert demo_rag.make_scorer("toy") is demo_rag.toy_scorer


def test_runner_trace_has_no_raw_text(tmp_path):
    run = demo_rag.make_runner("q1", lambda p, c, d: 5.0)
    cfg = {"index": "full", "template": "context_first", "log_level": "debug"}
    path = run(cfg, 3, tmp_path, "r000")
    text = path.read_text()
    assert "Kestrel" not in text and "order 4417" not in text.lower()
    assert demo_rag.answer_label(path) in {"correct", "wrong"}


# --- investigation ----------------------------------------------------------------


def test_toy_investigation_attributes_stale_index_only(toy_investigation):
    inv = toy_investigation
    summary = inv.factor_summary()
    assert summary["index"]["switching_alone_changed"] == ["q1", "q2", "q3", "q4"]
    assert summary["template"]["switching_alone_changed"] == []
    assert summary["log_level"]["switching_alone_changed"] == []
    first = {c.case: c.first_beyond_noise for c in inv.findings}
    assert first["q1"][0] == "retrieval#0"
    assert first["q5"][0] == "chat#0"  # prompt changed, outcome did not


def test_report_is_plain_and_does_not_say_caused(toy_investigation):
    md = render_report(toy_investigation)
    assert "## Answer" in md and "## What this does not show" in md
    assert "Switching index alone changed the outcome in 4/8 test cases" in md
    assert "No outcome change was detected from template, log_level alone" in md
    assert "caused" not in md.lower()
    assert "In 4 case(s) (q5, q6, q7, q8) the runs differed beyond noise" in md
    assert "| q1 | correct 8/8 | wrong 8/8 |" in md


def test_export_evidence_verifies(toy_investigation, tmp_path):
    pkg = toy_investigation.export_evidence(tmp_path / "evidence", "inv-test")
    assert verify_package(pkg) == []
    claim = json.loads((pkg / "claim.json").read_text())
    assert claim["status"] == "PRELIMINARY"
    assert "4/8" in claim["claim"]
    json.dumps(toy_investigation.to_dict())


def test_cli_demo_toy(tmp_path, capsys, monkeypatch):
    out = tmp_path / "demo"
    assert main(["demo", "--out", str(out), "--scorer", "toy", "--runs", "6"]) == 0
    printed = capsys.readouterr().out
    assert "toy scorer, not a language model" in printed
    assert (out / "REPORT.md").exists()
    assert verify_package(out / "evidence" / "investigation") == []
    with pytest.raises(FileExistsError):
        main(["demo", "--out", str(out), "--scorer", "toy", "--runs", "6"])


def test_incident_with_subset_of_changes(tmp_path):
    inc = demo_rag.make_incident(demo_rag.toy_scorer, ["template", "log_level"])
    assert [f.name for f in inc.factors] == ["template", "log_level"]
    assert "re-indexed" not in inc.description
    assert "prompt template was edited" in inc.description
    inv = investigate(inc, tmp_path, FAST)
    assert all(not c.attributed for c in inv.findings)  # index stays full
    with pytest.raises(ValueError):
        demo_rag.make_incident(demo_rag.toy_scorer, [])
    with pytest.raises(ValueError):
        demo_rag.make_incident(demo_rag.toy_scorer, ["model"])


def test_model_label_is_in_description():
    inc = demo_rag.make_incident(demo_rag.toy_scorer)
    assert "toy heuristic (NOT a language model)" in inc.description
    assert demo_rag.model_label(lambda p, a: 0.0).startswith("custom scorer")
