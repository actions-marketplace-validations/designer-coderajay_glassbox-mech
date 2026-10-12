# V7 Experiment 10: Glassbox Investigation Benchmark. RESULTS

*Provenance, in commit order:*
- Protocol v1.0: `5328a2b`, committed before any code and before the seed was revealed.
- Addendum 1 (sealed seed hash, exact implementation details): `379f8ee`.
- Code and tests (`generate.py`, `families.py`, `methods.py`, `score.py`, `run.py`,
  `tests/test_v7_benchmark.py`): `416262f`.
- Run once on the owner's Mac on 2026-10-12, after `416262f`, with the sealed seed
  (CLI refuses any other seed). GPT-2 small on CPU. Wall time was about one minute.

`results/results.json` is committed unchanged, sha256 `279d7d7e…ca031b27`. It contains the
seed in clear, as the protocol intended once the run was done. Its sha256 matches the hash
committed in Addendum 1 (`7dff2924…5638a1d79b3742`).

## Outcome

- **Hard Gate 11: MET.** The benchmark was run and every metric is published below.
- **V10.1 ("useful compared with the baselines"): PASS.** All five pre-declared
  criteria passed. K1 and K4 passed narrowly; see the caveats.

| Criterion | Rule | Value | Result |
|---|---|---|---|
| K1 GB exact diagnosis, pooled | ≥ 0.70 | 0.750 (21/28) | PASS |
| K2 GB minus the better baseline (B1, 0.500) | ≥ +0.15 | +0.250 | PASS |
| K3 GB false blame of zero-effect factors | ≤ 0.05 | 0.0033 (1/299) | PASS |
| K4 GB false alarm on negative controls | ≤ 0.10 | 0.021 (1/48) | PASS |
| K5 GB implied fix verified, detected positives | ≥ 0.80 | 0.833 (20/24) | PASS |

## What was run

- 32 incidents from the sealed seed: Family R (GPT-2 small RAG) R01–R12 plus negative
  controls RN01–RN04; Family S (synthetic tool-using agent) S01–S12 plus SN01–SN04.
- Units are (incident, test item) pairs: 8 questions per R incident, 4 items per S
  incident, so **192 units**: 144 from positive incidents and 48 from negative controls.
- **28 units were positive** (at least one factor with exact effect ≥ 0.5): 26 in
  Family R and 2 in Family S.
- Every method had the same budget: 180 traced runs per unit (n_per_cell 30, 999
  permutations, α 0.05).
- Methods:
  - **GB** is Glassbox `run_interventions`;
  - **B0** reverts every changed factor;
  - **B1** blames the owner of the first divergent step of one run pair.

## Pooled metrics (all three methods)

Values are k/n with 95% Wilson intervals.

| Metric | GB | B0 (revert all) | B1 (first divergence) |
|---|---|---|---|
| M1 Detection (positive units) | 24/28 = 0.857 [0.685, 0.943] | 24/28 = 0.857 [0.685, 0.943] | 28/28 = 1.000 [0.879, 1.000] |
| M2 Exact diagnosis | **21/28 = 0.750** [0.566, 0.873] | 0/28 = 0.000 [0.000, 0.121] | 14/28 = 0.500 [0.326, 0.674] |
| M3 Large-cause recall | 24/28 = 0.857 [0.685, 0.943] | 24/28 = 0.857 [0.685, 0.943] | 28/28 = 1.000 [0.879, 1.000] |
| M4 Zero-effect factors blamed | **1/299 = 0.003** [0.001, 0.019] | 79/299 = 0.264 [0.217, 0.317] | 18/299 = 0.060 [0.038, 0.093] |
| M5 False alarm (negative units) | **1/48 = 0.021** [0.004, 0.109] | 1/48 = 0.021 [0.004, 0.109] | 15/48 = 0.312 [0.199, 0.453] |
| M6 Fix verified (detected positives) | 20/24 = 0.833 [0.641, 0.933] | 24/24 = 1.000 [0.862, 1.000] | 27/28 = 0.964 [0.823, 0.994] |
| M7 Traced runs per unit | 180 | 180 | 180 (reuses 2) |
| Small units, exact (descriptive) | 10/39 = 0.256 [0.146, 0.411] | 0/39 | 7/39 = 0.179 |
| Small units, recall (descriptive) | 13/43 = 0.302 [0.186, 0.451] | 26/43 = 0.605 | 33/43 = 0.767 |

