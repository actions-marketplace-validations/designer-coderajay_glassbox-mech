# Experiment 9b, attempt 1 (2026-10-12): record

`reports/` is the `exp9b-reports` workflow artifact, extracted unchanged. The zip's
sha256 is `4f2c17e6dab2a0ebe9a72d65e397725cb4b140944d776aa8f33ce873482338a4`.

## Run

- **GitHub Actions run:** `38303022533`, attempt 1. Triggered manually from `main` at
  `6c08ddcdb5f997504ad2471b907e6e0f078ea2f5`, using workflow `repro_exp9b.yml` as
  committed in `478cc68`.
- **Runner:**
  - ubuntu-24.04;
  - AMD EPYC 7763, 4 vCPUs;
  - 15 GB RAM;
  - 84 GB free disk at start.
  - See `reports/lscpu.txt`, `memory.txt` and `disk_start.txt`.
- **Evidence packages, recipe commits and `glassbox/v7/reproduce.py`:** unchanged since
  `478cc68`. The only recipe added since then is `v7-exp10-benchmark`, which is not
  part of 9b.

## Outcome: incomplete (harness defect), 7 of 8 packages compared

| Package | Verdict | Decisions verdict |
|---|---|---|
| v7-exp4-interventions | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp3b-noise-baseline-merge | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp2-llama-dedup | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp8-cross-stack | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp1-rag-fault | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp5-real-interventions | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp6-cross-model | DECISIONS_ONLY (float differences only; largest shown about 0.004 in a margin) | DECISIONS_REPRODUCED |
| v7-exp3-noise-baseline | **not run** | — |

Every package that ran verified before comparison (B2 for those 7).

## Why the run stopped

1. **GitHub runs `shell: bash` steps as `bash -e -o pipefail`.** The workflow's own
   `set -uo pipefail` does not switch `-e` off.
2. **`reproduce compare` exits with status 1 for any verdict other than `REPRODUCED`.**
   That behaviour is intended for interactive use.
3. **Together, these stopped the step.** Experiment 6's `DECISIONS_ONLY` was the first
   non-`REPRODUCED` verdict. Its exit status passed through the `| tee` pipe and
   ended the step right after Experiment 6's report was written.
4. **Experiment 3 never started.**
   - There is no `v7-exp3-noise-baseline.commit.txt`, `.log` or report.
   - There is no `disk_end.txt` or `summary.txt`.
   - The step was reported as "Process completed with exit code 1".

This is a defect in the workflow, the author's error. It is not a result of the
experiment. Experiment 9b's protocol expected `DECISIONS_ONLY` as a possible outcome,
and the workflow should not have stopped on it. Addendum 1 of `../PROTOCOL.md` records
the fix and the rule for attempt 2.
