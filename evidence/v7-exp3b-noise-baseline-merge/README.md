# Evidence package: v7-exp3b-noise-baseline-merge

**Claim.** With redundant fields merged, the group diff localised a single injected change at the right step in 0.875 of replications at N = 30 (threshold 0.80) and kept false alarms at or below 0.02 at every N from 10 to 50, on a synthetic three-step pipeline.

**Status:** `EXPERIMENTALLY_SUPPORTED` (ASSURANCE.md taxonomy)

**Scope and limits.** Pre-registered (protocol ff75707), new master seed 20261006, 200 replications per world and N. Same synthetic worlds where Experiment 3's problem was found, so not an independent test of generality. Power 0.235 at N = 10. The unmerged method reached 0.82 at N = 30 on the same data, so merging is a moderate gain. Downstream propagation is flagged more as N grows. Traces are regenerable from seeds and not included. Single author, not blind.

## Provenance

- assurance_row: `V2.9`
- code_commit: `3462ed1`
- protocol_commit: `ff75707`
- results_commit: `55e8bcf`

## Contents

- `README.md`
- `artifacts/code/run.py`
- `artifacts/measurements/RESULTS.md`
- `artifacts/measurements/results.json`
- `artifacts/protocol/PROTOCOL.md`
- `claim.json`
- `provenance.json`

## Verify

`python -m glassbox.v7.evidence verify <path-to>/v7-exp3b-noise-baseline-merge`

**Integrity is not truth.** a verifying manifest shows these files are unchanged since packaging; it does not show the experiment or the claim is correct.
