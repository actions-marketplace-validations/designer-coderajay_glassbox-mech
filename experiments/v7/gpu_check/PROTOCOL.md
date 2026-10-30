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

## Addendum 1 (2026-10-30): attempt 1 was an infrastructure failure; setup fixed

**What happened.**
- Attempt 1 ran on Colab (Tesla T4, Python 3.13.16, torch 2.10.0+cu128, CUDA 12.8) at
  commit `c5bd4c2`.
- The setup checks passed: GPU visible, `torch.cuda.is_available()` True, 25 tests
  passed.
- It then crashed while configuration A was **loading** GPT-2, before any
  investigation ran:
  - `RuntimeError: operator torchvision::nms does not exist`;
  - then `ModuleNotFoundError: Could not import module 'BertForPreTraining'`.
- Cause: Colab preinstalls `torchvision 0.26.0+cu130`, which requires torch 2.11.0. The
  pinned torch 2.10.0 replaced torch but not torchvision. `transformers` imports
  torchvision when it is present, so importing `transformer_lens` failed.
- No `results.json` was written. The log is kept unchanged in `attempt1/run.log`
  (sha256 `abb136eef9e14985134918a8af5ccd4c3602996f9eb3ac98649780254348e682`).
- No decision data exists from attempt 1. It is not scored, per §4.

**Changes for attempt 2.** Setup only. The question, configurations, settings,
criteria and `run.py` are unchanged.
1. After installing the pins, uninstall `torchvision` and `torchaudio`. Neither is
   used by Glassbox or GPT-2 scoring.
2. Before the run, the setup check also imports `transformer_lens` and loads GPT-2
   once. Attempt 1 passed the tests only because they use fakes.
3. Output goes to `experiments/v7/gpu_check/attempt2/`, so both attempts stay on
   record.

`docs/v7/COLAB_GPU.md` is updated to match. The attempt 2 run uses the commit that
adds this addendum.

## Addendum 2 (2026-10-30): attempt 2 stopped at the setup check; isolated environment

**What happened.**
- Attempt 2 was set up per Addendum 1 at commit `6467d56`: a fresh runtime, Tesla T4,
  torch 2.10.0+cu128, 25 tests passed.
- The new model-load check failed:
  `ImportError: cannot import name 'BertForPreTraining' from 'transformers'`.
  Just before the error, TensorFlow printed start-up lines, so this time
  `transformers` was importing Colab's preinstalled TensorFlow.
- `run.py` was **not started**, so there is no output and no log for attempt 2.
- The likely cause is the same as in attempt 1: Colab preinstalls packages built for a
  newer stack, and removing them one by one does not hold. **This diagnosis is
  inferred from the import order; it is not confirmed.**

**Change.** Setup only. The question, configurations, settings, criteria and `run.py`
are unchanged.
- Everything runs in a separate virtual environment created with `uv`, using
  **Python 3.11 (the CI's version)** and only the CI pins.
- Colab's own packages are not visible inside it.
- Attempt 2 keeps its name, because nothing ran. It uses the commit that adds this
  addendum, writes to `attempt2/`, and records the venv's Python version in
  `environment.python_version`.
