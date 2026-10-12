# V7 Experiment 8: the same investigation on a second, independently instrumented stack (Hard Gate 2)

*Protocol v1.0. Written 2026-10-12, BEFORE any Experiment 8 code and before any run.
It is committed first and not changed afterwards. Deviations go in dated addenda below
the line.*

## 0. Question and hard gate

**V7 Hard Gate 2:** "At least two substantially different execution stacks can be
compared through the common representation."

So far every Glassbox trace has been written by Glassbox's own `Recorder`. This
experiment asks whether traces produced by **someone else's instrumentation**, in the
**standard OpenTelemetry format**, can be brought into the common Glassbox
representation and investigated with the **unchanged** diff engine, reaching the same
conclusions as Experiment 1 on the same injected fault.

It also tests ASSURANCE V1.1 (Glassbox traces are OTLP-compatible) at the level of the
official OTLP protobuf schema.

## 1. The two stacks

| | Stack A (reference) | Stack B (new) |
|---|---|---|
| **Pipeline code** | Experiment 1's own Python RAG (`experiments/v7/rag_fault/`) | A LlamaIndex pipeline written for this experiment (`subject.py`): `VectorStoreIndex` + retriever, using `llama-index-core` |
| **Who writes the trace** | Glassbox `Recorder` | **Third-party auto-instrumentation:** OpenInference `LlamaIndexInstrumentor` (Apache-2.0) on the OpenTelemetry Python SDK. Glassbox code does **not** run inside stack B. |
| **Trace format** | Glassbox JSONL | **OTLP JSON** (`ExportTraceServiceRequest`), encoded with the official OpenTelemetry encoder and `google.protobuf.json_format` |
| **How Glassbox reads it** | Directly | Through a new importer, `glassbox/v7/otlp.py` (stdlib only) |

Span names, nesting and attribute keys in stack B are chosen by OpenInference and
LlamaIndex, not by the author. That is what makes the stack "substantially different".

**Pinned versions,** in a separate venv outside the repository:
- `llama-index-core==0.14.19`;
- `openinference-instrumentation-llama-index==4.6.0`;
- `opentelemetry-sdk==1.45.1`;
- `opentelemetry-exporter-otlp-proto-common==1.45.1`;
- `opentelemetry-proto==1.45.1`.

If these cannot be installed together, the resolved versions are recorded in an addendum
**before** the run. Licences are checked at install and recorded in RUN.md.

## 2. System and fault (same as Experiment 1)

- **Corpus and questions:** Experiment 1's `corpus.json`, unchanged (8 fictional
  documents, 8 questions).
- **Embedding:** a deterministic bag-of-words embedding implemented as a LlamaIndex
  `BaseEmbedding` subclass. It uses the same lower-cased tokenisation as Experiment 1's
  retriever, over a fixed vocabulary built from the full corpus. No network, no model
  download.
- **Retrieval:** `similarity_top_k = 1`.
- **Stack B makes no LLM call.** The behaviour measured is retrieval. This is narrower
  than Experiment 1, which also scored answers with GPT-2.
- **Conditions:**
  - `baseline`: index over all 8 documents.
  - `baseline_repeat`: the same, rebuilt (tests determinism).
  - `fault`: stale index, d1–d4 missing.
  - `restored`: all 8 again.

  Questions about d1–d4 are **affected**; questions about d5–d8 are **unaffected**.
- **Trace scope:** only the query (`retriever.retrieve(question)`) is traced, once per
  (condition, question), giving 32 OTLP files. Index building happens before
  instrumentation is attached, as Experiment 1 treats the index as configuration.

## 3. The importer (`glassbox/v7/otlp.py`): fixed mapping

1. **Parse.** Read OTLP JSON: `resourceSpans → scopeSpans → spans`.
2. **Order and link.** Order spans depth-first from the root, with siblings by
   `startTimeUnixNano` and then `spanId`. Keep `traceId`, `spanId` and `parentSpanId`
   as fields, not attributes. Set `glassbox.step.index` from that order.
3. **Attributes.** Convert OTLP typed values (`stringValue`, `intValue`, `doubleValue`,
   `boolValue`, `arrayValue`) to plain JSON values, losslessly.
