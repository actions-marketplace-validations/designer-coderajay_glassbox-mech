# Evidence package: v7-exp10-benchmark

**Claim.** On a pre-registered benchmark of 32 known-cause incidents generated from a sealed seed (GPT-2 small RAG and a synthetic tool-using agent; 192 units, 28 positive), Glassbox interventions diagnosed the exact set of large causes in 21/28 positive units (0.75; first-divergence baseline 0.50, revert-all baseline 0.00), blamed 1/299 zero-effect factors, raised 1/48 false alarms on negative controls, and its implied fix was verified in 20/24 detected units. All five pre-declared criteria K1-K5 PASS; Hard Gate 11 met.

**Status:** `EXPERIMENTALLY_SUPPORTED` (ASSURANCE.md taxonomy)

**Scope and limits.** Pre-registered (protocol 5328a2b, addendum 379f8ee with the sealed seed hash, code 416262f). Only 28 positive units, 26 of them from the GPT-2 RAG family; units share incidents and two factor sets were drawn twice, so Wilson intervals overstate precision; K1 interval 0.57-0.87. Four positive units whose co-changes cancelled at the outcome were missed; small effects were diagnosed exactly in 10/39 units. Factor pools, families and generator designed by the author; baselines are automated stand-ins, not human engineers; causes come from a known pool, so this is not blind diagnosis (Gate 3). Single author, one machine, one run, not independently reproduced.

## Provenance

- addendum_commit: `379f8ee`
- assurance_row: `V10.1`
- code_commit: `416262f`
- model: `GPT-2 small (TransformerLens), CPU`
- protocol_commit: `5328a2b`
- related_assurance_rows: `V10 (Gate 11), V6`
- results_commit: `1a0e13a`
- sealed_seed_sha256: `7dff29241343a904eda8c01a9e49790b3cbd988f1cad6e756a5638a1d79b3742`
- writeup_commit: `d2cf7ed`

## Contents

- `README.md`
- `artifacts/code/demo_rag.py`
- `artifacts/code/families.py`
- `artifacts/code/generate.py`
- `artifacts/code/intervene.py`
- `artifacts/code/methods.py`
- `artifacts/code/run.py`
- `artifacts/code/score.py`
- `artifacts/measurements/RESULTS.md`
- `artifacts/measurements/results.json`
- `artifacts/protocol/PROTOCOL.md`
- `artifacts/tests/test_v7_benchmark.py`
- `claim.json`
- `provenance.json`

## Verify

`python -m glassbox.v7.evidence verify <path-to>/v7-exp10-benchmark`

**Integrity is not truth.** a verifying manifest shows these files are unchanged since packaging; it does not show the experiment or the claim is correct.
