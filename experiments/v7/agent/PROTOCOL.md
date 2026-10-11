# V7 Experiment 7: investigating an LLM agent that sends duplicate emails (Hard Gate 8)

*Protocol v1.0. Written 2026-10-11, BEFORE any Experiment 7 code and before any run.
It is committed first and not changed afterwards. Deviations go in dated addenda below
the line.*

## 0. Why this experiment

V7 Hard Gate 8 requires that at least one agent workflow can be traced and
investigated. Experiments 1–6 were single-step RAG.

This experiment uses a **multi-step tool-using agent**:
- an LLM chooses actions in a loop;
- tools return outputs that feed back into the next choice;
- a framework layer can retry calls;
- the failure is a side effect (duplicate confirmation emails), not a wrong answer.

The incident comes from the simulated interview persona S2: a prompt edit plus a
framework upgrade in the same week, followed by duplicate confirmation emails. It is a
**simulation-derived scenario, not user evidence**.

**Ground truth is exact, as in Experiment 6.**
- At every step the agent samples its action from the model's own deterministic
  probabilities over a fixed action set.
- The tool and framework behaviour is fully specified.
- So the exact outcome distribution under any configuration is computable by
  enumerating the (finite) tree of runs.

## 1. The agent (fixed)

**Model.** `Qwen/Qwen2.5-0.5B` via TransformerLens, on CPU. It loaded and ran in
Experiment 6, and no fallback is declared.

**Action scoring.**
- Score = teacher-forced log p(action text | prompt), with Experiment 1's scorer used
  unchanged.
- Action probabilities = softmax(score / T), with T = 1.0.
- Each run uses a seeded `random.Random(run_seed)`.

**Task (one per test case).** "Book a meeting with {person} on {day}."

| Case | Person | Day |
|---|---|---|
| c1 | Dana | Tuesday |
| c2 | Ravi | Thursday |
| c3 | Mei | Monday |
| c4 | Tomas | Friday |

**Actions** (the text scored after the prompt; the leading space is part of the text):
- ` check_calendar` → tool `check_calendar(day)`;
- ` send_confirmation` → tool `send_confirmation(person, day)`, which sends 1 email;
- ` finish` → stops the run.

**Loop.**
- At most **4 decisions** per run; a run also stops at ` finish`.
- **Prompt at each step:**

  ```
  <system prompt>
  Task: Book a meeting with {person} on {day}.
  <one line per previous step: "Step i: {action} -> {tool output}">
  Next action:
  ```

**Tools (deterministic except the timeout).**
- `check_calendar(day)` returns the day as free, in the format set by the factor below.
- `send_confirmation` always delivers the email (the email counter goes up by 1).
- **Email API timeout.** With probability **0.5**, drawn from the run's RNG, the
  delivery acknowledgement is lost and the call reports `timeout`. *The email was still
  delivered* (at-least-once delivery). This probability is fixed and is not a factor.

**Outcome:** the number of emails sent, as `"0"`, `"1"` or `"2+"`. `"1"` is the
correct behaviour.

## 2. Factors (candidate = all four changed)

| Factor | Base | Candidate |
|---|---|---|
| `system_prompt` | `You are a booking assistant. Check the calendar once, send exactly one confirmation, then finish.` | `You are a helpful booking assistant.` |
| `tool_format` | `check_calendar` returns `{day}: available` | returns `{"day": "{day}", "free": 1}` |
| `framework_retry` | v1: on `timeout`, the agent sees `send_confirmation -> error: timeout` and decides itself | v2: on `timeout`, the framework **automatically re-sends once** (1 extra email, whose own timeout is ignored). The agent then sees `send_confirmation -> ok` |
| `log_level` | `info` | `debug` (recorded as `glassbox.env.log_level`; inert) |

**Ground-truth notes, stated in advance.**
- `log_level` has exactly zero effect by construction.
- The effects of the other three factors are model-dependent and are computed exactly
  per case before any sampling.
- `framework_retry` is expected to raise `"2+"` whenever the agent sends and the call
  times out, but its true size depends on the model's policy.

