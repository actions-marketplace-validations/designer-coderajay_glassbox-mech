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
