# V7 Experiment 4: controlled interventions. Which of several changes caused it?

*Protocol v1.0. Written 2026-10-11, BEFORE any intervention code and before any run.
It is committed first and not changed afterwards. Deviations go in dated addenda below
the line.*

## 0. Why this experiment

Experiments 3 and 3b showed (D3) that a *diff* cannot tell one cause from two. A change
at retrieval propagates downstream, and at N = 50 the answer step was flagged in 90.5% of
replications whose only cause was retrieval. This is plan §12–13 and V7 Hard Gate 4:
changing the suspected factor must change the measured behaviour under a predefined
experiment.

**What is new:** Glassbox *re-runs* the system with one change at a time, instead of
only comparing what already happened.

## 1. Question

A candidate configuration differs from a baseline in *k* factors, and its behaviour
differs. Can one-factor-at-a-time interventions with repeated runs:

1. attribute the behaviour change to the factor(s) that actually cause it;
2. **not** attribute it to a factor that changed but has no effect (an *inert* factor);
3. stay silent when no factor has an effect?

## 2. The method under test (fixed before implementation)

New module `glassbox/v7/intervene.py`, standard library only, reusing
`glassbox.v7.groupdiff.tvd`, `permutation_p` and `holm`.

**Inputs**
- **Factors.** An ordered list of `(name, base_value, candidate_value)`.
- **Runner.** `runner(config, run_seed, out_dir, run_id) -> trace path`. It is supplied
  by the user and runs the system once under `config`, recording a Glassbox trace.
- **Outcome.** `outcome(trace path) -> hashable`. It is supplied by the user and is the
  behaviour that matters, e.g. the final answer label.
- **Settings.** `n_per_cell`, `n_perm`, `alpha`, `seed`.

**Cells** (configurations run; duplicates are run once and shared)
- `baseline`: every factor at its base value.
- `candidate`: every factor at its candidate value.
- `only_<f>`: baseline with factor *f* switched to its candidate value.
- `all_but_<f>`: candidate with factor *f* reverted to its base value.

For k = 2 this is the full 2×2 factorial (4 distinct cells). Each cell gets
`n_per_cell` runs with **independent** seeds derived from `(seed, cell config, i)`. The
design is unpaired; no seeds are shared across cells.

**Tests**
- Each test compares the outcome distribution of two cells. The statistic is TVD, and
  the p-value comes from a permutation test, exactly as in the group diff.
- **Total change** (reported): `baseline` vs `candidate`.
- **Sufficiency family** (confirmatory): for each factor, `baseline` vs `only_<f>`, with
  Holm across the *k* tests at α.
  - A factor is **attributed** iff its sufficiency test is significant. Reported
    wording: "switching *f* alone from the baseline changed the outcome distribution
    (TVD, p)".
- **Necessity family** (descriptive): for each factor, `candidate` vs `all_but_<f>`,
  with a separate Holm across the *k* tests.
  - Reported wording: "reverting *f* alone in the candidate changed the outcome
    distribution".
  - *Stated in advance:* with interactions, necessity can be weak even for a real
    cause. For example, once another factor has already broken the answer, reverting
    retrieval changes little. So it is not gated.
- **Output.** Outcome counts per cell, every test with TVD, p and the Holm decision,
  the attributed factors, and the evidence wording above.
- **Not claimed.** The method does not state "*f* caused the failure" in general. An
  attribution holds for the factors, values, inputs and outcome measure tested (plan
  §30, "intervention evidence").

## 3. Design (synthetic; ground truth known by construction)

The pipeline is Experiment 3's three-step stochastic pipeline. It is reused by import
from `experiments/v7/noise_baseline/part_a.py` (`simulate_run`, `BASELINE`), unchanged.
Three factors are available:

