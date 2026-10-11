# V7 Experiment 7: investigating an LLM tool-using agent. RESULTS

*Protocol `PROTOCOL.md` v1.0 was committed in `cc37722` (2026-10-11 16:24:51 +0200)
before any code. The code was committed in `633f1c6` (16:30:50) before the run. The
results were committed unchanged in `0b80753` (16:49:01). Run on the owner's Mac (CPU),
`Qwen/Qwen2.5-0.5B`.*

## Outcome: **INCONCLUSIVE**, as pre-declared when no large effect exists

| Criterion | Result |
|---|---|
| G1 Sensitivity | **not applicable**: 0 large (case, factor) pairs |
| G2 Specificity (`log_level` blamed) | 0/4, pass |
| G3 Trace fidelity | 4/4 cases, pass. **Weakly tested:** only 2 of 1,200 sampled runs sent any email |
| G4 Determinism | 0.0, pass |
| G5 Exact vs observed | 4/4 cases, pass. **Trivially:** almost every run had the same outcome |

**Hard Gate 8 is NOT met by this experiment.**

## What happened: the agent did not do the task

- The exact outcome distributions show the agent sends **no email** with probability
  0.992–0.994 in every case under the baseline configuration, and about 0.999 under the
  candidate.
- Of 1,200 distinct sampled runs, **1,198 sent no email**. One sent one email, one sent
  two or more.
- So the incident (duplicate emails) almost never occurs, under any configuration.
- Every factor's true effect was tiny: the system prompt about 0.005, the framework
  retry about 0.0003, the tool format about 0.00003. There was nothing for the
  investigation to find.

This is a failure of the **test system** (the agent), not evidence for or against the
investigation method. It is reported as INCONCLUSIVE, as the protocol required. No
design change was made after seeing the data for this experiment.

## Post-hoc hypotheses (exploratory, not evidence)

1. **H1, length bias in action scoring.**
   - Each action's score is the *sum* of its tokens' log-probabilities.
   - Multi-token actions such as ` send_confirmation` are therefore penalised against
     short ones such as ` finish`.
   - This is a known pitfall of summed-log-probability choice scoring. I did not
     anticipate it in the protocol.
2. **H2, base model.** `Qwen2.5-0.5B` is not instruction-tuned and may not follow the
   task at all.

`diagnose.py` checks both on two baseline prompts. It prints the token counts, the
summed and mean log-probabilities, and the resulting action probabilities. It is
**exploratory and post hoc**; its output is not evidence for any claim.

## What would be needed (a new pre-registered experiment, not a re-run)

A follow-up (Experiment 7b) would need:
- action choice that does not penalise length, for example single-token labels in a
  numbered menu;
- an instruction-tuned model;
- a **pre-declared competence check**: the agent must send exactly one email with
  probability ≥ some threshold at baseline, computed exactly *before* any
  interventions. Otherwise it is INCONCLUSIVE again;
- a model ladder fixed in advance, e.g. Qwen2.5-0.5B-Instruct, then 1.5B-Instruct, then
  a rented larger model, so the model is not chosen after seeing results.

That design would be informed by this result, and its protocol must say so.

## What this does and does not show

**Shows:**
- The recording, exact enumeration, intervention and GOF machinery runs end-to-end on
  an LLM-driven tool loop with 464 distinct prompts.
- G3's trace-fidelity check worked on the few runs where emails were sent.

**Does not show:** anything about whether Glassbox can investigate an agent incident.
The incident did not occur.
