# SPDX-License-Identifier: BUSL-1.1
# Copyright (C) 2026 Ajay Pravin Mahale <mahale.ajay01@gmail.com>
# Licensed under the Business Source License 1.1 (see LICENSE-COMMERCIAL).
# Free for non-production use and for production use inside your own organisation.
# Offering it as a commercial service or product to third parties needs a license.
"""OTLP JSON import and export for Glassbox traces (V7 Experiment 8, Hard Gate 2).

Import turns spans written by any OpenTelemetry instrumentation (for example
OpenInference on the OpenTelemetry SDK) into a normal Glassbox trace that
:func:`glassbox.v7.diff.diff_traces` reads unchanged. The mapping is fixed by
``experiments/v7/cross_stack/PROTOCOL.md`` §3 and Addendum 1:

* spans are wrapped under a synthetic ``glassbox.run`` root (resource attributes become
  ``glassbox.env.otlp.<key>``) and ordered depth-first, siblings by start time;
* typed OTLP values become plain JSON values;
* ``openinference.span.kind`` sets ``gen_ai.operation.name`` unless one is present;
* content attributes are replaced by ``glassbox.content.<key>.sha256``/``.length``
  (policy ``hash_only``); embedding vectors are dropped and counted;
* span ids are accepted as hex (OTLP/JSON) or base64 (protobuf JSON mapping).

Export writes a Glassbox trace as an OTLP ``ExportTraceServiceRequest`` in JSON.

Standard library only.
"""

from __future__ import annotations

import base64
import binascii
import fnmatch
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from glassbox.v7.trace import SCHEMA, _content_length, _sha256_text, canonical_json

PathLike = Union[str, Path]
Span = Dict[str, Any]

CONTENT_PATTERNS = (
    "input.value",
    "output.value",
    "*.document.content",
    "llm.input_messages.*",
    "llm.output_messages.*",
    "embedding.embeddings.*.embedding.text",
)
VECTOR_PATTERNS = ("*.embedding.vector",)
KIND_TO_OPERATION = {
    "RETRIEVER": "retrieval",
    "EMBEDDING": "embeddings",
    "LLM": "chat",
    "TOOL": "execute_tool",
}
_SPAN_KINDS = ("UNSPECIFIED", "INTERNAL", "SERVER", "CLIENT", "PRODUCER", "CONSUMER")
_STATUS = ("UNSET", "OK", "ERROR")


@dataclass
class ImportResult:
    """Imported spans (synthetic root first) and what the content policy did."""

    spans: List[Span]
    otlp_span_count: int
    vectors_dropped: int
    content_hashed: int


