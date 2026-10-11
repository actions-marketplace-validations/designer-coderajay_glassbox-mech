# Evidence package: v7-exp6-cross-model

**Claim.** Experiment 5's investigation, unchanged, on three further model families (Pythia-160m, OPT-125m, Qwen2.5-0.5B) blamed every large true effect (3/3, 3/3, 4/4), none of the 36 exactly-zero effects, and re-scored deterministically.

**Status:** `EXPERIMENTALLY_SUPPORTED` (ASSURANCE.md taxonomy)

**Scope and limits.** Pre-registered (protocol 74f1958). Ground truth computed exactly from each model's deterministic margins. Large effects were mostly near-deterministic. Detection limit at 30 runs per configuration: true effects of about 0.41 and above detected, about 0.16 and below missed. Small local open-weights models only, no hosted providers, two-option sampling, factors chosen by the author. Traces are regenerable and not included. Single author.

## Provenance

- assurance_row: `V3.6`
- code_commit: `a0f8c7d`
- protocol_commit: `74f1958`
- results_commit: `3314c58`

## Contents

- `README.md`
- `artifacts/code/run.py`
- `artifacts/measurements/RESULTS.md`
- `artifacts/measurements/results.json`
- `artifacts/protocol/PROTOCOL.md`
- `claim.json`
- `provenance.json`

## Verify

`python -m glassbox.v7.evidence verify <path-to>/v7-exp6-cross-model`

**Integrity is not truth.** a verifying manifest shows these files are unchanged since packaging; it does not show the experiment or the claim is correct.
