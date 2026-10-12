# V7 Experiment 8: the same investigation on a second, independently instrumented stack. RESULTS

*Provenance, in commit order:*
- Protocol v1.0: `5a5d2da`, committed before any code.
- Addenda 1–2 (importer details; disclosed toy-corpus smoke test): `7fcc028`.
- Code (`glassbox/v7/otlp.py`, `subject.py`, `evaluate.py`, tests): `226a4eb`.
- Run on the owner's Mac on 2026-10-12, after `226a4eb`.

`results/` is committed unchanged:
- `results.json`, sha256 `014992cc…af7ef4`;
- `schema_check.json`, sha256 `a197585b…a4b5cb`.

## Outcome: **PASS** (Hard Gate 2 met for the tested scope)

| Criterion | Result |
|---|---|
| S1 Import fidelity | 32/32 OTLP files imported with no fidelity problems: **PASS** |
| S2 Localisation (`fault` vs `baseline`, affected) | 4/4 first divergence at the step aligned as `retrieval`: **PASS** |
| S3 Specificity (unaffected) | 4/4: **PASS** |
| S4 Recovery (`restored` vs `baseline`) | 8/8 no divergence: **PASS** |
| S5 Determinism (`baseline_repeat` vs `baseline`) | 8/8 no divergence: **PASS** |
| S6 Engine unchanged | `glassbox/v7/diff.py` sha256 `d00da8d5…80227d` at the protocol commit and at the run: **PASS** |
| S7 OTLP schema (for V1.1) | 32/32 Experiment 1 traces exported, parsed by `google.protobuf.json_format` into `ExportTraceServiceRequest` (unknown fields rejected), with correct 16/8-byte ids, and round-tripped: **PASS** |

## Stack B as run

| Package | Version | Licence (from package metadata) |
|---|---|---|
| llama-index-core | 0.14.19 | MIT |
| openinference-instrumentation-llama-index | 4.6.0 | Apache-2.0 |
| opentelemetry-sdk / -exporter-otlp-proto-common / -proto | 1.45.1 | Apache-2.0 |
| protobuf | 7.36.2 | BSD-3-Clause |

Python 3.11.9, macOS arm64 (`results/stack_b_env.json`).

## Descriptive

- **D1: what OpenInference emitted.** Each of the 32 queries produced 4 spans:
  - `VectorIndexRetriever.retrieve` and `VectorIndexRetriever._retrieve` (both
    RETRIEVER);
  - `BowEmbedding.get_query_embedding` and `BowEmbedding._get_query_embedding` (both
    EMBEDDING).

  Span names, nesting and attribute keys came from the instrumentation, not from
  Glassbox.
- **D2:** 32 embedding vectors were dropped by the importer, as specified.
- **D3:** stack B retrieved the same document as Experiment 1's stack A in 32/32
  (condition, question) pairs.

## What this shows

- Traces written by **independent, standard instrumentation** (OpenInference on the
  OpenTelemetry SDK) for a **different framework** (LlamaIndex) were imported into the
  common Glassbox representation, with every non-content attribute kept, every content
  attribute hashed and vectors dropped.
- The **unchanged** diff engine reached Experiment 1's conclusions on the same injected
  fault: localisation, specificity, recovery and determinism.
- Glassbox's own traces export to OTLP JSON that the official OTLP protobuf schema
  accepts, and the export round-trips.

## What it does not show

- **Scope of the stacks:** other frameworks or languages (LangChain, Java, hosted APIs),
  or other OpenInference versions with different attribute keys.
- **Model and noise:** any LLM call in stack B (retrieval only) and any sampling noise
  (stack B is deterministic).
- **Analyses not run on stack B:** interventions or group diff.
- **Live export:** sending to a running OTLP collector. S7 is a schema-level check, so
  ASSURANCE V1.1 keeps its live-collector part open.
- **Unknown causes** (Hard Gate 3).

The fault, the corpus and stack B's pipeline code were written by the author, and the
cause was known by construction. A toy-corpus smoke test of the code was run and
disclosed before the run (Addendum 2). Nothing has been reproduced independently.
