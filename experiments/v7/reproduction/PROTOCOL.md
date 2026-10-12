# V7 Experiment 9: reproducing the V7 experiments in an independent environment (Hard Gate 5)

*Protocol v1.0. Written 2026-10-12, before any reproduction run. It is committed first and
not changed afterwards. Deviations go in dated addenda below the line.*

## 0. Question and hard gate

**V7 Hard Gate 5:** "Another run or independent environment reproduces the finding."

Every V7 result so far, except Experiment 7b, was produced on one machine: the owner's
Mac, arm64, macOS. This experiment re-runs each packaged experiment **from its evidence
package's recipe**, in a **different environment** (Linux x86-64), and checks
mechanically whether the findings come out the same.

**Who runs it.** The owner runs it, so this is a **same-author reproduction in an
independent environment**. That is what Gate 5 asks for. It is **not** an independent
reproduction by another person, so it can never justify the `REPRODUCED` status in
ASSURANCE.md. That needs a named independent reproducer and stays open.

## 1. What is reproduced

| Package | Experiment | Recipe commit | Notes |
|---|---|---|---|
| `v7-exp1-rag-fault` | 1 (controlled RAG fault, GPT-2) | `aedfebf` | |
| `v7-exp2-llama-dedup` | 2 (llama_index #21033) | `72cb710` | two pinned llama-index venvs |
| `v7-exp3-noise-baseline` | 3 (group diff; **pre-registered FAIL**) | `3cf24ac` | a reproduction must reproduce the FAIL |
| `v7-exp3b-noise-baseline-merge` | 3b | `55e8bcf` | |
| `v7-exp4-interventions` | 4 (synthetic interventions) | `ad75d43` | |
| `v7-exp5-real-interventions` | 5 (GPT-2 RAG interventions) | `e47cf4e` | |
| `v7-exp6-cross-model` | 6 (Pythia, OPT, Qwen) | `3314c58` | |
| `v7-exp8-cross-stack` | 8 (OTLP second stack) | `226a4eb` | stack-B venv |

**Excluded, pre-declared:** `v7-exp7b-agent`. It already has two runs on Linux x86
(Kaggle) and a numeric-explanation check (its Addenda 2 and 3); a third run would take
about 3.5 hours of CPU. Experiment 7 (INCONCLUSIVE) has no evidence package and is not
re-run.

## 2. Environment

- **Machine:** a Kaggle notebook on CPU (Linux x86-64), batch "Save & Run All"
  sessions. This differs from the original Mac in OS, CPU architecture and BLAS.
- **Python:** 3.11 in a `uv` venv with the pinned stack in
  `experiments/v7/reproduce_recipes.json`: numpy 1.26.4, torch 2.10.0,
  transformer-lens 2.17.0, transformers 4.57.6, pyarrow 23.0.0, datasets 4.5.0,
  pandas 3.0.0, scipy 1.17.1, einops 0.8.2.
- **Recorded per run:** the CPU model, `uv pip freeze`, and the commit printed by git.

## 3. Procedure (fixed)

For each package in §1:
1. **Code:** check out the recipe commit in its own worktree. That commit contains the
   code that produced the packaged results.
2. **Setup and run:** run the recipe's **run commands exactly**, writing to `repro/`.
   - The recipe's **setup** is carried out as its uv equivalent, because Kaggle's
     default Python is 3.13 and `python3.11` exists only through uv:
     - `python3.11 -m venv X` / `python3 -m venv X` becomes `uv venv X --python 3.11`;
     - `X/bin/pip install …` becomes `uv pip install --python X/bin/python …`.
   - The packages and pins are those of the recipe. `KAGGLE_RUN.md` spells out every
     command.
3. **Compare** in the current checkout:

   `python -m glassbox.v7.reproduce compare evidence/<package> <fresh results.json …> --reproducer "Ajay Pravin Mahale (author)" --environment "<Kaggle CPU model, Linux x86-64>" --out experiments/v7/reproduction/reports/<package>.json`

   - It uses the recipe's tolerance (1×10⁻⁴ for every package) and ignore list.
   - **Ignored keys:** `environment_differences_bug_vs_fix` for Experiment 2, and
     `stack_b_env` for Experiment 8. Both contain platform strings, which are expected
     to differ.
4. **Batching:** packages may run in several Kaggle sessions. A session that fails for
   infrastructure reasons (time-out, download failure) may be re-run; every attempt is
   listed in RESULTS.md.

## 4. Pre-declared criteria

| ID | Criterion | Pass rule |
|---|---|---|
| R1 | **Findings reproduced.** For each package, the verdict is `REPRODUCED` or `DECISIONS_ONLY`: every pass/fail decision, overall verdict, count and label is identical; only floats may differ. | 8/8 packages |
| R2 | **Numbers reproduced** (descriptive, not gated). The number of packages whose verdict is `REPRODUCED` (every float within 1×10⁻⁴). | reported |
| R3 | **Package integrity.** Every package verifies before comparison (the `compare` command refuses otherwise). | 8/8 |

**Overall: PASS iff R1 and R3 pass.** Then Hard Gate 5 is met for these experiments.
- **Any `NOT_REPRODUCED` is a FAIL for that experiment**, reported with every mismatch.
- A failed experiment's ASSURANCE row is then annotated as not reproduced across
  environments. Its status is reconsidered, never quietly kept.
- The overall result is then FAIL.

## 5. What a PASS would and would not show

**Would show:**
- The V7 findings do not depend on the original machine, OS or CPU architecture.
- The evidence packages contain enough (code commit, environment, commands) for someone
  to re-run them.

**Would not show:**
- reproduction by an independent person (needed for `REPRODUCED`; still open);
- reproduction on GPU;
- anything about Experiment 7b beyond its own two runs;
- that the experiments' designs are right. Reproducing a result reproduces its
  limitations too.

## 6. Execution

1. Commit this protocol.
2. Commit the Kaggle runbook (`KAGGLE_RUN.md`) that turns the recipes into notebook
   cells. It contains no new experiment code: only the recipes' own commands.
3. Run. Commit every report and log unchanged.
4. Write RESULTS.md and update ASSURANCE.

---
*(Addenda, if any, go below this line, with dates.)*
