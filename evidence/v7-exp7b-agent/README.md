# Evidence package: v7-exp7b-agent

**Claim.** On a small instruction-tuned LLM tool-using agent (Qwen2.5-3B-Instruct, chosen by a pre-declared competence check), Glassbox's investigation blamed the large real cause in 4/4 cases, never blamed the inert change, recorded every tool execution including hidden framework retries, and its exact and sampled outcomes agreed (G1-G5 PASS, Hard Gate 8).

**Status:** `EXPERIMENTALLY_SUPPORTED` (ASSURANCE.md taxonomy)

**Scope and limits.** Pre-registered (protocol 821333a, addenda 2eb6aac, 7ae8a08, 5d4ffcb). PASS in two Kaggle CPU runs; run 1's result files were lost and only its printed log survives. Run 2 matched every gate, attribution, observed value and p-value but was not reproduced bit-identically (13 exact probabilities differ in the 6th decimal); a pre-registered check attributed this to floating-point summation order on one machine, not to the exact original sessions. The measured change was mostly that the agent stopped sending the confirmation (P(0 emails) about 0.31 to 0.97), not duplicates (about 0.005 to 0.016). The mid-sized cause framework_retry (about 0.34) was attributed in 2/4 cases. Fixed action menu, raw-text prompts without a chat template, factors chosen by the author, cause known by construction, single author, not independently reproduced. Traces are regenerable and not included.

## Provenance

- addendum2_commit: `7ae8a08`
- addendum3_commits: `5d4ffcb, 38dba0d`
- assurance_row: `V3.8`
- code_commit: `b807af7`
- numeric_check_commit: `4bcf553`
- protocol_commit: `821333a`
- run2_results_commit: `80197c5`
- run_code_commit: `2eb6aac`
- writeup_commit: `222abd6`

## Contents

- `README.md`
- `artifacts/code/explain_numeric.py`
- `artifacts/code/run.py`
- `artifacts/measurements/RESULTS.md`
- `artifacts/measurements/results.json`
- `artifacts/numeric_check/numeric_check.json`
- `artifacts/numeric_check/numeric_check_log.txt`
- `artifacts/protocol/PROTOCOL.md`
- `artifacts/run1/notebook_run1.ipynb`
- `artifacts/run1/run_log_run1.txt`
- `artifacts/run2/env_freeze.txt`
- `artifacts/run2/run_log_run2.txt`
- `claim.json`
- `provenance.json`

## Verify

`python -m glassbox.v7.evidence verify <path-to>/v7-exp7b-agent`

**Integrity is not truth.** a verifying manifest shows these files are unchanged since packaging; it does not show the experiment or the claim is correct.
