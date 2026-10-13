# V7 Experiment 9b: decision-level reproduction in a new environment. RESULTS

*Provenance, in commit order:*
- Protocol v1.0: `440767f`.
- Decision-level `compare`, workflow and the guide for independent reproducers:
  `478cc68`.
- Attempt 1 record and Addendum 1 (workflow defect; fix; rule for attempt 2): `20fcea2`.
- Record of the re-run on the unfixed workflow and Addendum 2: `b1fdad4`.
- Attempt 2: Actions run `38368788372`, triggered from `main` at `b1fdad4`, on
  2026-10-13. It took 18 minutes.

Every attempt's artifact is committed unchanged:
- `attempt1/reports/`: zip sha256 `4f2c17e6…482338a4`;
- `attempt1_rerun/reports/`: zip sha256 `dfcff50f…7983bae`;
- `attempt2/reports/`: zip sha256
  `a04dd4dfd84080976fdb036fe6a11c79dc677f677bfb2afec24f6f45f9ef95b3`. The same digest is
  shown by GitHub for the artifact.

A repository-wide `.gitignore` rule (`reports/`) silently kept `attempt1/reports/` and
`attempt1_rerun/reports/` out of commits `20fcea2` and `b1fdad4`, although their
RECORD.md files say they were committed. A negation for
`experiments/v7/reproduction_b/*/reports/` was added, and all three artifacts are
committed together with this file. The files are the unchanged contents of the zips
above.

## Outcome: **PASS**. Hard Gate 5 met at the decision level, for a same-author reproduction

| Criterion | Rule | Result |
|---|---|---|
| B1 Decisions reproduced | 8/8 `DECISIONS_REPRODUCED` | **8/8: PASS** |
| B2 Package integrity | 8/8 verified before comparison | **8/8: PASS** |
| B3 Exact reproduction (descriptive) | reported | 7/8 `REPRODUCED`; Experiment 6 `DECISIONS_ONLY` |

## Per package (attempt 2)

| Package | Recipe commit | Verdict | Decisions | Mismatches |
|---|---|---|---|---|
| v7-exp4-interventions | `ad75d43` | REPRODUCED | DECISIONS_REPRODUCED | 0 |
| v7-exp3b-noise-baseline-merge | `55e8bcf` | REPRODUCED | DECISIONS_REPRODUCED | 0 |
| v7-exp2-llama-dedup | `72cb710` | REPRODUCED | DECISIONS_REPRODUCED | 0 |
| v7-exp8-cross-stack | `226a4eb` | REPRODUCED | DECISIONS_REPRODUCED | 0 |
| v7-exp1-rag-fault | `aedfebf` | REPRODUCED | DECISIONS_REPRODUCED | 0 |
| v7-exp5-real-interventions | `e47cf4e` | REPRODUCED | DECISIONS_REPRODUCED | 0 |
| v7-exp6-cross-model | `3314c58` | DECISIONS_ONLY | DECISIONS_REPRODUCED | 40, all floats, max 0.0040 |
| v7-exp3-noise-baseline (parts A and B) | `3cf24ac` | REPRODUCED | DECISIONS_REPRODUCED | 0 |

- Experiment 3's pre-registered **FAIL** reproduced, as it did in Experiment 9.
- In Experiment 6, the float differences are in Pythia/OPT/Qwen margins and the true
  effects derived from them. No raw sampled count changed on this runner, so the
  `cell_counts` exemption was not needed.

## Attempts

| Attempt | Run | What happened |
|---|---|---|
| 1 | `38303022533` #1, from `6c08ddc` | The first 7 packages compared, all `DECISIONS_REPRODUCED`. Then a workflow defect stopped the step (GitHub's `bash -e` plus `compare` exiting 1 on `DECISIONS_ONLY`). Experiment 3 never ran. |
| 1, re-run | `38303022533` #1 "Re-run jobs", from `6c08ddc` | Same unfixed workflow, same stop, same 7 results. |
| **2** | `38368788372` #2, from `b1fdad4` | Fixed workflow (Addendum 1). All 8 packages compared. |

**Cross-attempt consistency (Addendum 1, item 4).** Each of the 7 packages compared in
attempt 1 and its re-run has the same `decisions_verdict` in all three runs. Experiment
6's 40 float mismatches are identical across attempts 1 and 2. **Consistent.**

## Environment

- GitHub Actions `ubuntu-24.04`.
- AMD EPYC 7763, 4 vCPUs, 15 GB RAM, Linux x86-64.
- Python 3.11.17 via uv, torch 2.10.0 CPU build plus the recipe pins
  (`attempt2/reports/env_freeze.txt`).
- This environment was not used for any V7 run before Experiment 9b.

## What this shows and does not show

**Shows:**
- On a third machine, of a third CPU vendor and architecture family (after macOS arm64
  and Kaggle's Intel Xeon), every gated decision of the 8 packaged V7 experiments came
  out the same from the evidence packages alone.
- That includes Experiment 3's FAIL and the Experiment 6 attributions that failed the
  exact rule in Experiment 9.

**Does not show:**
- **Independence.** The author ran it. Status `REPRODUCED` in ASSURANCE requires
  another person; see `docs/v7/REPRODUCING.md`.
- **Count-exact reproduction across architectures.** Experiment 9 showed that one
  Pythia sampled count can flip on Intel Xeon. Here none did, but that is one runner.
- **Anything about Experiment 7b**, which was excluded, or Experiment 10, which came
  after the protocol.
- **That the experiments' designs are right.**
- **Choice of criterion.** The decision-level criterion was chosen after seeing
  Experiment 9. Experiment 9 stays FAIL and V9.1 stays `REFUTED`.

## Status changes

- ASSURANCE **V9.2**: `PLANNED` → `EXPERIMENTALLY_SUPPORTED`. The row states the
  same-author, decision-level scope.
- The 7 rows previously annotated "reproduced by the author on Linux" now also cite 9b.
  V3.6 (Experiment 6) notes the decision-level result.
