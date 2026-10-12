#!/usr/bin/env python3
"""Stack B for V7 Experiment 8 (see PROTOCOL.md): a LlamaIndex retrieval pipeline whose
traces are written by OpenInference's auto-instrumentation on the OpenTelemetry SDK and
exported as OTLP JSON. Glassbox code does not run inside the pipeline.

Runs in its own venv (see RUN.md) with only the pinned stack-B packages. LlamaIndex and
OpenTelemetry are imported inside functions, so the pure helpers (tokeniser,
vocabulary, conditions) can be tested without them.

Usage:
    python subject.py record --out experiments/v7/cross_stack/results
    python subject.py schema-check --out experiments/v7/cross_stack/results
"""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import math
import platform
import re
import sys
import types
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[3]
CORPUS = REPO / "experiments" / "v7" / "rag_fault" / "corpus.json"
EXP1_TRACES = REPO / "experiments" / "v7" / "rag_fault" / "results"
CONDITIONS = ("baseline", "baseline_repeat", "fault", "restored")
FAULT_EXCLUDED = frozenset({"d1", "d2", "d3", "d4"})
TOP_K = 1
SERVICE = "glassbox-exp8-stack-b"
PACKAGES = (
    "llama-index-core",
    "openinference-instrumentation-llama-index",
    "opentelemetry-sdk",
    "opentelemetry-exporter-otlp-proto-common",
    "opentelemetry-proto",
    "protobuf",
)
#: Same stopwords and regular expression as Experiment 1 (Addendum 1, item 5).
STOPWORDS = frozenset(
    "a an the of in on at by for from is was which who what where when to every".split()
)

Doc = Dict[str, str]


def tokenize(text: str) -> List[str]:
    """Lower-case word tokens without stopwords (Experiment 1's tokeniser)."""
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


def load_corpus() -> Tuple[List[Doc], List[Doc]]:
    """Experiment 1's documents and questions, unchanged."""
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    return data["documents"], data["questions"]


def build_vocab(docs: Sequence[Doc]) -> List[str]:
    """Sorted vocabulary of the full corpus (fixed across conditions)."""
    return sorted({t for d in docs for t in tokenize(d["text"])})


def bow_vector(text: str, vocab: Sequence[str]) -> List[float]:
    """L2-normalised bag-of-words vector over ``vocab``."""
    counts = Counter(tokenize(text))
    vec = [float(counts.get(t, 0)) for t in vocab]
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm else vec


def condition_docs(docs: Sequence[Doc], condition: str) -> List[Doc]:
    """Documents indexed under ``condition`` (``fault`` drops d1–d4)."""
    if condition == "fault":
        return [d for d in docs if d["id"] not in FAULT_EXCLUDED]
    return list(docs)


# --- stack B (needs the stack-B venv) ---------------------------------------------


def _embedding_class() -> Any:
    from llama_index.core.embeddings import BaseEmbedding

    class BowEmbedding(BaseEmbedding):  # type: ignore[misc]
        """Deterministic bag-of-words embedding; no network, no model download."""

        vocab: List[str] = []

        def _get_query_embedding(self, query: str) -> List[float]:
            return bow_vector(query, self.vocab)

        async def _aget_query_embedding(self, query: str) -> List[float]:
            return bow_vector(query, self.vocab)

        def _get_text_embedding(self, text: str) -> List[float]:
            return bow_vector(text, self.vocab)

    BowEmbedding.model_rebuild(_types_namespace={"List": List})
    return BowEmbedding


def _retrievers(docs: Sequence[Doc]) -> Dict[str, Any]:
    """One retriever per condition; every index is built before tracing starts."""
    from llama_index.core import Settings, VectorStoreIndex
    from llama_index.core.schema import TextNode

    emb = _embedding_class()(model_name="glassbox-bow", vocab=build_vocab(docs))
    Settings.embed_model = emb
    out = {}
    for cond in CONDITIONS:
        nodes = [
            TextNode(id_=d["id"], text=d["text"]) for d in condition_docs(docs, cond)
        ]
        index = VectorStoreIndex(nodes=nodes, embed_model=emb)
        out[cond] = index.as_retriever(similarity_top_k=TOP_K)
    return out


