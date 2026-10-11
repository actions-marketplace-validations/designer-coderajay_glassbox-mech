# Evidence package: v7-exp5-real-interventions

**Claim.** On GPT-2 small RAG with three simultaneous changes (stale index, prompt-template edit, inert log setting), one-factor interventions with 30 runs per cell attributed the known real fault for 4/4 affected questions, never blamed the zero-effect index (4/4 unaffected questions) or the inert setting (0/8), and the model's scores were deterministic on re-scoring.

**Status:** `EXPERIMENTALLY_SUPPORTED` (ASSURANCE.md taxonomy)

**Scope and limits.** Pre-registered (protocol 47ce955). Two-option sampling from GPT-2's own probabilities on Experiment 1's 8 fictional questions. The fault attribution was close to mechanical. Small real template effects (true TVD 0.05-0.11 on q3, q7) were not detected at 30 runs per cell. Factors were chosen and switched by the author, so this is not a blind test. Traces are regenerable and not included. Single author.

## Provenance

- assurance_row: `V3.3`
- code_commit: `d1ac3ec`
- protocol_commit: `47ce955`
- results_commit: `e47cf4e`

## Contents

- `README.md`
- `artifacts/code/run.py`
- `artifacts/measurements/RESULTS.md`
- `artifacts/measurements/results.json`
- `artifacts/protocol/PROTOCOL.md`
- `claim.json`
- `provenance.json`

## Verify

`python -m glassbox.v7.evidence verify <path-to>/v7-exp5-real-interventions`

**Integrity is not truth.** a verifying manifest shows these files are unchanged since packaging; it does not show the experiment or the claim is correct.
