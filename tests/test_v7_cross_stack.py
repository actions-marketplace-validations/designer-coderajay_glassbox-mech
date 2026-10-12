"""V7 Experiment 8 (cross-stack) mechanics, without LlamaIndex or OpenTelemetry."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "experiments" / "v7" / "cross_stack"
EXP1 = ROOT / "experiments" / "v7" / "rag_fault"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def subject():
    return _load("exp8_subject", EXP / "subject.py")


@pytest.fixture()
def ev():
    return _load("exp8_evaluate", EXP / "evaluate.py")


def test_tokeniser_matches_experiment_1(subject):
    exp1 = _load("exp1_run_for_exp8", EXP1 / "run.py")
    corpus = json.loads((EXP1 / "corpus.json").read_text())
    texts = [d["text"] for d in corpus["documents"]] + [
        q["question"] for q in corpus["questions"]
    ]
    for t in texts:
        assert subject.tokenize(t) == exp1.tokenize(t)


def test_vocab_and_vectors_deterministic(subject):
    docs, _ = subject.load_corpus()
    vocab = subject.build_vocab(docs)
    assert vocab == sorted(set(vocab))
    v1 = subject.bow_vector("Kestrel Freight shipped it", vocab)
    assert v1 == subject.bow_vector("Kestrel Freight shipped it", vocab)
    assert len(v1) == len(vocab) and sum(v1) > 0


def test_conditions_fixed(subject):
    docs, _ = subject.load_corpus()
    ids = {
        c: [d["id"] for d in subject.condition_docs(docs, c)]
        for c in subject.CONDITIONS
    }
    assert subject.CONDITIONS == ("baseline", "baseline_repeat", "fault", "restored")
    assert ids["fault"] == ["d5", "d6", "d7", "d8"]
    assert ids["baseline"] == ids["restored"] == ids["baseline_repeat"]
    assert len(ids["baseline"]) == 8


# --- evaluate, on a synthetic stack-B result tree ------------------------------


def _kv(key, value):
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    if isinstance(value, list):
        vals = [{"doubleValue": x} for x in value]
        return {"key": key, "value": {"arrayValue": {"values": vals}}}
    return {"key": key, "value": {"stringValue": value}}


def _otlp(question: str, doc: str, extra=None):
    sid, eid = "b7ad6b7169203331", "00f067aa0ba902b7"
    ret = {
        "openinference.span.kind": "RETRIEVER",
        "input.value": question,
        "retrieval.documents.0.document.id": doc,
        "retrieval.documents.0.document.score": 0.5,
        "retrieval.documents.0.document.content": f"text {doc}",
    }
    ret.update(extra or {})
    emb = {
        "openinference.span.kind": "EMBEDDING",
        "embedding.embeddings.0.embedding.text": question,
        "embedding.embeddings.0.embedding.vector": [0.1, 0.2],
    }

    def span(s, parent, name, start, attrs):
        d = {
            "traceId": "0af7651916cd43dd8448eb211c80319c",
            "spanId": s,
            "name": name,
            "kind": "SPAN_KIND_INTERNAL",
            "startTimeUnixNano": str(start),
            "endTimeUnixNano": str(start + 5),
            "attributes": [_kv(k, v) for k, v in attrs.items()],
            "status": {"code": "STATUS_CODE_OK"},
        }
        if parent:
            d["parentSpanId"] = parent
        return d

    spans = [
        span(sid, None, "BaseRetriever.retrieve", 10, ret),
        span(eid, sid, "BaseEmbedding.get_query_embedding", 20, emb),
    ]
    return {"resourceSpans": [{"resource": {}, "scopeSpans": [{"spans": spans}]}]}


def _tree(tmp: Path, volatile: bool = False) -> Path:
    res = tmp / "results"
    pair = {"q1": "d5", "q2": "d6", "q3": "d7", "q4": "d8"}
    for cond in ("baseline", "baseline_repeat", "fault", "restored"):
        for i in range(1, 9):
            q = f"q{i}"
            doc = pair[q] if cond == "fault" and q in pair else f"d{i}"
            extra = (
                {"llama.nonce": cond} if volatile and cond == "baseline_repeat" else {}
            )
            path = res / "otlp" / cond / f"{q}.otlp.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_otlp(f"question {q}", doc, extra)))
    (res / "schema_check.json").write_text(
        json.dumps({"traces": 32, "ok": 32, "problems": []})
    )
    (res / "stack_b_env.json").write_text(json.dumps({"packages": {}}))
    return res


def test_evaluate_pass_on_clean_tree(ev, tmp_path):
    res = _tree(tmp_path)
    out = ev.evaluate(res, diff_unchanged=lambda: (True, "same"))
    crit = out["criteria"]
    assert all(crit[k]["pass"] for k in ("S1", "S2", "S3", "S4", "S5", "S6"))
    assert crit["S2"]["value"] == "4/4" and crit["S4"]["value"] == "8/8"
    assert crit["S7"]["pass"] and out["overall"] == "PASS"
    assert out["descriptive"]["D2_vectors_dropped"] == 32
    assert (res / "imported" / "fault" / "q1.trace.jsonl").exists()


def test_evaluate_fails_on_volatile_attribute(ev, tmp_path):
    res = _tree(tmp_path, volatile=True)
    out = ev.evaluate(res, diff_unchanged=lambda: (True, "same"))
    assert not out["criteria"]["S5"]["pass"]
    assert out["overall"] == "FAIL"


def test_evaluate_fails_if_engine_changed(ev, tmp_path):
    res = _tree(tmp_path)
    out = ev.evaluate(res, diff_unchanged=lambda: (False, "changed"))
    assert not out["criteria"]["S6"]["pass"] and out["overall"] == "FAIL"


def test_write_never_overwrites(ev, tmp_path):
    res = _tree(tmp_path)
    ev.run(res, diff_unchanged=lambda: (True, "same"))
    with pytest.raises(FileExistsError):
        ev.run(res, diff_unchanged=lambda: (True, "same"))
