# Glassbox V7: security and privacy of trace handling

*Version 1.0, 2026-10-12. Scope: the investigation layer (`glassbox/v7/`). It addresses V7
Hard Gate 10, "sensitive trace handling has documented controls". Every control and
every limitation below is pinned by a test in `tests/test_v7_security_controls.py`
(IDs C1–C8, L1–L2), so this document cannot drift from the code without a test failing.
Project-wide security policy, vulnerability reporting and the web API are covered in
[`SECURITY.md`](../../SECURITY.md).*

> **Not legal advice.** This document describes technical controls. Whether a given use
> of traces complies with the GDPR or other law depends on your data, purpose and
> setting. Decide that with your data-protection officer or counsel.

## 1. What a trace contains

A Glassbox trace records one run of an AI system: spans for model calls, retrieval, tool
executions and custom steps, with their attributes, status and timing (see
[`TRACE_SPEC.md`](TRACE_SPEC.md)). Sensitive data can enter a trace in three places:

1. **Content:** prompts, outputs, retrieved documents, tool arguments and results. These
   are the OTel GenAI Opt-In attributes.
2. **Attributes:** anything the instrumenting code chooses to record, such as ids, model
   names, scores and configuration.
3. **Environment:** the reproduction context on the root span.

## 2. Controls

| ID | Control | Where | Test |
|---|---|---|---|
| C1 | **Content is not stored by default.** The default policy `hash_only` keeps only a SHA-256 and a length for each content attribute. | `trace.py` `Recorder` | `test_c1_…`, plus `test_v7_trace.py::test_hash_only_is_default_and_stores_no_content` |
| C2 | **Content cannot bypass the policy.** Passing a content attribute through `attributes=` raises an error; content must use `content=`, where the policy applies. | `trace.py` | `test_c2_…` |
| C3 | **Raw content needs an explicit opt-in per run** (`content_policy="full"`), and the choice is recorded on the root span. | `trace.py` | `test_c3_…` |
| C4 | **Minimal environment capture.** Python version and platform string only; no user name or host name. | `trace.environment_attributes` | `test_c4_…` |
| C5 | **Tampering is detected.** Each trace ends with a SHA-256 of its content; `read_trace` refuses a modified file. | `trace.py` | `test_c5_…`, `test_v7_trace.py::test_tampering_is_detected` |
| C6 | **Imported third-party traces get the same treatment.** The OTLP importer accepts only `hash_only`, hashes known content keys and drops embedding vectors. | `otlp.py` | `test_c6_…`, `test_v7_otlp.py` |
| C7 | **Evidence packages are append-only and honest about status.** They are never overwritten, and `REPRODUCED` requires a named independent reproducer. | `evidence.py` | `test_c7_…` |
| C8 | **Traces are never overwritten.** | `trace.py` | `test_c8_…` |

Local only: traces are written to local disk. Glassbox does not upload them anywhere.

## 3. Limitations, stated plainly

| ID | Limitation | Consequence | Test |
|---|---|---|---|
| L1 | **`hash_only` is pseudonymisation, not anonymisation.** Hashes are unsalted SHA-256, so anyone can confirm a guess for short or predictable content (e.g. "yes", a known name, a standard prompt). | Treat `hash_only` traces as personal data whenever the underlying content was. | `test_l1_…` |
| L2 | **Redaction (`redacted` policy) is best-effort.** It only replaces e-mail addresses and two API-key patterns. Names, phone numbers, dates of birth, addresses and identifiers stay. | Do not rely on `redacted` for personal data. Use `hash_only`, or keep sensitive content out of the run. | `test_l2_…` |
| L3 | **Integrity is not truth.** A valid hash shows a file is unchanged since writing, not that the run happened as described, and it is not a digital signature. | Do not present a hash manifest as proof of correctness or authorship. | (by design) |
| L4 | **No encryption at rest and no access control.** Traces are plain JSONL files. | Protect them like the data they describe: file permissions, encrypted disks, retention limits. | (by design) |
| L5 | **Non-content attributes are stored as given.** If instrumentation puts personal data into an ordinary attribute (e.g. a user id or an e-mail in a custom key), it is stored unchanged. The OTLP importer only hashes the content keys it knows. | Review custom attribute keys before collecting traces from real users. | (by design) |
| L6 | **The platform string** can reveal OS and kernel version. | Minor fingerprinting risk; acceptable for reproduction, but noted. | — |
| L7 | **The web demo writes temporary files.** The Hugging Face investigation tab writes each run to a temporary directory that is not cleaned up automatically. It only processes the built-in synthetic incident; no user-supplied data enters it. | Do not adapt the demo to accept real data without adding cleanup and access control. | — |
| L8 | **The GitHub Action defaults to the public demo Space.** | Never send confidential or personal data through the default `api_url`; self-host instead (see `ENTERPRISE.md`). | — |

## 4. Recommended practice

1. Keep the default `hash_only` policy. Use `full` only for synthetic or public data.
2. Treat every trace from a real system as potentially personal data (L1, L5). Apply
   access control, retention limits and deletion on request.
3. Before collecting traces from production, review the attribute keys your
   instrumentation emits (L5).
4. Share evidence packages only after checking them for personal data. Packages carry
   traces as they are.
5. Report a suspected vulnerability privately, as described in `SECURITY.md`.

## 5. What this document does not claim

- That Glassbox makes trace collection GDPR-compliant.
- That hashed traces are anonymous.
- That redaction finds all personal data.
- That the controls have been reviewed by an independent security assessor; they have
  not.
