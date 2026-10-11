# V7 Experiment 6: does the investigation work across model families? (Hard Gate 7)

*Protocol v1.0. Written 2026-10-11, BEFORE any Experiment 6 code and before any run.
It is committed first and not changed afterwards. Deviations go in dated addenda below
the line.*

## 0. Why this experiment

Experiments 4 and 5 used a synthetic pipeline and GPT-2 small only. V7 Hard Gate 7
requires the investigation layer to work across more than one model family. This
experiment repeats Experiment 5's design **unchanged** on three model families that
are not GPT-2.

**Improvement over Experiment 5: exact ground truth for every factor.**
- Each system samples its answer from the model's own two-option distribution:
  P(correct) = sigmoid(margin / T).
- The margin is deterministic per prompt, so the **true** effect of switching any
  factor alone is computable exactly, with no sampling:

  true TVD(f, q) = | P(correct | baseline config) − P(correct | only_f config) |

- Experiment 5 could gate only on effects known in advance. Here every (factor,
  question) pair has a known truth, and the gates are defined against it.

## 1. Models (fixed, in this order)

| Family | Model (TransformerLens name) | Why |
|---|---|---|
| Pythia (GPT-NeoX architecture) | `EleutherAI/pythia-160m` | Different architecture and training data from GPT-2; used in V6 |
| OPT (Meta) | `facebook/opt-125m` | Different family, same size class as GPT-2 small |
| Qwen 2.5 | `Qwen/Qwen2.5-0.5B` | A recent, larger, different-tokenizer family |

**Loading.**
- Each model is loaded with
  `transformer_lens.HookedTransformer.from_pretrained(name, device="cpu")`, one at a
  time, and freed before the next.
- **Qwen fallback, declared in advance.** If `Qwen/Qwen2.5-0.5B` fails to load at run
  time, `Qwen/Qwen2-0.5B` is tried, then nothing else.
- **Name check, done 2026-10-11 before this protocol was committed.** All four names
  (`EleutherAI/pythia-160m`, `facebook/opt-125m`, `Qwen/Qwen2.5-0.5B`,
  `Qwen/Qwen2-0.5B`) are in `transformer_lens.loading_from_pretrained.OFFICIAL_MODEL_NAMES`
  in the owner's environment (transformer-lens 2.17.0). Being in that list does not
  guarantee that a model loads and runs.
- **Load failures.** A model that fails to load is reported as **NOT RUN** with its
  error. No other model is substituted.

## 2. System, factors and design (identical to Experiment 5)

**Reused unchanged by import:**
- Experiment 1's corpus, 8 questions, bag-of-words retriever (top_k = 1) and
  teacher-forced scorer (`GPT2Scorer(model_name)`, which accepts any TransformerLens
  model name).
- Experiment 5's `RagRunner`, `MarginCache`, prompt templates and `label_outcome`.

**Factors:**
- `index`: full → stale (d1–d4 missing);
- `template`: context_first → question_first;
- `log_level`: info → debug (inert).

**Design:** `glassbox.v7.intervene.run_interventions`, one investigation per question:

| Setting | Value |
|---|---|
| Cells | 8 per question |
| Runs per cell | 30 |
| Permutations | `n_perm` = 999 |
| Multiple testing | α = 0.05, Holm within each question's sufficiency family |
| Temperature | T = 1.0 |
| Seed | `"exp6-<model>:<qid>"` |

**Computed per model before the runs (deterministic):** the margin for each of the 4
distinct (index, template) prompts per question. From these, the true TVD of each
factor per question follows.

## 3. Ground-truth classes (from the exact true TVD)

For each model and each (factor, question) pair:

| Class | Definition | Pairs |
|---|---|---|
| **Exactly zero** | Identical prompts, so true TVD = 0 by construction | `log_level` on all 8 questions; `index` on q5–q8 (Experiment 1 showed identical retrieval) |
| **Large** | true TVD ≥ 0.5 | Determined from the margins, per model |
| **Small** | 0 < true TVD < 0.5 | Determined per model; reported, not gated |

## 4. Pre-declared criteria (applied to each model that loads)

| ID | Criterion | Pass rule (per model) |
|---|---|---|
| X1 Sensitivity | Every **large** pair is attributed | all large pairs. If a model has no large pair, X1 is "not applicable" and reported as such. |
| X2 Specificity | Attributions among the **exactly-zero** pairs (12 per model) | ≤ 1 per model. Holm controls the family-wise error rate at ≤ 0.05 per question, so the expected count is ≤ 0.4. |
| X3 Determinism | Every cached margin re-scored | equal to ≤ 1e-6 |

*Note on X3's tolerance.* Experiment 5 used 1e-9. I widened it here, in advance,
because other architectures may use different reduction orders. If you prefer 1e-9,
change it before committing this protocol.

**Overall result.**
- **PASS** iff at least **two** of the three models load **and** every model that loads
  passes X1, X2 and X3.
- A model that loads but fails any criterion makes the experiment **FAIL**. It is not
  dropped.

**Descriptive (not gated):**

| ID | What is reported |
|---|---|
| D1 Detection vs true effect | For every pair: true TVD, observed TVD, p and the attribution, for all models. This shows the smallest true effect detected at N = 30 per family. |
| D2 Diff vs intervention | `first_beyond_noise` of the group diff per question and model, next to the attributions |
| D3 Model behaviour | Baseline P(correct) per question per model (does the model use the retrieved context at all?) |
| D4 Cross-check | GPT-2's margins from Experiment 5, shown for comparison (not re-run) |

## 5. What a PASS would and would not show

**Would show:** on three further model families, the same investigation finds every
large real effect, does not blame zero-effect or inert changes beyond the declared
error rate, and its scores are reproducible.

**Would not show:**
- Results for large or hosted models (providers, APIs).
- Free-form generation (this is two-option sampling).
- Agents.
- Unknown causes (V2.4).

## 6. Execution

1. Commit this protocol.
2. Implement `experiments/v7/cross_model/run.py` test-first. Unit tests use a fake
   scorer; no model is loaded in tests. The runner refuses to overwrite results.
3. Commit the code.
4. Run on the owner's Mac (CPU):

   `python3 experiments/v7/cross_model/run.py --out experiments/v7/cross_model/results`

   - Models are downloaded on first use: about 0.3 GB, 0.25 GB and 1 GB. These sizes
     are approximate; I have not verified them.
   - If the Mac cannot run a model, a rented machine with the same pinned stack may be
     used. This must be stated in RESULTS.md, with the machine type.
5. Commit `results.json` unchanged. Traces are not committed: they are regenerable from
   the seeds and deterministic margins.

---
*(Addenda, if any, go below this line, with dates.)*
