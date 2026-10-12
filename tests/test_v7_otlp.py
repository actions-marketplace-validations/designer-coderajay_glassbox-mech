"""glassbox.v7.otlp: OTLP JSON import/export (Experiment 8, protocol + addendum 1).

All inputs are synthetic; neither OpenTelemetry nor LlamaIndex is needed.
"""

from __future__ import annotations

import base64
import json

import pytest

from glassbox.v7 import otlp
from glassbox.v7.diff import diff_traces
from glassbox.v7.trace import Recorder, read_trace

TRACE = "0af7651916cd43dd8448eb211c80319c"
ROOT = "b7ad6b7169203331"
EMB = "00f067aa0ba902b7"
OTHER = "1111111111111111"


def _b64(hex_id: str) -> str:
    return base64.b64encode(bytes.fromhex(hex_id)).decode()


def _kv(key, value):
    if isinstance(value, bool):
        v = {"boolValue": value}
    elif isinstance(value, int):
        v = {"intValue": str(value)}
    elif isinstance(value, float):
        v = {"doubleValue": value}
    elif isinstance(value, list):
        v = {"arrayValue": {"values": [{"doubleValue": x} for x in value]}}
    else:
        v = {"stringValue": value}
    return {"key": key, "value": v}


def _span(span_id, parent, name, start, attrs, kind="SPAN_KIND_INTERNAL", status=None):
    s = {
        "traceId": TRACE,
        "spanId": span_id,
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(start),
        "endTimeUnixNano": str(start + 10),
        "attributes": [_kv(k, v) for k, v in attrs.items()],
        "status": status or {"code": "STATUS_CODE_OK"},
    }
    if parent:
        s["parentSpanId"] = parent
    return s


def _doc(doc_id="d1", score=0.5, encode=lambda x: x):
    root_attrs = {
        "openinference.span.kind": "RETRIEVER",
        "input.value": "Who shipped order 4417?",
        "retrieval.documents.0.document.id": doc_id,
        "retrieval.documents.0.document.score": score,
        "retrieval.documents.0.document.content": f"text of {doc_id}",
    }
    emb_attrs = {
        "openinference.span.kind": "EMBEDDING",
        "embedding.model_name": "bow",
        "embedding.embeddings.0.embedding.text": "Who shipped order 4417?",
        "embedding.embeddings.0.embedding.vector": [0.1, 0.2],
    }
    other = {"llama.flag": True, "llama.count": 3}
    spans = [
        _span(encode(OTHER), encode(ROOT), "Other.step", 300, other),
        _span(encode(ROOT), None, "BaseRetriever.retrieve", 100, root_attrs),
        _span(
            encode(EMB),
            encode(ROOT),
            "BaseEmbedding.get_query_embedding",
            200,
            emb_attrs,
        ),
    ]
    for s in spans:
        s["traceId"] = encode(TRACE)
    return {
        "resourceSpans": [
            {
                "resource": {"attributes": [_kv("service.name", "stack-b")]},
                "scopeSpans": [{"scope": {"name": "openinference"}, "spans": spans}],
            }
        ]
    }


def test_values_are_converted_losslessly():
    assert otlp.otlp_value({"stringValue": "x"}) == "x"
    assert otlp.otlp_value({"intValue": "7"}) == 7
    assert otlp.otlp_value({"intValue": 7}) == 7
    assert otlp.otlp_value({"doubleValue": 0.25}) == 0.25
    assert otlp.otlp_value({"boolValue": False}) is False
    arr = {"arrayValue": {"values": [{"intValue": "1"}, {"stringValue": "a"}]}}
    assert otlp.otlp_value(arr) == [1, "a"]
    assert otlp.otlp_value({"arrayValue": {}}) == []


def test_ids_accept_hex_and_base64():
    assert otlp.normalize_id(TRACE) == TRACE
    assert otlp.normalize_id(_b64(TRACE)) == TRACE
    assert otlp.normalize_id(_b64(ROOT)) == ROOT
    assert otlp.normalize_id("") is None
    with pytest.raises(ValueError):
        otlp.normalize_id("not-an-id")


def test_import_structure_order_and_mapping():
    res = otlp.import_otlp(_doc())
    spans = res.spans
    assert spans[0]["name"] == "glassbox.run"
    root = spans[0]["attributes"]
    assert root["glassbox.import.source"] == "otlp"
    assert root["glassbox.env.otlp.service.name"] == "stack-b"
    assert root["glassbox.content.policy"] == "hash_only"
    assert [s["name"] for s in spans[1:]] == [
        "BaseRetriever.retrieve",
        "BaseEmbedding.get_query_embedding",
        "Other.step",
    ]
    assert [s["attributes"]["glassbox.step.index"] for s in spans] == [0, 1, 2, 3]
    assert spans[1]["parent_span_id"] == spans[0]["span_id"]
    assert spans[2]["parent_span_id"] == ROOT and spans[3]["parent_span_id"] == ROOT
    assert spans[1]["span_id"] == ROOT and spans[1]["trace_id"] == TRACE
    assert spans[1]["attributes"]["gen_ai.operation.name"] == "retrieval"
    assert spans[2]["attributes"]["gen_ai.operation.name"] == "embeddings"
    assert "gen_ai.operation.name" not in spans[3]["attributes"]
    assert spans[1]["kind"] == "INTERNAL" and spans[1]["status"] == {"code": "OK"}
    assert spans[3]["attributes"]["llama.count"] == 3


