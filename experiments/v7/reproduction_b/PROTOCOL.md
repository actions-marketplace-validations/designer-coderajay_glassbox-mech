# V7 Experiment 9b: decision-level reproduction in a new environment (Hard Gate 5)

*Protocol v1.0. Written 2026-10-12, before any Experiment 9b run. It is committed first
and not changed afterwards. Deviations go in dated addenda below the line.*

## 0. Why this experiment exists (read first)

**What Experiment 9 found.**
- Experiment 9 re-ran 8 packages on Linux x86-64 (Kaggle CPU). It **FAILED as
  pre-registered**: 7/8 were `REPRODUCED`, and Experiment 6 was `NOT_REPRODUCED`.
- In Experiment 6, cross-architecture floating-point differences in Pythia's margins
  (at most 0.0047) shifted one probability by 3.2×10⁻⁴, and one seeded draw out of 30
  flipped (q7, `only_log_level`, 24/6 → 25/5).
- Every gated decision (attributions, criteria, overall PASS) was identical.
- Experiment 9 stays FAIL, and ASSURANCE V9.1 stays `REFUTED`. **Nothing here re-scores
  it.**

**What this experiment asks.**
- Experiment 9 showed that *raw sampled outcomes* are not stable across CPU
  architectures, while it did not show any instability in *findings*.
- 9b therefore asks a narrower question:

  > Do the **gated decisions** of the V7 experiments reproduce in an environment that
  > has **never been used** for any V7 run?

**Stated openly:**
1. The decision-level criterion was chosen **after** seeing Experiment 9. On Experiment
   9's data it would have passed 8/8. That is exactly why 9b must use a **new
   environment** and a **new run**: Experiment 9's data cannot count towards it.
2. 9b is weaker than an exact reproduction. It checks that the same conclusions come
   out, not that the same numbers do.
3. An independent reproduction by another person is being sought separately; see
   `docs/v7/REPRODUCING.md`. 9b does not replace it.

## 1. Environment (new; never used for any V7 run)

- **Runner:** GitHub Actions hosted runner `ubuntu-24.04`, x86-64. Its CPU model is
  unknown in advance, so the workflow records `lscpu`.
- **Trigger:** manually (`workflow_dispatch`) from the commit that adds this protocol's
  workflow. The workflow file is `.github/workflows/repro_exp9b.yml`.
- **Python:** 3.11 via uv; torch 2.10.0 CPU build plus the recipe pins. This is the same
  mechanics as Experiment 9 Addendum 1: one shared venv, worktrees in `/tmp`, and recipe
  run commands executed literally.
- **Logs and reports:** public in the Actions run, and uploaded as a workflow artifact
  that the owner downloads and commits unchanged.

## 2. What is reproduced

The same 8 packages as Experiment 9, each at its recipe commit:
`v7-exp1-rag-fault`, `v7-exp2-llama-dedup`, `v7-exp3-noise-baseline` (pre-registered
FAIL), `v7-exp3b-noise-baseline-merge`, `v7-exp4-interventions`,
`v7-exp5-real-interventions`, `v7-exp6-cross-model`, `v7-exp8-cross-stack`.

`v7-exp7b-agent` is excluded for the same reason as in Experiment 9, and because a 3B
model is too large for a 16 GB runner.

## 3. Decision level (fixed now; implemented in `glassbox/v7/reproduce.py`)

`compare` reports `decisions_verdict`:
- **`DECISIONS_REPRODUCED`** iff no mismatch exists other than:
  1. float values (any size);
  2. values under a key named `cell_counts`, which holds the raw per-cell sampled
     outcomes in Experiments 5–7b.
- **Everything else must be identical:**
  - overall verdicts and every `pass` flag;
  - every `attributed`/`significant` flag and class label;
  - every integer outside `cell_counts` (for example, criterion counts and replication
    counts);
  - every string;
  - the same set of keys.

The ignore lists of the recipes apply as before (Experiment 2:
`environment_differences_bug_vs_fix`; Experiment 8: `stack_b_env`).

## 4. Pre-declared criteria

| ID | Criterion | Pass rule |
|---|---|---|
| B1 | **Decisions reproduced:** `decisions_verdict == DECISIONS_REPRODUCED` | 8/8 packages |
| B2 | **Package integrity:** every package verifies before comparison | 8/8 |
| B3 | **Exact reproduction** (descriptive): number of packages with `verdict == REPRODUCED` | reported, not gated |

**Overall: PASS iff B1 and B2 pass.**
- PASS meets **Hard Gate 5 at the decision level**, for a same-author reproduction. It
  must always be described that way: never as an exact or an independent reproduction.
- Any `DECISIONS_NOT_REPRODUCED` makes the result **FAIL**, reported with every
  mismatch. No tolerance or key list changes after the run.

**Infrastructure failures** (runner time-out, download failure, disk) may be re-run.
Every attempt is listed. A re-run must use the same commit and workflow.

## 5. What a PASS would and would not show

**Would show:**
- On a third, previously unused machine, the V7 experiments reach the **same gated
  decisions** from their evidence packages alone.
- That includes Experiment 3's pre-registered FAIL.

**Would not show:**
- bit-exact or count-exact reproduction;
- reproduction by an independent person;
- anything about Experiment 7b;
- that the experiments' designs are right.

## 6. Execution

1. Commit this protocol.
2. Commit the decision-level `compare` (tested), the workflow and the guide for
   independent reproducers.
3. The owner triggers the workflow once in the GitHub UI and downloads the artifact.
4. Commit the artifact unchanged, then write RESULTS.md and update ASSURANCE.

---
*(Addenda, if any, go below this line, with dates.)*
