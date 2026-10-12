# V7 Experiment 7b: investigating an LLM tool-using agent, with a competent agent. RESULTS

*Provenance, in commit order:*
- Protocol v1.0: `821333a`, committed before any code.
- Code: `b807af7`.
- Addendum 1 (move to Kaggle, progress logging): `2eb6aac`. This is the code that ran.
- Addendum 2 (run 1 files lost; rules for run 2): `7ae8a08`, 2026-10-12 09:10 +0200,
  committed after run 1 and before run 2.

`results/results.json` is run 2's file, committed unchanged.

## Outcome

| | |
|---|---|
| **Pre-registered result** | **PASS**, in both runs (G1–G5 all pass) |
| **Reproduction rule (Addendum 2)** | **Not reproduced bit-identically.** 13 of 81 printed numbers differ in the 6th decimal (max \|Δ\| = 9×10⁻⁶). Every gate, attribution decision, observed effect and p-value is identical. As pre-declared, ASSURANCE V3.8 is therefore `PRELIMINARY` until the difference is explained. |
| **Hard Gate 8** | Met on the pre-registered criteria for one in-repository agent, subject to the reproduction caveat above |

## Runs

| | Run 1 | Run 2 |
|---|---|---|
| **Where** | Kaggle interactive CPU session (4 CPU, 31 GB RAM) | Kaggle "Save & Run All" batch CPU session |
| **When** (notebook clock) | 2026-10-11 18:01 → 21:24 | 2026-10-12 07:17 → ~09:54 |
| **Code** | `2eb6aac` | `2eb6aac` |
| **Environment** | Python 3.11.17 venv (uv); torch 2.10.0, transformer-lens 2.17.0, transformers 4.57.6, numpy 1.26.4 | same pins (`run2_kaggle/env_freeze.txt`) |
| **Files kept** | Printed output only, inside the notebook (`run1_kaggle/`). `results.json` and traces were lost when the session restarted. | `results/results.json`, `run2_kaggle/run_log_run2.txt`, `run2_kaggle/env_freeze.txt` |
| **sha256** | notebook `e790de25…a7024e`; log `4cf1b275…05c1cf` | results.json `a4b4cabc…6f182d`; log `447e50f3…05dcfd`; zip `5b9b39c5…abef28` |

Traces were not committed (`settings.traces_committed: false`), as in Experiment 7.

## Model ladder (D5)

| Model | Labels (single-token check) | Competence, run 1 | Competence, run 2 | Status |
|---|---|---|---|---|
| Qwen2.5-0.5B-Instruct | `1`,`2`,`3` (no-space fallback) | 0.327629 | 0.327631 | not competent |
| Qwen2.5-1.5B-Instruct | `1`,`2`,`3` | 0.52456 | 0.524561 | not competent |
| Qwen2.5-3B-Instruct | `1`,`2`,`3` | 0.686497 | 0.686496 | **selected** (≥ 0.6) |

**Notes on the ladder:**
- The aborted Mac run (Addendum 1) had already shown that 0.5B was below threshold;
  Kaggle agrees.
- Protocol §2 expected model 3 to need a rented machine. It ran on free Kaggle CPU at
  no cost.

## Gates (identical in both runs)

| Gate | Result |
|---|---|
| G1 Sensitivity | 4/4 large (case, factor) pairs attributed, all `system_prompt`: **PASS** |
| G2 Specificity | `log_level` attributed in 0/4 cases: **PASS** |
| G3 Trace fidelity | 4/4 cases: **PASS** |
| G4 Determinism (within a run) | max \|Δ\| 0.0: **PASS** |
| G5 Exact vs observed | 4/4 cases: **PASS** |

## Per case (run 2 values; run 1 differs only in the 6th decimal of "true")

