# V7 Experiment 4: controlled one-factor interventions. RESULTS

*Protocol `PROTOCOL.md` v1.0 was committed in `30ce32f` (2026-10-11 11:47:28 +0200)
before any intervention code. The code was committed in `87cb447` (11:52:26) before
the run. The results were committed unchanged in `ad75d43` (11:55:30), run on the
owner's Mac. Master seed `20261011`, 50 runs per cell, 200 replications per world,
synthetic pipeline only.*

## Outcome: **PASS** (all four gated criteria met; I2 only narrowly)

| Criterion | Rule | Result | Wilson 95% CI (computed afterwards) |
|---|---|---|---|
| I1 Type I: V0, inert factor blamed | ≤ 0.08 | **0.025** (5/200) | 0.011–0.057 |
| I2 Single cause: V1, `retrieval_r` blamed | ≥ 0.80 | **0.825** (165/200) | **0.766–0.871** |
| I3 Inert not blamed: V1, `log_level` blamed | ≤ 0.08 | **0.02** (4/200) | 0.008–0.050 |
| I4 Two causes: V2, both blamed in the same replication | ≥ 0.80 | **0.90** (180/200) | 0.851–0.934 |

**I2 is a narrow pass.** Its confidence interval includes values below 0.80, and it is
below the rough power of about 0.9 I disclosed in the protocol. By the pre-declared
rule it passes. Read it as "about 0.77–0.87 power for this effect at 50 runs per cell",
not as comfortably above 0.80.

## Descriptive results

### Why I2 (0.825) is lower than retrieval attribution in V2 (0.90)

The same test, `baseline` vs `only_retrieval_r`, attributes retrieval in 165/200
replications in V1 but in 180/200 in V2. The effect is the same in both worlds: mean
P(correct) is about 0.785 at baseline and 0.46 with retrieval switched.

The difference comes from Holm's step-down rule:
- In V2, the other factor (`chat_cr`) is almost always strongly significant. Retrieval
  is then tested at the full α = 0.05.
- In V1, the other factor is the inert `log_level`, which is almost never significant.
  Retrieval must then clear α/2 = 0.025.

So a real cause is slightly harder to attribute when it sits next to inert co-changes.
This is a property of the multiple-testing correction, not a bug. It means power for a
real cause depends on how many inert factors are tested alongside it.

### I5 Total change, `baseline` vs `candidate`, unadjusted

Significant in 0.915 of V1 replications and 1.0 of V2.

### I6 Necessity: revert one factor in the candidate (not gated)

| World | `retrieval_r` | second factor |
|---|---|---|
| V1 | 0.855 | `log_level` 0.04 |
| V2 | **0.055** | `chat_cr` 0.375 |

In V2, reverting retrieval alone barely changes anything: mean P(correct) goes from
0.257 to 0.331. Once the answer step is broken, retrieval quality matters little. This
was predicted in the protocol (§2 and I6), and it is why necessity was not used for
attribution. **A "revert one change and see if it fixes it" check would have missed
retrieval as a cause in about 95% of V2 replications.**

### I7 Diff vs intervention, V1 (the headline contrast)

| | Rate |
|---|---|
| Group diff flags the `chat` step (baseline vs candidate) | **0.92** |
| Interventions blame anything other than `retrieval_r` | **0.02** |

In V1 the answer step's own behaviour is unchanged, and only retrieval changed. The
diff shows the change *propagating* to the answer step in 92% of replications. The
interventions blamed something other than the real cause in only 2%, and those were
the inert `log_level` false positives counted in I3. This is the case Experiment 3b
(D3) showed a diff cannot resolve.

### Misses

- **V1:** nothing attributed in 35/200 replications. These are missed detections, not
  wrong blame.
- **V2:** `chat_cr` attributed without `retrieval_r` in 19/200; nothing attributed in
  1/200; `retrieval_r` without `chat_cr` in 0/200. The retrieval effect is the smaller
  of the two, so it is the one missed.

## What this does and does not show

**Shows** (synthetic pipeline, 2 factors, single author, not blind):
- One-factor-at-a-time interventions with 50 runs per cell blamed the real cause(s)
  and rarely blamed an inert co-change (≤ 0.025).
- They separated two simultaneous causes in 0.90 of replications.
- Where the diff saw propagation, the interventions did not blame the downstream step.

**Does not show:**
- That this works on real systems. Real factors may not be independently switchable,
  re-runs cost money, and runs can have side effects (V2.4, Hard Gate 3).
- Power for smaller effects or more factors. The Holm penalty grows with every inert
  factor tested (see above).
- An interaction estimate. Only 2×2 cells were run.
- A general causal claim. Attribution holds for these factors, values, inputs and the
  answer-label outcome.

**V7 Hard Gate 4** ("changing the suspected factor changes the measured behaviour under
a predefined experiment") is met here on a **synthetic** system only. Experiment 1 met
the restore-and-recover form on GPT-2 with one injected cause. Gate 4 on a real system
with unknown causes remains open.

## Practical guidance (this pipeline and effect sizes only)

- Gate attribution on **switching a factor alone from the baseline**, not on "revert it
  and see if it fixes it". Reverting misses real causes when another change also
  breaks the system.
- Test only the factors that actually changed. Every extra inert factor costs power.
- Treat "nothing attributed" at 50 runs per cell as **inconclusive** for effects of
  this size or smaller.
