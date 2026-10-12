# V7 Experiment 7b: investigating an LLM agent, with a competent agent (Hard Gate 8)

*Protocol v1.0. Written 2026-10-11, BEFORE any Experiment 7b code and before any run.
It is committed first and not changed afterwards. Deviations go in dated addenda below
the line.*

## 0. Relation to Experiment 7 (read first)

- **Experiment 7 stays INCONCLUSIVE** and ASSURANCE V3.7 stays `UNRESOLVED`. Nothing
  here re-scores it.
- **This design is informed by Experiment 7's post-hoc, exploratory diagnosis**
  (`experiments/v7/agent/diagnose.py`; output saved verbatim in
  `experiments/v7/agent/DIAGNOSIS_2026-10-11.md`). It is a **new experiment**, not a re-run:
  - **The failure was at the first decision.** Under summed log-probability scoring,
    the 1-token ` finish` beat the 2-token ` check_calendar` / ` send_confirmation`
    (P(finish) = 0.994). The agent quit immediately in about 99% of runs.
  - **The model followed the task once it had a tool result** (P(send) = 0.998 after a
    calendar check).
- **The two changes in 7b:**
  1. Actions are chosen from a **numbered menu scored as single tokens**, which removes
     length bias by construction.
  2. The model is taken from an **instruction-tuned ladder**, gated by a **pre-declared
     competence check** that looks only at baseline behaviour.
- **Everything else is identical to Experiment 7:** task, cases, tools, the 0.5 timeout,
  factors, gates G1–G5, the INCONCLUSIVE rule, N and permutations. Only the seeds
  differ.

## 1. Agent changes relative to Experiment 7

**Prompt at each step** (the system prompt and history lines are as in Experiment 7):

```
<system prompt>
Task: Book a meeting with {person} on {day}.
<one line per previous step: "Step i: {action} -> {tool output}">
Actions:
1. check_calendar
2. send_confirmation
3. finish
Next action (1, 2 or 3):
```

**Scoring.**
- Score of action k = log p(label_k | prompt), using Experiment 1's teacher-forced
  scorer.
- Labels: ` 1`, ` 2`, ` 3`.
- **Single-token check, fixed in advance.** When a model loads, the runner checks that
  each label is exactly one token.
  - If ` 1`/` 2`/` 3` are not single tokens, the labels `1`/`2`/`3` (no leading space)
    are used instead.
  - If neither set is single-token, that model is **NOT RUN** and the ladder continues.
- Action probabilities = softmax(score / T), with T = 1.0. The history lines record the
  action name (e.g. `send_confirmation`), not the number.
- **Raw text, no chat template.** The prompt is given as plain text, without the
  model's chat template. That is a limitation for instruction-tuned models, stated here
  in advance.

## 2. Model ladder and competence check (fixed in advance)

**Ladder, tried in this order:**
1. `Qwen/Qwen2.5-0.5B-Instruct`
2. `Qwen/Qwen2.5-1.5B-Instruct`
3. `Qwen/Qwen2.5-3B-Instruct`

**Name check, done 2026-10-11 before this protocol was committed.** All three ladder
names are in `transformer_lens.loading_from_pretrained.OFFICIAL_MODEL_NAMES` in the
owner's environment (transformer-lens 2.17.0). Being in that list does not guarantee
that a model loads or fits in memory.

**Competence check.**
- For each model, *before any intervention run*, the exact baseline outcome
  distribution is computed for all 4 cases.
- The model is **competent** iff the mean over the 4 cases of the exact P(exactly 1
  email) at baseline is **≥ 0.6**.
- The **first competent model** on the ladder is used for the experiment. Later models
  are not run.
- The check uses only the baseline configuration. No factor effect is computed for a
  model until it has been selected.
- **No competent model on the ladder: INCONCLUSIVE**, with every model's competence
  value reported.

**Hardware.**
- Models 1–2 are expected to run on the owner's 8 GB Mac.
- Model 3 (3B in fp32, roughly 12 GB of weights; *approximate, not verified*) will
  likely need a **rented machine**. That requires the owner's approval of the cost, and
  must be recorded in RESULTS.md with the machine type.
- If model 3 is needed but no machine is approved, the result is **NOT RUN for model 3**.
  It is reported as such, with no substitution.

## 3. Design (identical to Experiment 7 except as stated)