4. **Operation name** (alignment key for the diff), from `openinference.span.kind`:
   - `RETRIEVER` → `retrieval`
   - `EMBEDDING` → `embeddings`
   - `LLM` → `chat`
   - `TOOL` → `execute_tool`
   - otherwise unset, so the span aligns by its name.

   An existing `gen_ai.operation.name` is never overwritten.
5. **Content policy `hash_only`.** Attribute values whose key matches a fixed list of
   content patterns are replaced by `glassbox.content.<key>.sha256` and `.len`, in the
   form the diff engine already understands:
   - `input.value`, `output.value`;
   - `*.document.content`;
   - `llm.input_messages.*`, `llm.output_messages.*`;
   - `embedding.embeddings.*.embedding.text`.

   **Embedding vectors** (`*.embedding.vector`) are dropped and counted.
6. **Status.** The OTLP status code maps to Glassbox `UNSET`/`OK`/`ERROR`.
7. **Output.** A normal Glassbox JSONL trace with its integrity summary, readable by
   `read_trace`.

The importer also has the reverse direction, **export**: a Glassbox trace to OTLP JSON.
That is used only for S7.

## 4. Pre-declared criteria

Traces are compared with **`glassbox.v7.diff.diff_traces`, unchanged**, per question,
against `baseline`.

| ID | Criterion | Pass rule |
|---|---|---|
| S1 Import fidelity | For each of the 32 OTLP files, the imported trace has the same span count and the same span/parent ids. Every non-content, non-vector attribute is present with an equal value. Every content attribute is present as a hash. | 32/32 |
| S2 Localisation | `fault` vs `baseline`: first divergence at the step aligned as `retrieval` | 4/4 affected |
| S3 Specificity | `fault` vs `baseline`: if the retrieved document is unchanged, no divergence; if it changed, the first divergence is at `retrieval` | 4/4 unaffected |
| S4 Recovery | `restored` vs `baseline`: no divergence | 8/8 |
| S5 Determinism | `baseline_repeat` vs `baseline`: no divergence | 8/8 |
| S6 Engine unchanged | `glassbox/v7/diff.py` is byte-identical (sha256) between this protocol's commit and the run | yes |
| S7 OTLP schema (for V1.1) | Every Experiment 1 Glassbox trace exported by `otlp.py` parses with `json_format.Parse(…, ExportTraceServiceRequest(), ignore_unknown_fields=False)`; re-importing it gives the same span structure and attributes | 32/32 |

**Overall result for Hard Gate 2: PASS iff S1–S6 all pass.**
- S7 decides only ASSURANCE V1.1. It checks the official OTLP schema; it does **not**
  test sending to a running collector.
- **Descriptive (not gated):**
  - D1: span names and kinds that OpenInference emitted;
  - D2: number of vector attributes dropped;
  - D3: whether stacks A and B retrieve the same document per (condition, question).
    The embeddings differ (BoW cosine in both, but the implementations differ), so
    agreement is reported, not required.

**Failure handling.** If a volatile attribute makes S3–S5 fail (for example, a value
that changes on every call), that is a **FAIL** of this protocol. A fix to the importer's
mapping would need a new addendum and a re-run, reported as such.

## 5. What a PASS would and would not show

**Would show:**
- Traces written by independent, standard instrumentation (OpenInference on
  OpenTelemetry) for a different framework can be imported losslessly into Glassbox.
- The unchanged diff engine reaches Experiment 1's conclusions on the same injected
  fault: localisation, specificity, recovery and determinism.

**Would not show:**
- other frameworks or languages (LangChain, Java, hosted APIs);
- traces with LLM generation in stack B;
- sampling noise (stack B is deterministic);
- interventions or group diff on stack B;
- unknown causes (Hard Gate 3);
- export to a live OTLP collector;
- that every OpenInference version keeps the same attribute keys.

The fault and stack B's pipeline code are written by the author, and the cause is known
by construction.

## 6. Execution

1. Commit this protocol.
2. Implement `glassbox/v7/otlp.py`, `subject.py`, `evaluate.py` and `RUN.md`
   test-first. Tests use synthetic OTLP JSON and need neither LlamaIndex nor
   OpenTelemetry. Commit them.
3. Run on the owner's Mac, as documented in `RUN.md`. Stack B runs in its own venv;
   evaluation runs in the main environment.
4. Commit `results/` (OTLP files, imported traces, `results.json`) unchanged, whether
   PASS or FAIL.

---
*(Addenda, if any, go below this line, with dates.)*