def test_content_hashed_vectors_dropped():
    res = otlp.import_otlp(_doc())
    attrs = res.spans[1]["attributes"]
    assert "input.value" not in attrs
    assert "glassbox.content.input.value.sha256" in attrs
    assert attrs["glassbox.content.input.value.length"] == len(
        "Who shipped order 4417?"
    )
    assert "retrieval.documents.0.document.content" not in attrs
    assert attrs["retrieval.documents.0.document.id"] == "d1"
    emb = res.spans[2]["attributes"]
    assert not any(k.endswith("embedding.vector") for k in emb)
    assert "glassbox.content.embedding.embeddings.0.embedding.text.sha256" in emb
    assert res.vectors_dropped == 1
    assert res.content_hashed == 3


def test_base64_and_hex_imports_agree():
    hexed = otlp.import_otlp(_doc()).spans
    b64 = otlp.import_otlp(_doc(encode=_b64)).spans
    assert hexed[1:] == b64[1:]


def test_existing_operation_name_kept_and_policy_checked():
    data = _doc()
    sp = data["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
    sp["attributes"].append(_kv("gen_ai.operation.name", "custom"))
    assert (
        otlp.import_otlp(data).spans[1]["attributes"]["gen_ai.operation.name"]
        == "custom"
    )
    with pytest.raises(ValueError):
        otlp.import_otlp(_doc(), content_policy="full")


def test_status_and_kind_numeric_forms():
    data = _doc()
    sp = data["resourceSpans"][0]["scopeSpans"][0]["spans"][1]
    sp["status"] = {"code": 2, "message": "boom"}
    sp["kind"] = 3
    s = otlp.import_otlp(data).spans[1]
    assert s["status"]["code"] == "ERROR" and s["kind"] == "CLIENT"


def test_written_trace_is_readable_and_diff_localises(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(_doc("d1", 0.5)))
    b.write_text(json.dumps(_doc("d5", 0.3)))
    otlp.import_file(a, tmp_path / "a.trace.jsonl")
    otlp.import_file(b, tmp_path / "b.trace.jsonl")
    spans, _ = read_trace(tmp_path / "a.trace.jsonl")
    assert len(spans) == 4
    rep = diff_traces(tmp_path / "a.trace.jsonl", tmp_path / "b.trace.jsonl")
    first = rep.first_divergence
    assert first is not None and first.name_a == "BaseRetriever.retrieve"
    same = diff_traces(tmp_path / "a.trace.jsonl", tmp_path / "a.trace.jsonl")
    assert same.identical
    with pytest.raises(FileExistsError):
        otlp.import_file(a, tmp_path / "a.trace.jsonl")


def test_fidelity_problems(tmp_path):
    data = _doc()
    res = otlp.import_otlp(data)
    assert otlp.fidelity_problems(data, res) == []
    del res.spans[2]["attributes"]["embedding.model_name"]
    probs = otlp.fidelity_problems(data, res)
    assert probs and "embedding.model_name" in probs[0]
    res2 = otlp.import_otlp(data)
    res2.spans.pop()
    assert otlp.fidelity_problems(data, res2)


def _native(tmp_path):
    with Recorder(out_dir=tmp_path, run_id="q1", label="baseline") as rec:
        with rec.span(
            "retrieval",
            "kb",
            attributes={"gen_ai.retrieval.top_k": 1},
            content={"gen_ai.retrieval.query.text": "q"},
        ):
            pass
        with rec.step("parse", attributes={"x.flag": True}):
            pass
    return tmp_path / "q1.trace.jsonl"


def test_export_round_trip(tmp_path):
    path = _native(tmp_path)
    original, _ = read_trace(path)
    data = otlp.export_otlp(path)
    spans = data["resourceSpans"][0]["scopeSpans"][0]["spans"]
    assert len(spans) == len(original)
    assert all(len(s["spanId"]) == 16 and len(s["traceId"]) == 32 for s in spans)
    back = otlp.import_otlp(data).spans[1:]
    assert [s["name"] for s in back] == [s["name"] for s in original]
    assert [s["span_id"] for s in back] == [s["span_id"] for s in original]
    for o, r in zip(original, back):
        strip = lambda d: {
            k: v for k, v in d.items() if k != "glassbox.step.index"
        }  # noqa: E731
        assert strip(r["attributes"]) == strip(o["attributes"])
        assert r["parent_span_id"] == o["parent_span_id"] or o["parent_span_id"] is None


def test_export_base64_ids(tmp_path):
    path = _native(tmp_path)
    original, _ = read_trace(path)
    data = otlp.export_otlp(path, id_encoding="base64")
    spans = data["resourceSpans"][0]["scopeSpans"][0]["spans"]
    for s, o in zip(spans, original):
        assert base64.b64decode(s["spanId"]).hex() == o["span_id"]
        assert len(base64.b64decode(s["traceId"])) == 16
    with pytest.raises(ValueError):
        otlp.export_otlp(path, id_encoding="nope")