| Factor | Base | Candidate | Effect |
|---|---|---|---|
| `retrieval_r` | r = 0.90 | r = 0.40 | real: fewer right documents |
| `chat_cr` | c_r = 0.85 | c_r = 0.35 | real: fewer correct answers given the right document |
| `log_level` | `"info"` | `"debug"` | **inert**: recorded as an attribute on the root, with no effect on behaviour |

**Outcome:** `glassbox.answer.label` of the `chat` span (`correct` / `distractor`).

| World | Candidate changes | k | Truth |
|---|---|---|---|
| V0 | `log_level` | 1 | nothing should be attributed |
| V1 | `retrieval_r`, `log_level` | 2 | `retrieval_r` only |
| V2 | `retrieval_r`, `chat_cr` | 2 | both |

| Setting | Value |
|---|---|
| Runs per cell | `n_per_cell` = 50 |
| Replications | R = 200 per world |
| Permutations | `n_perm` = 999 |
| α | 0.05 |
| Master seed | `20261011` |
| Replication seed | `"<master>:<world>:<rep>"` |

**Disclosure.** N = 50 was chosen from Experiment 3b's power curve (D1), plus a rough
hand calculation. For `retrieval_r`, P(correct) is about 0.785 vs 0.46, which suggests
power of about 0.9 at N = 50 with Holm over 2 tests. That calculation is an
expectation, not a result.

## 4. Pre-declared criteria

| ID | Criterion | Pass rule |
|---|---|---|
| I1 Type I | V0: `log_level` attributed | ≤ 0.08 of replications |
| I2 Single cause | V1: `retrieval_r` attributed | ≥ 0.80 |
| I3 Inert not blamed | V1: `log_level` attributed | ≤ 0.08 |
| I4 Two causes | V2: `retrieval_r` attributed **and** `chat_cr` attributed | ≥ 0.80 (both in the same replication) |
| I5 Total change detected (**descriptive**) | V1, V2: `baseline` vs `candidate` significant at α (no correction) | Reported |
| I6 Necessity (**descriptive**) | V1, V2: necessity-family results per factor | Reported. Expected: `retrieval_r` necessity weak in V2 (interaction) |
| I7 Diff vs intervention (**descriptive**) | V1: rate at which the **group diff** (`merge_redundant=True`) on `baseline` vs `candidate` flags `chat#0`, next to the rate at which interventions attribute `chat_cr` | Reported. Contrasts "where it shows up" with "what caused it" |

**Overall result.**
- **PASS** iff I1, I2, I3 and I4 all pass.
- I5–I7 are descriptive.
- A FAIL is reported as a FAIL. Thresholds, N, worlds and seeds are not changed after
  any run.

## 5. What a PASS would and would not show

**Would show:** on this synthetic pipeline, one-factor-at-a-time interventions with 50
runs per cell attribute a behaviour change to the real cause(s), do not blame an inert
co-change, and separate two simultaneous causes. This is the case the diff could not
handle (Experiments 3/3b, D3).

**Would not show:**
- That this works on real systems, where factors cannot always be switched
  independently (V2.4, Hard Gate 3).
- Anything about factors with small effects, or about more than 2 factors.
- A general causal claim: attribution holds only for the tested values, inputs and
  outcome measure.
- That interactions are characterised. Only the 2×2 cells are run, with no estimand for
  the interaction.

## 6. Execution

1. Commit this protocol.
2. Implement `glassbox/v7/intervene.py` test-first, with unit tests on toy runners only.
   Then implement `experiments/v7/intervention/run.py`, which reuses Experiment 3's
   pipeline and adds the inert `log_level` attribute. Experiment 4 is not run during
   development, except smoke tests with non-protocol settings.
3. Commit the code.
4. Run on the owner's Mac:

   `python3 experiments/v7/intervention/run.py --out experiments/v7/intervention/results`
5. Commit `results.json` unchanged. Traces go to a temporary directory and are not
   committed (regenerable from the seeds).

---
*(Addenda, if any, go below this line, with dates.)*