| Setting | Value |
|---|---|
| Cases | c1–c4 (Dana/Tuesday, Ravi/Thursday, Mei/Monday, Tomas/Friday) |
| Factors | `system_prompt` (strict → helpful), `tool_format` (text → json), `framework_retry` (v1 → v2), `log_level` (info → debug, inert) |
| Agent | At most 4 decisions; email timeout probability 0.5 (always delivered); v2 auto re-send |
| Investigation | `run_interventions` per case, 10 cells, 30 runs per cell, `n_perm` 999, α = 0.05 (Holm within each case's family of 4) |
| Seeds | `"exp7b:<case>"` |
| Ground truth | Exact enumeration, as in Experiment 7. Classes: zero (`log_level`), large (≥ 0.5), small |
| Recording | As in Experiment 7, plus the menu label chosen, recorded as `glassbox.agent.action_label` |

## 4. Pre-declared criteria

The gates are G1–G5 exactly as in Experiment 7 §4, for the selected model.

**Overall result.**
- **INCONCLUSIVE** if no model on the ladder is competent, **or** if the selected
  model has no large (case, factor) pair.
- **PASS** iff G1–G5 all pass.
- **FAIL** otherwise.

**Descriptive:** the same as Experiment 7 (D1–D4), plus:
- **D5** every ladder model's competence value and single-token check;
- **D6** the selected model's exact baseline and candidate distributions, i.e. how
  often the duplicate-email incident occurs.

## 5. What a PASS would and would not show

**Would show:**
- On a small instruction-tuned LLM agent that does the task, Glassbox records every tool
  execution, including hidden framework retries.
- Its interventions blame the large real causes of a duplicate-email incident and not an
  inert change.
- Exact and sampled outcomes agree.
- **Hard Gate 8 would be met** for an in-repository agent.

**Would not show:**
- Production agent frameworks.
- Free-form tool calling: this is a fixed menu.
- Chat-templated prompting.
- Hosted models.
- Unknown causes (V2.4).

## 6. Execution

1. The ladder-name check is done (see §2).
2. Commit this protocol.
3. Implement `experiments/v7/agent_b/run.py` test-first, reusing Experiment 7's
   agent, enumerator, tracing and gates by import where they are unchanged.
   - Tests use a fake scorer with fake tokenisation.
   - No model is loaded in tests.
4. Commit the code.
5. Run:

   `python3 experiments/v7/agent_b/run.py --out experiments/v7/agent_b/results`

   The runner stops at the first competent model. If it reaches model 3 and the Mac
   cannot load it, it records NOT RUN and stops. The owner then decides whether to rent
   a machine and run model 3 alone, recorded as an addendum.
6. Commit `results.json` unchanged.

---
*(Addenda, if any, go below this line, with dates.)*

### Addendum 1 (2026-10-11): machine change and progress logging. No change to the design.

**Why the run moved.**
- The first run was started on the owner's 8 GB Mac at commit `b807af7`.
- After about 1 h 52 min it was thrashing: swap 20.1 GB used of 21.5 GB, the process at
  2.1% CPU and only about 0.75 GB resident. That was during the
  `Qwen/Qwen2.5-1.5B-Instruct` competence computation.
- It was stopped. **No `results.json` was written, and no factor effects had been
  computed.**

**Disclosed observation from the aborted run.** The ladder had moved past
`Qwen/Qwen2.5-0.5B-Instruct`, which means that model scored below the 0.6 competence
threshold. Its exact competence value was not printed. This observation uses only
baseline behaviour, which is what the competence rule allows.

**Changes.**
1. **Machine.** The run is repeated **from the start of the ladder** on a Kaggle
   notebook (CPU session). It uses the same commit, pinned package versions, seeds and
   `device="cpu"`; only the machine differs.
   - RESULTS.md must record the notebook's CPU count, RAM, Python version and key
     package versions, as printed by the runbook (`KAGGLE_RUN.md`).
   - Because the computation is deterministic, the 0.5B-Instruct competence on Kaggle is
     expected to repeat the Mac result. Any difference must be reported.
2. **Progress logging.** `run.py` now prints progress lines to stderr: model loading,
   competence, a count every 25 prompts scored, and per-case stages. These lines do not
   affect any computation. The tests are unchanged and still pass.

The design, ladder, threshold, gates, N, permutations and seeds are all unchanged.

### Addendum 2 (2026-10-12): run 1 completed, but its result files were lost; run 2 recovers them. No change to the design.

Written **after** run 1 finished and before run 2 starts.

**Run 1: what happened**
- **Where it ran:** Kaggle notebook, interactive CPU session (4 CPU, 31 GB RAM). Commit
  `2eb6aac`, Python 3.11.17 venv with the pinned stack, `device="cpu"`.
- **When:** 2026-10-11, 18:01–21:24 by the notebook clock.
- **Outcome:** it ran to completion and printed `EXPERIMENT 7b OVERALL: PASS`, with
  G1–G5 PASS, ladder 0.5B 0.327629 / 1.5B 0.52456 / 3B 0.686497 (selected), and the
  per-case table.
- **What was lost:** the interactive session had no persistence and was restarted before
  `results.json` and the traces could be downloaded. Those files no longer exist.
- **What survives:** the complete printed output of run 1, inside the notebook the owner
  downloaded. It is committed unchanged in `run1_kaggle/`:
  - `notebook_run1.ipynb`, sha256 `e790de2509ca8a272b5e09ce85eba1e591f9f9eb0c9170a424d5f36ddf7a024e`;
  - `run_log_run1.txt`, the run cell's output extracted verbatim, sha256
    `4cf1b275617abefaaf48afd1db4b78d7e46980d38c584071105781938905c1cf`.

**Run 2: rules fixed before it starts**
1. **Purpose:** recover the result files, not to get a second chance at the outcome.
   Everything is identical to run 1: same commit `2eb6aac`, same pins, seeds and
   `device="cpu"`, same command and the same Kaggle CPU machine type.
2. **How it runs:** as a Kaggle "Save Version → Save & Run All" batch run, whose
   `/kaggle/working` output is retained. At the end it prints `results.json`, its
   sha256 and `pip freeze` into the log.
3. **The computation is deterministic** given the seeds and environment (run 1's G4:
   max_abs_diff 0.0), so run 2's printed gate lines and per-case lines are expected to
   be **identical** to run 1's.
   - **If identical:** run 2's `results.json` is committed unchanged as the result
     artifact, and RESULTS.md reports both runs. The result is the pre-registered
     outcome, PASS.
   - **If any printed line differs:** both runs are reported in full. The experiment is
     recorded as **not reproduced**, and ASSURANCE V3.8 stays no higher than
     `PRELIMINARY` until the difference is explained. A differing run 2 is not used to
     replace or overrule run 1.
4. **Descriptive observations from run 1's log**, recorded now so they cannot be
   reframed later:
   - the candidate change mostly made the agent send **no** email (about 0.97 of runs
     sent zero), rather than duplicates (about 0.015 sent two or more);
   - `framework_retry` (true effect about 0.34, "small" class) was attributed in c1 and
     c3, but not in c2 and c4;
   - `log_level` in c2 showed an observed effect of 0.233 (p = 0.088, not attributed).

### Addendum 3 (2026-10-12): numeric-explanation check. No change to the design or to the 7b result.

Written after run 2 and before any explanation run.

**Why.**
- Run 2 matched run 1 on every gate, attribution, observed value and p-value.
- But 13 of 81 printed numbers differed in the 6th decimal (max 9×10⁻⁶).
- Under Addendum 2 this keeps ASSURANCE V3.8 at `PRELIMINARY` until the difference is
  explained.
- Hypothesis: the floating-point summation order differed between the two Kaggle sessions
  (thread split or CPU vector instructions). It does not affect results beyond the last
  digits.

**Check.** `experiments/v7/agent_b/explain_numeric.py`, at the commit that adds this
addendum, run on one Kaggle CPU machine with the same pinned environment. It recomputes
the competence of `Qwen/Qwen2.5-0.5B-Instruct` (run 1 0.327629, run 2 0.327631) in four
separate processes:

| Config | Setting |
|---|---|
| A1, A2 | Default, twice |
| B_threads1 | `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1` |
| C_scalar | `ATEN_CPU_CAPABILITY=default` (no vectorised kernels) |

It also records the CPU model, the AVX2/AVX-512 flags, the torch version, the thread
count and the ATen CPU capability of each process.

**Criteria** (TOL = 1×10⁻⁴):
- **E1:** A1 and A2 are bit-identical.
- **E2:** B or C differs from A1 by more than 0 and at most TOL.
- **E3:** every value is within TOL of both run 1 and run 2, and below 0.6, so the ladder
  decision is unchanged.

**Decision.**
- **E1 ∧ E2 ∧ E3 → EXPLAINED.** The run 1 / run 2 differences are attributed to
  floating-point summation order, and V3.8 may move to `EXPERIMENTALLY_SUPPORTED`.
  RESULTS.md states this as an explanation on one machine, not a proof about the two
  original sessions, whose CPUs were not recorded.
- **Anything else → NOT EXPLAINED.** V3.8 stays `PRELIMINARY` and the outcome is
  reported as it is.
- The check is run once, and its output is committed unchanged, whatever it shows.

**Scope.** Only the 0.5B competence is rechecked. It is one of the 13 differing numbers
and the cheapest to compute. The 3B values are not re-run.