## Per family

| | GB M2 | GB M4 | GB M5 | GB M6 | GB small exact |
|---|---|---|---|---|---|
| R (GPT-2 RAG) | 19/26 | 0/203 | 0/32 | 18/22 | 1/11 |
| S (synthetic agent) | 2/2 | 1/96 | 1/16 | 2/2 | 9/28 |

The baselines per family are in `results.json` (`per_family`).

## Where GB fell short

**1. Four positive units had no observable outcome change, and GB stayed silent.**
- The units are R10 q5, R10 q6, R11 q5 and R11 q6.
- On these, `top_k = 2` alone has a large effect (0.634 on q5, 0.928 on q6).
- But the full candidate configuration differs from baseline by TVD 0.000009 and 0.0.
  The co-changes cancel at the outcome level.
- GB tests the total change first and found nothing to explain. These four units are
  all of GB's M1 misses and four of its seven M2 misses.
- The ground truth defines "large" by each factor alone, so these units count as
  positive. Whether an incident with no visible outcome change should count as
  positive is a property of the pre-registered design. It is reported here, not
  changed after the fact.

**2. Three exact-diagnosis misses were over-blame of a real small cause.**
- R10 q1, R10 q4 and R11 q4: GB blamed `index` (large, 0.9995 to 0.9999) together with
  `top_k` (small but real, 0.23 to 0.29).
- No zero-effect factor was blamed here, but M2 requires the blamed set to equal the
  large set exactly.

**3. The four fix failures left a small real cause in place.**
- R06 q3, R10 q3, R11 q1 and R11 q3.
- GB blamed only the large factor. Reverting it left the small effect (0.11 to 0.28),
  above the 0.10 tolerance.

**4. The one false alarm.**
- SN01 c2: inert `log_level` only, total test TVD 0.233, p = 0.045. GB blamed
  `log_level`.
- This is the one false blame in M4 and the one false alarm in M5. At α 0.05 over 48
  negative units, about two such events are expected by chance.

**5. Small effects are mostly not diagnosed.**
- Exact diagnosis on small-effect units was 10/39 and recall 13/43, below both
  baselines' recall.
- This is consistent with Experiments 5–7b: effects of about 0.1–0.3 at N = 30 are
  often below detection.

## How the baselines behaved

- **B0 (revert all)** always fixes what it detects, but blames every co-change. It
  wrongly blamed 26% of the zero-effect factors.
- **B1 (first divergence)** "detects" whenever any trace differs, outcome change or
  not. That gives it perfect M1 and M3 but a 31% false-alarm rate on inert-only
  controls, and half its diagnoses are not exact.

## Caveats (read these before citing the numbers)

1. **Few positive units.**
   - Only 28 of 192 units were positive, so the K1 interval is wide (0.57–0.87) and
     includes values below 0.70.
   - K1 passed as a point estimate by 0.05. The K4 upper bound (0.109) is above 0.10.
2. **Family R dominates.**
   - 26 of the 28 positive units come from Family R. The S magnitude ranges mostly
     produced small effects, as disclosed before the run.
   - The pooled K1–K2 result is in effect a Family R result.
3. **Units are not independent.**
   - Units share incidents: 8 questions per R incident.
   - The generator drew two identical factor sets twice: R04 = R05 and R10 = R11, with
     only the order differing.
   - The Wilson intervals treat units as independent, so they overstate precision.
4. **The design is the author's own.**
   - The baselines are automated stand-ins, not human engineers.
   - The factor pools, families and generator were designed by the author. The seed
     only prevents choosing incidents after seeing results.
5. **Not blind diagnosis.** The causes come from a known pool. This is not Gate 3 (a
   blind real failure) and says nothing about unknown causes in production systems.
6. **Same author, one machine, one run.** No independent reproduction yet.

## Status changes

- ASSURANCE **V10** (benchmark run, Gate 11): `PLANNED` → `EXPERIMENTALLY_SUPPORTED`.
- ASSURANCE **V10.1** (useful vs baselines): `PLANNED` → `EXPERIMENTALLY_SUPPORTED`,
  scoped to this benchmark with the caveats above.
- ASSURANCE **V6** (Investigation Benchmark exists): `PLANNED` → `IMPLEMENTED`.