def _environment() -> Dict[str, Any]:
    pkgs = {}
    for name in PACKAGES:
        try:
            meta = importlib.metadata.metadata(name)
            pkgs[name] = {
                "version": importlib.metadata.version(name),
                "license": meta.get("License-Expression") or meta.get("License"),
            }
        except importlib.metadata.PackageNotFoundError:
            pkgs[name] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": pkgs,
    }


def record(out: Path) -> int:
    """Trace every (condition, question) query and write one OTLP JSON file each."""
    from google.protobuf.json_format import MessageToJson
    from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
    from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    docs, questions = load_corpus()
    retrievers = _retrievers(docs)
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    LlamaIndexInstrumentor().instrument(tracer_provider=provider)
    for cond in CONDITIONS:
        for q in questions:
            exporter.clear()
            retrievers[cond].retrieve(q["question"])
            req = encode_spans(exporter.get_finished_spans())
            target = out / "otlp" / cond / f"{q['id']}.otlp.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "x", encoding="utf-8") as fh:
                fh.write(MessageToJson(req, indent=1) + "\n")
    with open(out / "stack_b_env.json", "x", encoding="utf-8") as fh:
        fh.write(json.dumps(_environment(), indent=1) + "\n")
    sys.stdout.write(f"recorded {len(CONDITIONS) * len(questions)} OTLP files\n")
    return 0


def _load_glassbox_modules() -> Tuple[types.ModuleType, types.ModuleType]:
    """Load trace.py and otlp.py by path, without importing the glassbox package."""
    for name in ("glassbox", "glassbox.v7"):
        if name not in sys.modules:
            pkg = types.ModuleType(name)
            pkg.__path__ = []
            sys.modules[name] = pkg
    mods = []
    for name in ("trace", "otlp"):
        spec = importlib.util.spec_from_file_location(
            f"glassbox.v7.{name}", REPO / "glassbox" / "v7" / f"{name}.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        mods.append(module)
    return mods[0], mods[1]


def _check_one(path: Path, trace: Any, otlp: Any) -> List[str]:
    from google.protobuf.json_format import Parse
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
        ExportTraceServiceRequest,
    )

    problems = []
    original, _ = trace.read_trace(path)
    b64 = otlp.export_otlp(path, id_encoding="base64")
    msg = Parse(
        json.dumps(b64), ExportTraceServiceRequest(), ignore_unknown_fields=False
    )
    parsed = [s for rs in msg.resource_spans for ss in rs.scope_spans for s in ss.spans]
    for p, o in zip(parsed, original):
        if (
            len(p.trace_id) != 16
            or len(p.span_id) != 8
            or p.span_id.hex() != o["span_id"]
        ):
            problems.append(f"{path.name}: id mismatch in {o['name']}")
    if len(parsed) != len(original):
        problems.append(f"{path.name}: span count {len(parsed)} != {len(original)}")
    back = otlp.import_otlp(otlp.export_otlp(path)).spans[1:]
    for b, o in zip(back, original):
        strip = {k: v for k, v in o["attributes"].items() if k != "glassbox.step.index"}
        got = {k: v for k, v in b["attributes"].items() if k != "glassbox.step.index"}
        if b["name"] != o["name"] or b["span_id"] != o["span_id"] or got != strip:
            problems.append(f"{path.name}: round trip changed {o['name']}")
    return problems


def schema_check(out: Path) -> int:
    """S7: every Experiment 1 trace exported to OTLP parses with the official schema."""
    trace, otlp = _load_glassbox_modules()
    paths = sorted(EXP1_TRACES.glob("*/*.trace.jsonl"))
    problems: List[str] = []
    ok = 0
    for path in paths:
        found = _check_one(path, trace, otlp)
        problems.extend(found)
        ok += not found
    result = {"traces": len(paths), "ok": ok, "problems": problems}
    with open(out / "schema_check.json", "x", encoding="utf-8") as fh:
        fh.write(json.dumps(result, indent=1) + "\n")
    sys.stdout.write(f"schema check: {ok}/{len(paths)} ok\n")
    return 0 if ok == len(paths) else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="V7 Experiment 8, stack B")
    parser.add_argument("command", choices=("record", "schema-check"))
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    return record(args.out) if args.command == "record" else schema_check(args.out)


if __name__ == "__main__":
    sys.exit(main())
