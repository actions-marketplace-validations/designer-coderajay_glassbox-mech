# V7 Experiment 5: controlled interventions on a real model (GPT-2 RAG, three co-changes)

*Protocol v1.0. Written 2026-10-11, BEFORE any Experiment 5 code and before any run.
It is committed first and not changed afterwards. Deviations go in dated addenda below
the line.*

## 0. Why this experiment

Experiment 4 showed that one-factor interventions separate causes, but only on a
synthetic pipeline whose probabilities were set by hand. Experiment 5 runs the same
engine (`glassbox.v7.intervene`, unchanged) on a **real language model** with a
realistic incident:

> "In the same week we re-indexed the knowledge base, edited the prompt template, and
> changed a logging setting. Answers got worse. Which change did it?"

**Ground truth.** It is known by construction for two factors and **unknown** for one:
- **Index (known).** A stale index that drops d1–d4 changes retrieval for q1–q4 and
  leaves q5–q8 untouched. This is established in Experiment 1 (RESULTS.md, C1/C2), so
  for q5–q8 the index factor has exactly zero effect.
- **`log_level` (known).** It is inert by construction: recorded in the trace, never
  read by the system.
- **Prompt template (unknown).** A real prompt edit whose effect on GPT-2 nobody has
  measured. It is reported, not gated.

## 1. System under test (fixed)

**Corpus, retriever and model**
- The corpus, the 8 questions, the bag-of-words retriever (top_k = 1) and the
  teacher-forced scorer come from Experiment 1 (`experiments/v7/rag_fault/run.py`),
  imported unchanged.
- The model is GPT-2 small via TransformerLens, on CPU.

**Stochastic answer**
- For each prompt, the scorer gives margin = log p(correct) − log p(distractor).
- The system *samples* its answer from GPT-2's own two-option distribution:
  P(answer = correct) = 1 / (1 + exp(−margin / T)), with T = 1.0 and a seeded
  `random.Random(run_seed)`.
- The margin is deterministic per prompt and is computed once per distinct prompt
  (cached). The run-to-run randomness is the sampling.

**Recorded per run**
- A Glassbox trace with a retrieval span (hashed documents) and a chat span.
- The chat span records the hashed prompt, the attribute `glassbox.answer.label`
  (`correct` / `distractor`) and the attribute `gen_ai.request.temperature`.

**Outcome:** `glassbox.answer.label`.

## 2. Factors (candidate = all three changed)

| Factor | Base | Candidate |
|---|---|---|
| `index` | `full` (all 8 docs) | `stale` (d1–d4 missing; Experiment 1's fault) |
| `template` | `context_first`: `Context:\n<docs>\nQuestion: <q>\nAnswer:` (Experiment 1's prompt) | `question_first`: `Question: <q>\nContext:\n<docs>\nAnswer:` |
| `log_level` | `info` | `debug` (recorded as `glassbox.env.log_level`; inert) |

## 3. Design

| Setting | Value |
|---|---|
| Interventions | `run_interventions` once **per question** (8 independent investigations), k = 3: baseline, candidate, 3 × `only_<f>`, 3 × `all_but_<f>` (8 distinct cells) |
| Runs per cell | `n_per_cell` = 30 |
| Permutations | `n_perm` = 999 |
| α | 0.05 (Holm within each question's sufficiency family of 3) |
| Settings seed | `"exp5-20261011:<qid>"` |

**Group diff (descriptive).** For each question, the script also runs
`glassbox.v7.groupdiff.group_diff` (merged) on the `baseline` vs `candidate` traces.

## 4. Pre-declared criteria

| ID | Criterion | Pass rule |
|---|---|---|
| E1 Real fault attributed | q1–q4: `index` attributed | 4/4 |
| E2 No false blame on the index | q5–q8: `index` **not** attributed (true effect is exactly zero) | ≥ 3/4 (Holm FWER ≤ 0.05 per question) |
| E3 Inert never blamed | `log_level` attributed | ≤ 1/8 questions (with FWER ≤ 0.05 each, P(≥ 2 false in 8) ≈ 0.06) |
| E4 Scorer determinism | Every distinct prompt's margin, re-scored once at the end, equals the cached value | all prompts, to 1e-9 |

**Descriptive**

| ID | What is reported |
|---|---|
| D1 Template effect | `template` attributed or not per question; P(correct) per cell; TVD and p. The real unknown, reported as found. |
| D2 Necessity and interaction | Necessity results per factor and question. Expected: for q1–q4, reverting `template` alone may matter little while the index is stale. |
| D3 Diff vs intervention | `first_beyond_noise` step and all flagged steps of the group diff, per question, next to the attributed factors |
| D4 Experiment 1 cross-check | Max absolute difference between this run's `context_first` margins (full/stale index) and Experiment 1's committed margins |

**Overall result.**
- **PASS** iff E1, E2, E3 and E4 all pass.
- D1–D4 are descriptive.
- A FAIL is reported as a FAIL. Factors, templates, N, T and seeds are not changed
  after any run.

**Stated in advance:**
- E1 is close to mechanical. Experiment 1's committed margins flip sign for q1–q4
  (e.g. q1 +10.16 → −9.80), so the sampled outcome changes almost surely.
- E2 and E3 test that the engine does not invent causes.
- The scientifically open part is D1/D2: what the real prompt edit does to GPT-2.

## 5. What a PASS would and would not show

**Would show:**
- The intervention engine runs end-to-end on a real language model with a stochastic
  outcome.
- It attributes a known real fault, does not blame a zero-effect factor or an inert
  setting, and reports an unknown factor's effect with a test.

**Would not show:**
- That Glassbox finds unknown causes in systems it did not build (V2.4, Hard Gate 3).
  The factors here are still chosen and switched by the author.
- Anything about larger models, other providers or agents.
- That two-option sampling resembles free-form generation.
- A general causal claim about prompt templates.

## 6. Execution

1. Commit this protocol.
2. Implement `experiments/v7/real_intervention/run.py` test-first. Unit tests use a
   fake scorer only; GPT-2 is not loaded in tests and Experiment 5 is not run during
   development.
3. Commit the code.
4. Run on the owner's Mac:

   `python3 experiments/v7/real_intervention/run.py --out experiments/v7/real_intervention/results`
5. Commit `results.json` unchanged. Per-run traces are written to a temporary directory
   and not committed: 1,920 files, regenerable from seeds and the deterministic scorer.

---
*(Addenda, if any, go below this line, with dates.)*
