# V7 Experiment 3b: redundant-field merging and a power curve. RESULTS

*Protocol `PROTOCOL.md` v1.0 was committed in `ff75707` (2026-10-05 20:34:58 +0200)
before any 3b code. The code was committed in `3462ed1` (2026-10-11 11:34:38) before
the run. The results were committed unchanged in `55e8bcf` (2026-10-11 11:42:55), run
on the owner's Mac. Master seed `20261006`, 200 replications per (world, N), synthetic
pipeline only.*

## Outcome: **PASS** (all six gated criteria met)

| Criterion | Rule | Result |
|---|---|---|
| A1′ Type I (W0), each N | ≤ 0.08 | N=10 **0.005**, 20 **0.02**, 30 **0.02**, 50 **0.015** |
| A2′ Chat localisation (W1, N=30) | ≥ 0.80 | **0.875** (175/200; Wilson 95% CI 0.82–0.91) |
| A2b′ No false upstream flag (W1), each N | ≤ 0.08 | **0.0 / 0.02 / 0.005 / 0.005** |
| A3′ Retrieval localisation (W2, N=30) | ≥ 0.80 | **0.94** |
| A4′ Free text untestable | 100% | **100%** |
| A7 Merge validity (W1, N=30) | ≥ 0.95 | **1.0** |

Experiment 3 is **unchanged**: it stays FAIL, and ASSURANCE V2.7 stays `REFUTED`.

## Descriptive results

The numbers below are computed from `results/results.json`. The confidence intervals
are Wilson 95% intervals, computed afterwards; the protocol did not ask for them.

### D1 Power curve (merged method)

| N per group | W1: first at `chat#0` | W1: any detection | W2: first at `retrieval#0` |
|---|---|---|---|
| 10 | 0.235 (CI 0.18–0.30) | 0.235 | 0.385 |
| 20 | 0.685 (CI 0.62–0.75) | 0.705 | 0.865 |
| 30 | 0.875 (CI 0.82–0.91) | 0.88 | 0.94 |
| 50 | 0.98 (CI 0.95–0.99) | 0.985 | 1.0 |

Detections at the wrong step (W1) were 0, 4, 1 and 1 of 200 at N = 10, 20, 30 and 50.
For an effect of this size, groups of about 10 runs miss most changes, and about 30 or
more are needed for ≥ 0.80. The effect is P(correct) ≈ 0.79 vs 0.34 at the answer step
in W1. **Smaller effects would need larger groups. That was not measured.**

### D2 Merge effect, on the same 3b traces

| N | W1 first at `chat#0`, merged | W1 first at `chat#0`, unmerged |
|---|---|---|
| 10 | 0.235 | 0.13 |
| 20 | 0.685 | 0.61 |
| 30 | 0.875 | **0.82** |
| 50 | 0.98 | 0.965 |

False alarms without merging were 0.005 / 0.005 / 0.005 / 0.0.

**Read this carefully.**
- Merging helps at every N on paired data, with the largest relative gain at small N.
- But the **unmerged** method reached **0.82** at N = 30 on these fresh seeds, above the
  0.80 threshold that Experiment 3 missed with 0.79. The intervals overlap:
  Experiment 3 158/200 has CI 0.73–0.84, and 3b unmerged 164/200 has CI 0.76–0.87.
- So Experiment 3's FAIL was a borderline outcome within sampling variation. It was
  not a broken method. Merging is a real but moderate improvement (+5.5 points at
  N = 30), not a rescue.

### D3 One cause vs two causes

| N | `chat` flagged in W2 (retrieval-only cause) | `chat` flagged in W3 (two causes) |
|---|---|---|
| 10 | 0.155 | 0.46 |
| 20 | 0.47 | 0.855 |
| 30 | 0.595 | 0.975 |
| 50 | 0.905 | 1.0 |

The group diff **cannot** tell a second cause apart from downstream propagation, and
this gets **worse as N grows**. At N = 50, `chat` is flagged in 90.5% of W2
replications, where there is no cause at `chat`. More data makes propagation more
detectable, not more separable. A downstream flag is never evidence of a second cause.
This is what V3 (controlled one-change-at-a-time re-runs) must address. V2.2 stays
`NOT_SUPPORTED`.

## What this does and does not show

**Shows** (synthetic pipeline only, single author, not blind):
- With redundant fields merged, the group diff localised a single injected change at
  the right step in 0.875 of replications at N = 30.
- False alarms stayed at or below 0.02 at every N from 10 to 50.
- A measured power curve is available to guide group sizes.

**Does not show:**
- Validity on other pipelines or real systems. These are the same worlds where
  Experiment 3's problem was found, so 3b is not an independent test of generality.
- Power for smaller effects.
- Separation of causes (D3).
- Anything about unknown causes (V2.4).
- Any change to Experiment 3's FAIL.

## Practical guidance (from D1; holds for this effect size only)

- Use at least about 30 runs per group, and treat "nothing significant" from smaller
  groups as **inconclusive**, not as "no change".
- Read every flag downstream of the first significant step as possible propagation.
