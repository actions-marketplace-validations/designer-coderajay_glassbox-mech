# V7 Experiment 5: controlled interventions on GPT-2 RAG. RESULTS

*Protocol `PROTOCOL.md` v1.0 was committed in `47ce955` (2026-10-11 12:02:54 +0200)
before any Experiment 5 code. The code was committed in `d1ac3ec` (12:05:52) before the
run. The results were committed unchanged in `e47cf4e` (12:07:24), run on the owner's
Mac: GPT-2 small via TransformerLens, CPU, 30 runs per cell, 8 cells per question,
8 questions.*

## Outcome: **PASS** (all four gated criteria met)

| Criterion | Rule | Result |
|---|---|---|
| E1 Real fault attributed: stale index blamed for q1–q4 | 4/4 | **4/4** (sufficiency p = 0.001, the floor with 999 permutations) |
| E2 No false blame on the index for q5–q8 (true effect exactly zero) | ≥ 3/4 | **4/4** |
| E3 Inert `log_level` blamed | ≤ 1/8 | **0/8** |
| E4 Scorer determinism (all cached prompts re-scored) | ≤ 1e-9 | **0.0** |
| D4 Cross-check with Experiment 1's committed margins | descriptive | max abs diff **0.0** |

As stated in the protocol, E1 was close to mechanical: Experiment 1's margins flip sign
for q1–q4. The informative results are E2/E3 and the descriptive findings below.

## Descriptive findings

### D1 The prompt-template edit: not blamed anywhere, and why

`template` was attributed for **0/8** questions. GPT-2's two-option margins are
deterministic, so the **true** effect can be computed exactly, with no sampling, and
compared with what the interventions found. The probabilities below are for the full
index.

| Q | P(correct), context first | P(correct), question first | True TVD of the edit | Observed sufficiency p |
|---|---|---|---|---|
| q1, q2, q4, q5, q6, q8 | 1.000 | 1.000 | 0.000 | 1.0 |
| q3 | 0.876 | 0.768 | **0.108** | 0.306 |
| q7 | 0.786 | 0.740 | **0.046** | 0.263 |

- For six questions the edit has no effect at the reported precision. Not blaming it is
  correct.
- For q3 and q7 the edit has a **small real effect**, which 30 runs per cell cannot
  detect. Not blaming it there is a **miss of a small effect**, not evidence of no
  effect.
- **"Not attributed" means "no effect detected at this N", not "no effect".** The
  report wording ("did not detectably change") is correct on this point and should
  stay that way.

### D2 Necessity

- Reverting the index alone in the candidate was significant for q1–q4 and for no other
  question.
- Reverting `template` or `log_level` alone was never significant.
- No interaction showed up at this N. For q3, the index's effect is large: true
  P(correct) is about 0.88 with the full index and about 0.33 with the stale one.

### D3 Diff vs intervention

| Questions | Group diff, `first_beyond_noise` (merged) | Interventions blame |
|---|---|---|
| q1–q4 | `retrieval#0` documents; also flags `chat#0` | `index` |
| q5–q8 | **`chat#0` prompt hash**; flags nothing else | **nothing** |

For q5–q8 the diff reports a significant difference at the answer step. The prompt
really did change, because the template changed. **But the answer did not change**:
P(correct) is identical, at 1.0 for three of them, and the q7 change is too small to
detect.

So the diff tells you *where the runs differ*, and the interventions tell you *which
change matters for the outcome*. Here they disagree, and the interventions are right
about the outcome. This is the clearest real-model illustration so far of V2.2 (a
divergence is not a cause).

## What this does and does not show

**Shows** (one real model, one corpus, single author, not blind):
- The intervention engine runs end-to-end on a real language model with a stochastic
  outcome.
- It blamed the known real fault and nothing inert or zero-effect.
- Where the diff flagged an outcome-irrelevant change, the interventions did not blame
  it.

**Does not show:**
- Detection of small effects at N = 30. Template effects of TVD 0.05–0.11 were missed.
- Anything about unknown causes in systems Glassbox did not build. The factors here
  were chosen and switched by the author (V2.4, Hard Gate 3).
- Larger models, other providers, free-form generation (this is two-option sampling),
  or agents.
- A general claim about prompt templates.

## Practical guidance

- Use the diff to find *where* runs differ, and interventions to decide *which change
  matters*.
- A significant diff on a prompt or config field is not evidence that it caused a
  behaviour change.
- If a candidate cause is not attributed, check the effect size you can detect at your
  N before calling it harmless.