def otlp_value(value: Dict[str, Any]) -> Any:
    """Convert one OTLP ``AnyValue`` to a plain JSON value."""
    if "stringValue" in value:
        return value["stringValue"]
    if "boolValue" in value:
        return bool(value["boolValue"])
    if "intValue" in value:
        return int(value["intValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "arrayValue" in value:
        return [otlp_value(v) for v in value["arrayValue"].get("values", [])]
    if "kvlistValue" in value:
        return {
            kv["key"]: otlp_value(kv.get("value", {}))
            for kv in value["kvlistValue"].get("values", [])
        }
    if "bytesValue" in value:
        return value["bytesValue"]
    return None


def normalize_id(raw: Optional[str]) -> Optional[str]:
    """Hex form of a trace/span id given as hex (32/16 chars) or base64 (24/12).

    Raises:
        ValueError: If the value is neither.
    """
    if not raw:
        return None
    if len(raw) in (16, 32):
        try:
            bytes.fromhex(raw)
            return raw.lower()
        except ValueError:
            pass
    if len(raw) in (12, 24):
        try:
            return base64.b64decode(raw, validate=True).hex()
        except (binascii.Error, ValueError):
            pass
    raise ValueError(f"not a hex or base64 OTLP id: {raw!r}")


def _matches(key: str, patterns: Tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(key, p) for p in patterns)


def _kind(raw: Any) -> str:
    if isinstance(raw, int):
        return _SPAN_KINDS[raw] if 0 <= raw < len(_SPAN_KINDS) else "UNSPECIFIED"
    return str(raw or "SPAN_KIND_UNSPECIFIED").replace("SPAN_KIND_", "")


def _status(raw: Optional[Dict[str, Any]]) -> Dict[str, str]:
    raw = raw or {}
    code = raw.get("code", 0)
    if isinstance(code, int):
        name = _STATUS[code] if 0 <= code < len(_STATUS) else "UNSET"
    else:
        name = str(code).replace("STATUS_CODE_", "")
    out = {"code": name}
    if raw.get("message"):
        out["message"] = str(raw["message"])
    return out


def _attributes(raw: List[Dict[str, Any]], counts: Dict[str, int]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for kv in raw:
        key, val = kv["key"], otlp_value(kv.get("value", {}))
        if _matches(key, VECTOR_PATTERNS):
            counts["vectors"] += 1
        elif _matches(key, CONTENT_PATTERNS):
            counts["content"] += 1
            out[f"glassbox.content.{key}.sha256"] = _sha256_text(canonical_json(val))
            out[f"glassbox.content.{key}.length"] = _content_length(val)
        else:
            out[key] = val
    kind = out.get("openinference.span.kind")
    if kind in KIND_TO_OPERATION and "gen_ai.operation.name" not in out:
        out["gen_ai.operation.name"] = KIND_TO_OPERATION[kind]
    return out


def _flat_spans(data: Dict[str, Any]) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """``(resource_attributes_raw, span)`` for every span in the request."""
    out = []
    for rs in data.get("resourceSpans", []):
        res = rs.get("resource", {}).get("attributes", [])
        for ss in rs.get("scopeSpans", []):
            out.extend((res, sp) for sp in ss.get("spans", []))
    return out


def _convert(sp: Dict[str, Any], counts: Dict[str, int]) -> Span:
    return {
        "trace_id": normalize_id(sp.get("traceId")),
        "span_id": normalize_id(sp.get("spanId")),
        "parent_span_id": normalize_id(sp.get("parentSpanId")),
        "name": sp.get("name", ""),
        "kind": _kind(sp.get("kind")),
        "start_time_unix_nano": int(sp.get("startTimeUnixNano", 0)),
        "end_time_unix_nano": int(sp.get("endTimeUnixNano", 0)),
        "status": _status(sp.get("status")),
        "attributes": _attributes(sp.get("attributes", []), counts),
    }


def _depth_first(spans: List[Span], root_id: str) -> List[Span]:
    """Re-parent orphans to the synthetic root and order depth-first."""
    ids = {s["span_id"] for s in spans}
    children: Dict[str, List[Span]] = {}
    for s in spans:
        parent = s["parent_span_id"] if s["parent_span_id"] in ids else root_id
        s["parent_span_id"] = parent
        children.setdefault(parent, []).append(s)
    return _emit(children, root_id)


def _emit(children: Dict[str, List[Span]], node: str) -> List[Span]:
    out: List[Span] = []
    kids = sorted(
        children.get(node, []), key=lambda s: (s["start_time_unix_nano"], s["span_id"])
    )
    for kid in kids:
        out.append(kid)
        out.extend(_emit(children, kid["span_id"]))
    return out


def import_otlp(
    data: Dict[str, Any], content_policy: str = "hash_only"
) -> ImportResult:
    """Convert an OTLP JSON request into Glassbox spans (synthetic root first).

    Raises:
        ValueError: If ``content_policy`` is not ``"hash_only"``.
    """
    if content_policy != "hash_only":
        raise ValueError("only content_policy='hash_only' is supported for import")
    counts = {"vectors": 0, "content": 0}
    flat = _flat_spans(data)
    spans = [_convert(sp, counts) for _, sp in flat]
    trace_id = spans[0]["trace_id"] if spans else "0" * 32
    root_id = hashlib.sha256(f"glassbox.run:{trace_id}".encode()).hexdigest()[:16]
    root_attrs: Dict[str, Any] = {
        "glassbox.trace.schema": SCHEMA,
        "glassbox.content.policy": content_policy,
        "glassbox.import.source": "otlp",
    }
    if flat:
        for kv in flat[0][0]:
            root_attrs[f"glassbox.env.otlp.{kv['key']}"] = otlp_value(
                kv.get("value", {})
            )
    ordered = _depth_first(spans, root_id)
    root: Span = {
        "trace_id": trace_id,
        "span_id": root_id,
        "parent_span_id": None,
        "name": "glassbox.run",
        "kind": "INTERNAL",
        "start_time_unix_nano": min(
            (s["start_time_unix_nano"] for s in spans), default=0
        ),
        "end_time_unix_nano": max((s["end_time_unix_nano"] for s in spans), default=0),
        "status": {"code": "OK"},
        "attributes": root_attrs,
    }
    result = [root] + ordered
    for i, s in enumerate(result):
        s["attributes"]["glassbox.step.index"] = i
    return ImportResult(result, len(spans), counts["vectors"], counts["content"])


def write_trace(spans: List[Span], path: PathLike) -> Path:
    """Write spans as a Glassbox JSONL trace with its integrity summary (never overwrites)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(canonical_json(s) + "\n" for s in spans)
    summary = {
        "glassbox.trace.summary": {
            "schema": SCHEMA,
            "span_count": len(spans),
            "sha256": _sha256_text(body),
        }
    }
    with open(target, "x", encoding="utf-8") as fh:
        fh.write(body + canonical_json(summary) + "\n")
    return target


def import_file(src: PathLike, dst: PathLike) -> ImportResult:
    """Import one OTLP JSON file and write the Glassbox trace to ``dst``.

    Raises:
        FileExistsError: If ``dst`` exists.
    """
    if Path(dst).exists():
        raise FileExistsError(f"{dst} exists; traces are never overwritten")
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    result = import_otlp(data)
    write_trace(result.spans, dst)
    return result


def _expected(key: str, value: Any, attrs: Dict[str, Any]) -> Optional[str]:
    if _matches(key, VECTOR_PATTERNS):
        return None if not any(k == key for k in attrs) else f"{key}: vector kept"
    if _matches(key, CONTENT_PATTERNS):
        want = _sha256_text(canonical_json(value))
        got = attrs.get(f"glassbox.content.{key}.sha256")
        return None if got == want else f"{key}: content hash missing or wrong"
    if key not in attrs or attrs[key] != value:
        return f"{key}: missing or changed"
    return None


def fidelity_problems(data: Dict[str, Any], result: ImportResult) -> List[str]:
    """Differences between an OTLP request and its import (empty list = faithful)."""
    flat = _flat_spans(data)
    imported = {s["span_id"]: s for s in result.spans[1:]}
    problems: List[str] = []
    if len(result.spans) - 1 != len(flat):
        problems.append(f"span count {len(result.spans) - 1} != {len(flat)}")
    for _, sp in flat:
        sid = normalize_id(sp.get("spanId"))
        got = imported.get(sid or "")
        if got is None:
            problems.append(f"span {sid} missing")
            continue
        if got["name"] != sp.get("name", ""):
            problems.append(f"span {sid}: name changed")
        for kv in sp.get("attributes", []):
            issue = _expected(
                kv["key"], otlp_value(kv.get("value", {})), got["attributes"]
            )
            if issue:
                problems.append(f"span {sid}: {issue}")
    return problems


def _any_value(value: Any) -> Dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, (list, tuple)):
        return {"arrayValue": {"values": [_any_value(v) for v in value]}}
    if isinstance(value, dict):
        return {"stringValue": canonical_json(value)}
    return {"stringValue": str(value)}


def _encode_id(hex_id: str, id_encoding: str) -> str:
    return (
        hex_id
        if id_encoding == "hex"
        else base64.b64encode(bytes.fromhex(hex_id)).decode()
    )


def export_otlp(path: PathLike, id_encoding: str = "hex") -> Dict[str, Any]:
    """A Glassbox trace as an OTLP ``ExportTraceServiceRequest`` JSON object.

    Args:
        path: Glassbox trace file (integrity-checked on read).
        id_encoding: ``"hex"`` (OTLP/JSON specification) or ``"base64"`` (protobuf
            JSON mapping, as ``google.protobuf.json_format`` expects).

    Raises:
        ValueError: If ``id_encoding`` is unknown.
    """
    if id_encoding not in ("hex", "base64"):
        raise ValueError("id_encoding must be 'hex' or 'base64'")
    from glassbox.v7.trace import read_trace

    spans, _ = read_trace(path)
    out = []
    for s in spans:
        sp: Dict[str, Any] = {
            "traceId": _encode_id(s["trace_id"], id_encoding),
            "spanId": _encode_id(s["span_id"], id_encoding),
            "name": s["name"],
            "kind": f"SPAN_KIND_{s.get('kind', 'INTERNAL')}",
            "startTimeUnixNano": str(s["start_time_unix_nano"]),
            "endTimeUnixNano": str(s["end_time_unix_nano"]),
            "attributes": [
                {"key": k, "value": _any_value(v)}
                for k, v in s["attributes"].items()
                if v is not None
            ],
            "status": {"code": f"STATUS_CODE_{s['status'].get('code', 'UNSET')}"},
        }
        if s.get("parent_span_id"):
            sp["parentSpanId"] = _encode_id(s["parent_span_id"], id_encoding)
        out.append(sp)
    scope = {"scope": {"name": "glassbox.v7"}, "spans": out}
    return {"resourceSpans": [{"resource": {"attributes": []}, "scopeSpans": [scope]}]}
