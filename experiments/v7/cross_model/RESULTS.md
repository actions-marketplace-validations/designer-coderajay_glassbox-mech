# V7 Experiment 6: the investigation across model families. RESULTS

*Protocol `PROTOCOL.md` v1.0 was committed in `74f1958` (2026-10-11 13:26:51 +0200)
before any code. The code was committed in `a0f8c7d` (13:30:47) before the run. The
results were committed unchanged in `3314c58` (14:42:57).*

*Run on the owner's Mac (CPU). All three models loaded; the Qwen fallback was not
needed; no rented machine was used.*

## Outcome: **PASS** (all three families pass X1–X3)

| Model | X1 sensitivity: large true effects blamed | X2 specificity: zero-effect pairs blamed | X3 determinism (max re-score diff) |
|---|---|---|---|
| `EleutherAI/pythia-160m` | **3/3** | **0/12** | **0.0** |
| `facebook/opt-125m` | **3/3** | **0/12** | **0.0** |
| `Qwen/Qwen2.5-0.5B` | **4/4** | **0/12** | **0.0** |

## Descriptive findings

### D1 Detection vs the exact true effect (30 runs per configuration)

| Model | Smallest true effect detected | Largest true effect missed |
|---|---|---|
| Pythia | 0.415 (q3, index; observed 0.333, p = 0.015) | 0.157 (q3, template; observed 0.20, p = 0.20) |
| OPT | 0.417 (q3, index) | 0.024 (q3, template) |
| Qwen 2.5 | 0.655 (q3, index) | 0.145 (q7, template; observed 0.033, p = 1.0) |

- Across all four model families now tested (GPT-2 in Experiment 5 plus these three),
  every true effect ≥ about 0.41 was detected, and every effect ≤ about 0.16 was missed
  at N = 30.
- **The Pythia q3 index effect (true 0.415) passed with p = 0.015**, just under the Holm
  threshold of 0.0167. Effects around 0.4 are at the edge of what 30 runs per
  configuration can detect.
- **Qwen q7 template:** the true effect is 0.145, but the sample showed only 0.033. This
  is sampling variation of the kind the method is built to tolerate. It means "not
  attributed" must be read as "not detected", which the report already says.
- **Large-effect pairs (X1) were mostly near-deterministic,** with true TVD ≈ 1 (q1, q2,
  q4). Only Qwen's q3 (0.65) was a less trivial large effect. **X1 is therefore an easy
  gate.** The informative results are X2, where 0 of 36 zero-effect pairs were blamed,
  and the detection limits above.

### D2 Diff vs intervention

The pattern is identical for all three models, and the same as GPT-2 in Experiment 5:
- **q1–q4:** the group diff flags the retrieval step first, and the interventions blame
  the index.
- **q5–q8:** the group diff flags the chat step first (the prompt text changed with the
  template), and **the interventions blame nothing**. For q7 there is a small template
  effect in Pythia (0.07) and Qwen (0.145) that was not detected.

### D3 Does each model use the retrieved context?

Yes for all three:
- the correct-answer rate at baseline is ≥ 0.999 on six of eight questions for every
  model;
- the hard questions are q3 and q7 (P(correct) 0.71–0.95).

### Notes

- **Qwen 2.5 warning.** TransformerLens printed *"You are not using LayerNorm, so the
  writing weights can't be centered! Skipping"*. I read this as an informational notice
  for models that use a different normalisation, not an error. *I have not verified that
  it has no effect on the scores.* X3 shows the scores are deterministic either way.
- **Trace label.** Experiment 5's runner labels every chat span `"gpt2"`, whatever the
  model (stated in `run.py`). Traces were not committed; `results.json` records the
  real model for every run.

## What this does and does not show

**Shows:** on four model families in total, the same investigation:
- blamed every large true effect;
- blamed none of the 36 exactly-zero effects in this experiment;
- produced bit-identical scores on re-scoring;
- had a similar detection limit across families (about 0.4 detected, about 0.16 missed
  at N = 30).

**Does not show:**
- Large models.
- Hosted or API models: the plan's gate mentions "model family/provider", and only
  local open-weights models were tested.
- Free-form generation (this is two-option sampling).
- Agents (Hard Gate 8).
- Causes Glassbox did not set up (V2.4).

**On Hard Gate 7.** The gate asks that the investigation layer work across more than one
model family. For **local open-weights models** that is now met: GPT-2, Pythia, OPT and
Qwen 2.5. Hosted providers have not been tested.