| Case | Factor | Class | True effect | Observed | p | Attributed |
|---|---|---|---|---|---|---|
| c1 | system_prompt | large | 0.668478 | 0.600 | 0.001 | yes |
| c1 | tool_format | small | 0.073651 | 0.033 | 1.0 | no |
| c1 | framework_retry | small | 0.345734 | 0.367 | 0.007 | yes |
| c1 | log_level | zero | 0.0 | 0.033 | 1.0 | no |
| c2 | system_prompt | large | 0.676227 | 0.500 | 0.001 | yes |
| c2 | tool_format | small | 0.068698 | 0.033 | 1.0 | no |
| c2 | framework_retry | small | 0.346425 | 0.300 | 0.045 | no |
| c2 | log_level | zero | 0.0 | 0.233 | 0.088 | no |
| c3 | system_prompt | large | 0.662118 | 0.700 | 0.001 | yes |
| c3 | tool_format | small | 0.032712 | 0.067 | 0.778 | no |
| c3 | framework_retry | small | 0.342375 | 0.400 | 0.005 | yes |
| c3 | log_level | zero | 0.0 | 0.067 | 0.769 | no |
| c4 | system_prompt | large | 0.660790 | 0.600 | 0.001 | yes |
| c4 | tool_format | small | 0.085966 | 0.067 | 0.807 | no |
| c4 | framework_retry | small | 0.340472 | 0.333 | 0.026 | no |
| c4 | log_level | zero | 0.0 | 0.100 | 0.578 | no |

The p-values are raw permutation p-values (999 permutations). Attribution applies Holm correction within each case's family of 4 at α = 0.05, which is why p = 0.045 and p = 0.026 are not attributed.

## What the incident actually was (D6, recorded in Addendum 2 before run 2)

Exact outcome distributions, P(number of emails sent):

| Case | Baseline 0 / 1 / 2+ | Candidate 0 / 1 / 2+ |
|---|---|---|
| c1 | 0.304 / 0.690 / 0.007 | 0.965 / 0.017 / 0.018 |
| c2 | 0.305 / 0.692 / 0.003 | 0.970 / 0.015 / 0.015 |
| c3 | 0.310 / 0.684 / 0.007 | 0.972 / 0.014 / 0.014 |
| c4 | 0.315 / 0.680 / 0.004 | 0.970 / 0.014 / 0.015 |

- **The behaviour change is mainly "the agent stopped sending the confirmation", not
  "the agent sent duplicates".** The duplicate rate rises only from about 0.005 to about
  0.016. The investigation correctly blamed the cause of the measured change in the
  outcome distribution, `system_prompt`. But the experiment does **not** show Glassbox
  explaining a duplicate-email incident in the everyday sense.
- **The baseline agent itself is imperfect:** about 0.31 of baseline runs send no email.

## Other descriptive findings

- **The hidden framework retry was found 2 of 4 times.** `framework_retry` has a real
  effect of about 0.34 ("small" class, below 0.5). It was attributed in c1 and c3 but
  missed in c2 (p 0.045) and c4 (p 0.026), which fail after Holm correction. This fits
  the detection limit seen in Experiment 6 at N = 30: effects ≥ ~0.41 detected,
  ≤ ~0.16 missed, 0.34 borderline.
- **The small effect was never detected.** `tool_format` (0.03–0.09) was never
  attributed.
- **A noise excursion on the inert factor.** `log_level` showed an observed difference
  of 0.233 in c2 (p 0.088) from sampling noise alone. It was not attributed, but it is
  close.

## Why the two runs differ, and what is not yet known

- **Same in both runs:** the code commit, package pins and seeds. Only the Kaggle session
  differed (interactive vs batch).
- **The differences are tiny:** at most 9×10⁻⁶, and only in the *exact* probabilities
  computed from model scores. The sampled outcomes, and therefore every observed value
  and p-value, are identical.
- **Most likely cause:** floating-point summation order on different CPU hardware or
  thread scheduling. That would explain why G4, within one run, shows 0.0 while two
  sessions differ. **This is a hypothesis, not a demonstrated explanation.** The CPU
  model of each session was not recorded, so it cannot be checked after the fact.
- **Consequence:** under the rule fixed in Addendum 2, V3.8 is `PRELIMINARY`, not
  `EXPERIMENTALLY_SUPPORTED`, until an explanation check is run and recorded.

## What this does and does not show

**Shows, on this in-repository agent:**
- Glassbox recorded every tool execution, including hidden framework retries (G3).
- One-factor interventions blamed the large real cause in every case and never the
  inert change.
- Exact and sampled outcomes agree.
- The pre-registered PASS repeated in a second session.

**Does not show:**
- production agent frameworks;
- free-form tool calling (actions came from a fixed menu);
- chat-templated prompting;
- hosted models;
- unknown causes (V2.4);
- reliable detection of mid-sized causes around 0.34;
- explanation of a duplicate-email incident as such (see D6).

The design and factors were chosen by the author, the cause was known by construction,
and nothing here has been reproduced independently.
