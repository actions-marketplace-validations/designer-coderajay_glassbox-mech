# V7 Experiment 9: reproduction in an independent environment. RESULTS

*Provenance, in commit order:*
- Protocol v1.0 and runbook: `fe8103a`.
- Tooling (`glassbox/v7/reproduce.py`, recipes): `219b1a7`.
- Addendum 1 (attempt 1 stopped by a full disk; mechanics for attempt 2): `1bb8234`,
  committed before attempt 2.

Every report, log, fresh `results.json`, environment freeze and both notebooks are
committed unchanged under `attempt2/`.
- `repro_A.zip`: sha256 `17b25e1c…ba76d50de`.
- `repro_B.zip`: sha256 `4e07a5c7…cf9fde247`.

## Outcome: **FAIL** as pre-registered (R1 7/8). Hard Gate 5 is **not met** by this experiment

| Criterion | Result |
|---|---|
| R1 Findings reproduced (verdict `REPRODUCED` or `DECISIONS_ONLY`) | **7/8**. `v7-exp6-cross-model` is `NOT_REPRODUCED`: **FAIL** |
| R2 Numbers reproduced (descriptive) | 7/8 `REPRODUCED` (every float within 1×10⁻⁴) |
| R3 Package integrity | 8/8 packages verified before comparison: **PASS** |

## Attempts

| Attempt | What happened |
|---|---|
| 1 (notebook A, main `fe8103a`) | `v7-exp4-interventions` **REPRODUCED**. Then the disk filled (a separate CUDA-torch venv per package) and the other packages never ran. Infrastructure failure; see `attempt1/RECORD.md` and Addendum 1. |
| — | A duplicate "Save Version" run of the attempt-2 notebook A was started by mistake and cancelled by the owner before it completed. It produced no results. |
| **2, notebook A** (main `1bb8234`) | Experiments 4, 3b, 2, 8 and 1: all **REPRODUCED**, with zero mismatches. Run 19:00–19:14 UTC. |
| **2, notebook B** (main `1bb8234`) | Experiments 5 and 3 (A and B): **REPRODUCED**, zero mismatches. Experiment 6: **NOT_REPRODUCED**. Run 19:17–19:28 UTC. |

**Environment (both notebooks):**
- Kaggle CPU, Intel(R) Xeon(R) CPU @ 2.20GHz (family 6, model 79), 4 logical CPUs,
  AVX2, no AVX-512, Linux x86-64.
- Python 3.11.17 (uv).
- torch 2.10.0+cpu plus the recipe pins (`attempt2/notebook_*/env_freeze.txt`).

**Original runs:** macOS arm64 (Apple Silicon), Python 3.11.9.

## Per package (attempt 2)

| Package | Recipe commit | Verdict | Mismatches |
|---|---|---|---|
| v7-exp1-rag-fault | `aedfebf` | REPRODUCED | 0 |
| v7-exp2-llama-dedup | `72cb710` | REPRODUCED | 0 |
| v7-exp3-noise-baseline (pre-registered FAIL) | `3cf24ac` | REPRODUCED, the FAIL included | 0 + 0 |
| v7-exp3b-noise-baseline-merge | `55e8bcf` | REPRODUCED | 0 |
| v7-exp4-interventions | `ad75d43` | REPRODUCED (also in attempt 1) | 0 |
| v7-exp5-real-interventions | `e47cf4e` | REPRODUCED | 0 |
| **v7-exp6-cross-model** | `3314c58` | **NOT_REPRODUCED** | 40 (38 float, 2 integer) |
| v7-exp8-cross-stack | `226a4eb` | REPRODUCED | 0 |

## Why Experiment 6 did not reproduce

**Where the mismatches are.** 36 of the 40 are in the Pythia-160m section and 4 in the
Qwen2.5-0.5B section; OPT-125m matches exactly.

1. **34 floats are teacher-forced margins** (summed log-probabilities): 30 for Pythia and
   4 for Qwen (Qwen's within 2×10⁻⁴). They differ by up to 0.0047 between macOS arm64
   and Linux x86-64. Example: Pythia q2, full, context-first: 18.082446 → 18.077986.
   These are floating-point differences of the same kind as Experiment 7b's (Addendum 3
   there), larger here because margins sum log-probabilities over several tokens.
2. **Through the sampling model, these shift three Pythia exact probabilities** slightly:
   - q7 `baseline_p_correct`: 0.832041 → 0.832361;
   - q7 template `true_tvd`: 0.072381 → 0.072693;
   - q3 index `true_tvd`: 0.414701 → 0.415108.
3. **One sampled run flipped.** In Pythia q7, cell `only_log_level`, one of 30 seeded
   draws landed between the old and the new probability. The counts moved from
   **24 correct / 6 distractor** to **25 / 5**, and the observed TVD of `log_level` went
   from 0.0 to 0.0333 (one run in 30). These two integer counts are the **only non-float
   differences**.
4. **What did not change:**
   - every attribution decision;
   - every p-value (the `log_level` test stayed non-significant, p unchanged);
   - every per-model criterion (X1–X3);
   - the overall PASS;
   - which large effects were blamed, and that no zero effect was blamed.

**Reading:**
- Experiment 6's *findings* reproduced.
- Its *raw sampled outcomes* did not, exactly.
- Under the pre-registered rule (§4 R1 counts integers as decisions), that is
  `NOT_REPRODUCED` and a **FAIL**. That verdict stands.

**What it teaches:** seeded sampling is reproducible only for an identical floating-point
computation. Across CPU architectures, a draw that lands within about 3×10⁻⁴ of a
probability can flip. Experiments 1–5, 7b and 8 were unaffected in this run. They are
either deterministic, or their probabilities did not move near a draw.

## Consequences (no criterion or tolerance changed after seeing these results)

- **Hard Gate 5 is not met by Experiment 9 as pre-registered.**
- **ASSURANCE V9.1** (the 8/8 claim) is `REFUTED`.
- **V3.6 (Experiment 6), reconsidered as Addendum 1 / §4 require:**
  - Its claim is about attributions (every large true effect blamed, no exactly-zero
    effect blamed), and those reproduced identically on Linux x86-64.
  - It therefore keeps `EXPERIMENTALLY_SUPPORTED`, with an explicit note that its
    sampled counts did not reproduce bit-exactly across architectures.
  - This is a decision made in the open, not a silent retention.
- **Rows V2.3, V2.5, V2.7 (still `REFUTED`), V2.9, V3.1, V3.3 and V2.10** gain a note:
  reproduced by the author on Linux x86-64 (Experiment 9). Their statuses do not change.
  `REPRODUCED` needs an independent person.

## Possible follow-up (not part of this experiment)

A new, separately pre-registered experiment could define reproduction for sampled
experiments at the level of **gated decisions**. It would have to state openly that it
was motivated by this result, and it could not re-score Experiment 9. It could also
measure how often seeded draws flip across architectures. Whether to do this is the
owner's decision.