## 3. Recording and investigation

**Each run is recorded with the Glassbox Recorder:**
- one `chat` span per decision, with the prompt hashed and the attribute
  `glassbox.agent.action`;
- one `execute_tool` span per tool execution, **including framework retries**, carrying
  `gen_ai.tool.name` and `glassbox.tool.result` (`ok` / `timeout`);
- the root attribute `glassbox.env.log_level`.

**Investigation.** `glassbox.v7.intervene.run_interventions`, unchanged, per case.

| Setting | Value |
|---|---|
| Factors | k = 4: 10 distinct cells (baseline, candidate, 4 × `only`, 4 × `all_but`) |
| Runs per cell | 30 |
| Permutations | `n_perm` = 999 |
| Multiple testing | α = 0.05, Holm within each case's sufficiency family of 4 |
| Seed | `"exp7:<case>"` |

**Group diff (descriptive).** `group_diff` (merged) on `baseline` vs `candidate`, per
case.

**Exact ground truth.** For every case and every relevant configuration, the exact
outcome distribution is computed by enumerating all decision paths and timeout events,
with the same cached scores. From it: true TVD(f, case) = TVD between the exact
`baseline` and exact `only_f` outcome distributions. The classes are as in Experiment 6:
- **zero:** `log_level`, by construction;
- **large:** ≥ 0.5;
- **small:** otherwise.

## 4. Pre-declared criteria

| ID | Criterion | Pass rule |
|---|---|---|
| G1 Sensitivity | Every **large** (case, factor) pair is attributed | all large pairs |
| G2 Specificity | `log_level` attributed | ≤ 1 of 4 cases |
| G3 Trace fidelity | In every run, the number of `execute_tool` spans named `send_confirmation` equals the emails actually sent, including framework retries | 100% of runs, all cells and cases |
| G4 Determinism | All cached action scores re-scored | ≤ 1e-6 |
| G5 Exact-vs-observed sanity | In the `baseline` cell of each case, the observed outcome frequencies are consistent with the exact distribution: a chi-square goodness-of-fit with categories merged so that each expected count is ≥ 5 (or an exact multinomial test if merging leaves one category), at α = 0.01 | ≥ 3 of 4 cases |

**Overall result.**
- **INCONCLUSIVE** if no (case, factor) pair is **large**. Then G1 cannot be tested,
  and the experiment does not show sensitivity, whatever else passes.
- **PASS** iff G1–G5 all pass and at least one large pair exists.
- **FAIL** otherwise.

**Descriptive (not gated):**

| ID | What is reported |
|---|---|
| D1 | Exact outcome distributions for baseline and candidate per case: how often the incident ("2+") occurs |
| D2 | True vs observed TVD, p and the attribution for every pair |
| D3 | Group-diff `first_beyond_noise` and flagged steps per case, next to the attributions. The question: does the diff point at the email step while the cause is the framework retry or the prompt? |
| D4 | Necessity results; interactions such as the prompt edit mattering only with v2 retries |

## 5. What a PASS would and would not show

**Would show:**
- On a small but real LLM-driven tool loop, Glassbox records every tool execution,
  including the hidden framework retries.
- Its interventions blame the large real causes of a side-effect incident and not the
  inert change.
- Its exact checks agree with the sampled runs.

**Would not show:**
- Production agent frameworks: this agent is written in the repository, not LangChain,
  LlamaIndex or similar.
- Free-form tool calling: actions are chosen from a fixed set by scoring.
- Larger models or hosted APIs.
- Unknown causes (V2.4).

## 6. Execution

1. Commit this protocol.
2. Implement `experiments/v7/agent/run.py` test-first.
   - Tests use a fake scorer only; no model is loaded.
   - The exact enumerator is checked against brute-force sampling on the fake scorer.
   - G3 is checked on a run where the framework retries.
3. Commit the code.
4. Run on the owner's Mac:

   `python3 experiments/v7/agent/run.py --out experiments/v7/agent/results`
5. Commit `results.json` unchanged. Traces are not committed (regenerable).

---
*(Addenda, if any, go below this line, with dates.)*
