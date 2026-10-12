# Evidence package: v7-exp8-cross-stack

**Claim.** Traces written by independent instrumentation (OpenInference on the OpenTelemetry SDK) for a different framework (LlamaIndex), exported as OTLP JSON, were imported losslessly (32/32) into the common Glassbox representation, and the unchanged diff engine reached Experiment 1's conclusions on the same stale-index fault: localisation 4/4, specificity 4/4, recovery 8/8, determinism 8/8. Glassbox traces exported to OTLP JSON passed the official OTLP protobuf schema (32/32).

**Status:** `EXPERIMENTALLY_SUPPORTED` (ASSURANCE.md taxonomy)

**Scope and limits.** Pre-registered (protocol 5a5d2da, addenda 7fcc028 including a disclosed toy-corpus code smoke test, code 226a4eb). Stack B is retrieval only (no LLM call), deterministic, one framework, one injected fault, pipeline and corpus written by the author, cause known by construction. The schema check uses opentelemetry-proto 1.45.1 and is not a test against a live OTLP collector. Single author, not independently reproduced.

## Provenance

- addenda_commit: `7fcc028`
- assurance_row: `V2.10`
- code_commit: `226a4eb`
- protocol_commit: `5a5d2da`
- related_assurance_row: `V1.2 (schema check)`
- results_commit: `3f99b2b`
- stack_b: `llama-index-core 0.14.19, openinference-instrumentation-llama-index 4.6.0, opentelemetry-sdk 1.45.1`
- writeup_commit: `42b4f38`

## Contents

- `README.md`
- `artifacts/code/evaluate.py`
- `artifacts/code/otlp.py`
- `artifacts/code/subject.py`
- `artifacts/imported_baseline/q1.trace.jsonl`
- `artifacts/imported_baseline/q2.trace.jsonl`
- `artifacts/imported_baseline/q3.trace.jsonl`
- `artifacts/imported_baseline/q4.trace.jsonl`
- `artifacts/imported_baseline/q5.trace.jsonl`
- `artifacts/imported_baseline/q6.trace.jsonl`
- `artifacts/imported_baseline/q7.trace.jsonl`
- `artifacts/imported_baseline/q8.trace.jsonl`
- `artifacts/imported_baseline_repeat/q1.trace.jsonl`
- `artifacts/imported_baseline_repeat/q2.trace.jsonl`
- `artifacts/imported_baseline_repeat/q3.trace.jsonl`
- `artifacts/imported_baseline_repeat/q4.trace.jsonl`
- `artifacts/imported_baseline_repeat/q5.trace.jsonl`
- `artifacts/imported_baseline_repeat/q6.trace.jsonl`
- `artifacts/imported_baseline_repeat/q7.trace.jsonl`
- `artifacts/imported_baseline_repeat/q8.trace.jsonl`
- `artifacts/imported_fault/q1.trace.jsonl`
- `artifacts/imported_fault/q2.trace.jsonl`
- `artifacts/imported_fault/q3.trace.jsonl`
- `artifacts/imported_fault/q4.trace.jsonl`
- `artifacts/imported_fault/q5.trace.jsonl`
- `artifacts/imported_fault/q6.trace.jsonl`
- `artifacts/imported_fault/q7.trace.jsonl`
- `artifacts/imported_fault/q8.trace.jsonl`
- `artifacts/imported_restored/q1.trace.jsonl`
- `artifacts/imported_restored/q2.trace.jsonl`
- `artifacts/imported_restored/q3.trace.jsonl`
- `artifacts/imported_restored/q4.trace.jsonl`
- `artifacts/imported_restored/q5.trace.jsonl`
- `artifacts/imported_restored/q6.trace.jsonl`
- `artifacts/imported_restored/q7.trace.jsonl`
- `artifacts/imported_restored/q8.trace.jsonl`
- `artifacts/measurements/RESULTS.md`
- `artifacts/measurements/results.json`
- `artifacts/measurements/schema_check.json`
- `artifacts/measurements/stack_b_env.json`
- `artifacts/otlp_baseline/q1.otlp.json`
- `artifacts/otlp_baseline/q2.otlp.json`
- `artifacts/otlp_baseline/q3.otlp.json`
- `artifacts/otlp_baseline/q4.otlp.json`
- `artifacts/otlp_baseline/q5.otlp.json`
- `artifacts/otlp_baseline/q6.otlp.json`
- `artifacts/otlp_baseline/q7.otlp.json`
- `artifacts/otlp_baseline/q8.otlp.json`
- `artifacts/otlp_baseline_repeat/q1.otlp.json`
- `artifacts/otlp_baseline_repeat/q2.otlp.json`
- `artifacts/otlp_baseline_repeat/q3.otlp.json`
- `artifacts/otlp_baseline_repeat/q4.otlp.json`
- `artifacts/otlp_baseline_repeat/q5.otlp.json`
- `artifacts/otlp_baseline_repeat/q6.otlp.json`
- `artifacts/otlp_baseline_repeat/q7.otlp.json`
- `artifacts/otlp_baseline_repeat/q8.otlp.json`
- `artifacts/otlp_fault/q1.otlp.json`
- `artifacts/otlp_fault/q2.otlp.json`
- `artifacts/otlp_fault/q3.otlp.json`
- `artifacts/otlp_fault/q4.otlp.json`
- `artifacts/otlp_fault/q5.otlp.json`
- `artifacts/otlp_fault/q6.otlp.json`
- `artifacts/otlp_fault/q7.otlp.json`
- `artifacts/otlp_fault/q8.otlp.json`
- `artifacts/otlp_restored/q1.otlp.json`
- `artifacts/otlp_restored/q2.otlp.json`
- `artifacts/otlp_restored/q3.otlp.json`
- `artifacts/otlp_restored/q4.otlp.json`
- `artifacts/otlp_restored/q5.otlp.json`
- `artifacts/otlp_restored/q6.otlp.json`
- `artifacts/otlp_restored/q7.otlp.json`
- `artifacts/otlp_restored/q8.otlp.json`
- `artifacts/protocol/PROTOCOL.md`
- `artifacts/protocol/RUN.md`
- `claim.json`
- `provenance.json`

## Verify

`python -m glassbox.v7.evidence verify <path-to>/v7-exp8-cross-stack`

**Integrity is not truth.** a verifying manifest shows these files are unchanged since packaging; it does not show the experiment or the claim is correct.
