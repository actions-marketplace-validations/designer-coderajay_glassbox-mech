# V8 phase B: GPU sanity check. PROTOCOL

*Protocol v1.0, written 2026-10-30 before any code or run. Committed first and not
changed afterwards; deviations go in dated addenda at the end.*

## 1. Question

Moving from CPU to a rented GPU (Google Colab) changes floating-point arithmetic. Does
the built-in investigation (`glassbox.v7.investigate`, RAG demo incident, GPT-2 small)
still reach the **same decisions** on GPU as on CPU?

This matters before any GPU experiment (phases E2, E5, E6). Experiment 9 showed that
moving across CPU architectures can flip individual sampled outcomes while every
decision stayed the same.

## 2. Setup (fixed now)

- **Machine.** One Google Colab session with a GPU runtime. All three configurations
  run in the **same session**, so CPU and GPU share the machine, software and seed.
  The environment record (`glassbox.v7.compute.environment_record`) is saved for each
  configuration.
- **Incident.** `demo_rag.make_incident(scorer)` with all three changes
  (`index`, `template`, `log_level`) and all 8 questions as cases.
- **Settings.** `InterventionSettings(n_per_cell=30, n_perm=999, alpha=0.05,
  seed="gpu-check")`, identical for every configuration.
- **Configurations:**

  | ID | Device | Dtype | Role |
  |---|---|---|---|
  | A | cpu | float32 | reference (the published default) |
  | B | cuda | float32 | **gated** comparison |
  | C | cuda | bfloat16 | descriptive only |

- **Code.** `experiments/v7/gpu_check/run.py` at the commit that adds it. Install from
  that commit with the CI-pinned stack (`docs/v7/COLAB_GPU.md`).

## 3. What is compared

The **decisions** for each configuration:
- per case: `attributed` (switching a factor alone changed the outcome) and
  `reverting_matters` (reverting it alone changed the outcome);
- the `factor_summary` across cases.

Descriptive, not gated:
- raw outcome counts per cell;
- runtime per configuration;
- for C, how many cases match A.

## 4. Criteria

| ID | Criterion | Pass rule |
|---|---|---|
| G1 | Decisions A vs B | `factor_summary` and every case's `attributed` and `reverting_matters` identical |
| G2 | Environment recorded | B's record names a GPU and a CUDA version; A's says cpu |

**Overall PASS iff G1 and G2 pass.**

If G1 fails:
- report it as **FAIL**, with every differing case and the raw counts;
- GPU runs of later experiments then compare only within the same device, and each
  device gets its own reproduction.

If the session has no GPU, B and C cannot run. That is an **infrastructure failure**:
record it, then re-run. It is never scored as PASS.

## 5. What a PASS would and would not show

- **Would show:** on this incident and model, the investigation's decisions do not
  depend on CPU vs GPU float32.
- **Would not show:**
  - anything about other models, larger models or other incidents;
  - anything about bfloat16 beyond the descriptive count;
  - independence (same author).

## 6. Execution

1. Commit this protocol.
2. Commit `run.py` and its tests (toy scorer, no GPU needed).
3. Owner runs it on Colab and downloads `results.json` and the log.
4. Commit the results unchanged, then write `RESULTS.md`.

---
*(Addenda, if any, go below this line, with dates.)*
