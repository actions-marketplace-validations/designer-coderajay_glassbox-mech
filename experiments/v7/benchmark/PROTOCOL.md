# V7 Experiment 10: the Glassbox Investigation Benchmark (Hard Gate 11)

*Protocol v1.0. Written 2026-10-12, before any benchmark code and before any case is
drawn. It is committed first and not changed afterwards. Deviations go in dated addenda
below the line.*

## 0. Question and gate

**V7 Hard Gate 11:** "Glassbox is evaluated against known-failure cases with
quantitative metrics."

The benchmark asks four questions:
1. Across many incidents with **known** causes, how often does Glassbox's investigation
   (noise-aware group diff plus one-factor interventions, `glassbox.v7.investigate`)
   **detect** the behaviour change and **name exactly the real causes**?
2. How often does it **blame a change that had no effect**?
3. How often does it **raise an alarm when nothing changed** the behaviour?
4. Does the **fix it implies** (reverting what it blamed) **actually restore** the
   behaviour?

It also compares Glassbox with two simple, automated stand-ins for common practice.

**What counts as meeting Gate 11.** The gate is met by **running this benchmark and
publishing all metrics**, whatever they show. The criteria in §6 decide only the
separate claim that Glassbox is **useful compared with the baselines** (ASSURANCE row
V10.1).

## 1. Units, families and ground truth

**Definitions:**
- An **incident** is a baseline configuration, a set of changed factors (the
  candidate), and a set of test items.
- A **unit** is one (incident, test item).
- **Ground truth** is computed **exactly**, never estimated: for each unit and each
  changed factor `f`, the true effect is the exact total-variation distance (TVD)
  between the outcome distribution at baseline and at baseline + only `f`.
  - Classes: **large** ≥ 0.5; **zero** = exactly 0.0; **small** otherwise.

### Family R: real model (GPT-2 small RAG)

- **Pipeline:** the RAG pipeline of Experiments 1/5: 8 fictional documents, 8 questions,
  bag-of-words retriever, GPT-2 small via TransformerLens, CPU.
- **Outcome:** sampled at temperature 1 from P(correct) = sigmoid(margin), where the
  margin is the teacher-forced log-probability margin of the correct over the
  distractor answer, as in Experiment 5.
- **Test items:** the 8 questions.
- **Factor pool** (base → candidate):
  - `index`: full → stale (d1–d4 missing);
  - `top_k`: 1 → 2;
  - `template`: context_first → question_first;
  - `preamble`: none → "Answer with one word." placed before the context;
  - `log_level`: info → debug;
  - `cache_mode`: off → on.

  `log_level` and `cache_mode` are recorded in the trace but do not affect the prompt or
  retrieval, so they are inert by construction.

### Family S: synthetic tool-using agent

- **Agent:** Experiment 7's booking agent loop (check calendar, send confirmation,
  finish; timeout 0.5; framework retry), driven by a **synthetic policy** whose
  per-step action probabilities are set directly by the configuration. No language
  model.
- **Faults are policy changes:**

| Factor | Agent fault it models | Effect |
|---|---|---|
| `skip_check` | skipped tool | P(check first) moves from 0.95 to `a` |
| `early_stop` | ending prematurely | P(finish before sending) moves from 0.02 to `b` |
| `wrong_order` | wrong tool order | P(send before check) moves from 0.03 to `c` |
| `resend_bias` | wrong tool | P(send again after "ok") moves from 0.02 to `d` |
| `framework_retry` | | v1 → v2 |
| `log_level` | | inert |
| `trace_sampling` | | inert |

  - The magnitudes `a`–`d` are drawn by the generator (§2). That spreads true effects
    across the large, small and zero classes.
- **Test items:** Experiment 7's 4 cases (c1–c4).
- **Outcome:** the number of emails sent (0 / 1 / 2+).

## 2. Case generation, with a sealed seed

**Generator** (`benchmark/generate.py`):
- **Positive incidents:** 12 in Family R and 12 in Family S.
  - Each changes **2 to 4 factors** drawn from the family's pool.
  - At least one of them is an inert or decoy factor whenever the pool allows.
- **Negative-control incidents:** 4 in R and 4 in S.
  - Each changes **only factors whose true effect is exactly zero for every test item**
    (inert factors, and policy factors drawn at their base value).
- **Seed:** all draws (factor choice, magnitudes) come from one seed.

**The seed is sealed before any benchmark code exists.**
1. The **owner** generates a random seed on their own machine and keeps it private (not
   in the repository, not shared with the assistant).
2. Only its **sha256** is recorded in Addendum 1, committed **before** any benchmark
   code.
3. After the code is committed, the owner reveals the seed, and the run uses it. The
   run checks that the revealed seed matches the hash and refuses to start otherwise.

So the code and criteria cannot be tuned to the specific cases. This is **blinded case
generation**, not a blind diagnosis by an independent person (that is Gate 3, which
stays open).

## 3. Methods compared

**All three methods share the same budget:**
- 30 runs per cell;
- seeds `bench:<incident>:<item>`;
- 999 permutations;
- α = 0.05, Holm-corrected within each unit's family.

| Method | Detects a change when | Blames |
|---|---|---|
| **GB: Glassbox** | the baseline vs candidate outcome permutation test is significant | factors whose one-factor sufficiency test is significant (`run_interventions`), only when a change was detected |
| **B0: revert everything** | the same test as GB | **every** changed factor, when a change is detected |
| **B1: one-pair first divergence** | one baseline run and one candidate run (first seed of each) differ (`diff_traces`) | the factor owning the first divergent step (ownership map in §3.1) |

### 3.1 Ownership map for B1 (fixed now)

| Family | First divergent step | Blamed factors |
|---|---|---|
| R | retrieval | `index`, `top_k` (if changed) |
| R | chat input | `template`, `preamble` (if changed) |
| R | root environment only | nothing (no detection) |
| S | the first tool or decision step that differs | every changed policy factor |
| S | a retry-flagged step | `framework_retry` |

B0 and B1 are **automated stand-ins** for common practice. They are **not** a study of
human engineers; no human time is measured.

## 4. Metrics (all methods, per family and pooled)

**On positive units (at least one large factor):**
- **M1 Detection rate.**
- **M2 Exact diagnosis:** the blamed set equals the set of large factors. An undetected
  unit counts as a miss.
- **M3 Large-cause recall.**

**On all units:**
- **M4 Zero-effect false blame:** blamed (unit, factor) pairs with true effect exactly 0,
  divided by all (unit, zero-effect factor) pairs.

**On negative-control units:**
- **M5 False alarm rate:** any detection or any blame.

**On positive units where a change was detected:**
- **M6 Fix verified:** reverting the blamed factors gives an exact outcome distribution
  within TVD 0.10 of baseline. Computed from the exact ground truth.

**Also reported:**
- **M7 Cost:** runs per unit.

**By effect class:** M2 and M3 are also reported for units whose largest true effect is
**small** (from 0.1 up to 0.5). These are descriptive, because Experiments 5–7b showed
that effects below about 0.4 are often missed at 30 runs per cell.

Every count is reported with its denominator and a 95% Wilson interval.

## 5. Ground truth and the large threshold

Effects and classes come only from exact computation:
- **Family R:** deterministic margins → P(correct) per configuration → exact
  distribution.
- **Family S:** exact enumeration of the agent tree.

A positive incident whose units, after drawing, contain **no** large factor at all is
still run and reported, but only its zero-effect factors contribute to M4. The generator
cannot see effects before drawing.

## 6. Pre-declared criteria for the "useful" claim (V10.1)

| ID | Criterion | Pass rule |
|---|---|---|
| K1 | GB exact diagnosis on positive units, pooled | ≥ 0.70 |
| K2 | GB exact diagnosis minus the better of B0/B1, pooled | ≥ +0.15 |
| K3 | GB zero-effect false blame, pooled | ≤ 0.05 |
| K4 | GB false alarm on negative controls, pooled | ≤ 0.10 |
| K5 | GB fix verified, among detected positive units | ≥ 0.80 |

**V10.1 is PASS iff K1–K5 all pass; otherwise FAIL.**
- The overall Gate 11 result is "met" in either case (§0).
- Per-family results are reported. K1–K5 are judged on the pooled numbers only.

## 7. Execution

1. **Before any code:** the owner records the seed's sha256 in Addendum 1 and commits.
2. **Code**, test-first:
   - `generate.py` (with the seed check);
   - the Family S synthetic policy;
   - the three methods;
   - scoring with exact ground truth;
   - `run.py`.

   Tests use toy scorers and no model. Commit.
3. The owner reveals the seed and runs it on their Mac (CPU):

   `python3 experiments/v7/benchmark/run.py --seed <seed> --out experiments/v7/benchmark/results`

4. Commit `results/` unchanged; write RESULTS.md and update ASSURANCE (V10, V10.1).

## 8. What this does and does not show

**Would show:**
- how well Glassbox's investigation names the real causes across 32 incidents with known
  causes, including decoys and negative controls, on a real small LLM RAG pipeline and
  a synthetic agent;
- whether it beats two simple automated alternatives, and whether its implied fixes
  work.

**Would not show:**
- performance on real production incidents or unknown causes (Gate 3);
- performance against skilled human engineers, or the time they save;
- performance on other models, frameworks or fault types;
- generalisation beyond the factor pools defined here.

The pools, generator and baselines were designed by the author.

---
*(Addenda, if any, go below this line, with dates.)*

### Addendum 1 (2026-10-12): sealed seed and implementation details, before any benchmark code

**Sealed seed.**
- The owner generated the seed on their own machine and stored it outside the
  repository (`~/.glassbox_bench_seed.txt`). It has the form `bench-` + 32 hex
  characters. The assistant has not seen it.
- Its sha256, of the stripped UTF-8 string, is:

  `7dff29241343a904eda8c01a9e49790b3cbd988f1cad6e756a5638a1d79b3742`

- `run.py` refuses to run unless `sha256(seed)` equals this value.

**Details fixed now** (clarifications of §1–§3; the criteria in §6 are unchanged):

1. **Negative controls change only inert factors.**
   - Family R draws 1–2 of `log_level`, `cache_mode`; Family S draws 1–2 of
     `log_level`, `trace_sampling`.
   - §2's "policy factors drawn at their base value" is dropped. A factor whose
     candidate equals its base is not a change, and `run_interventions` rejects it.
2. **Positive incidents.** k ∈ {2, 3, 4} changed factors, chosen uniformly. Of these,
   n_inert ∈ {1, …, min(2, k−1)} are inert (uniform) and the rest are drawn without
   replacement from the effectful pool:
   - **R:** `index`, `top_k`, `template`, `preamble`;
   - **S:** `skip_check`, `early_stop`, `wrong_order`, `resend_bias`, `framework_retry`.
3. **Family S magnitudes**, drawn uniformly and rounded to 3 decimals:

   | Factor | Range |
   |---|---|
   | `skip_check` | a ∈ [0.05, 0.90] |
   | `early_stop` | b ∈ [0.05, 0.80] |
   | `wrong_order` | c ∈ [0.05, 0.80] |
   | `resend_bias` | d ∈ [0.05, 0.90] |

4. **Family S agent, exactly specified.** At most 4 decisions. Actions: `check`, `send`,
   `finish`. Each state has weights, normalised to probabilities:

   | State | Weights |
   |---|---|
   | nothing done yet | check `w_check` (base 0.95, `skip_check` → a), send `w_order` (base 0.03, `wrong_order` → c), finish `w_stop` (base 0.02, `early_stop` → b) |
   | after a check, nothing sent | check 0.02, send 0.96, finish `w_stop` |
   | after a send that reported a timeout | send `q_t`, finish 1 − `q_t` |
   | after a send that reported ok | send `w_resend` (base 0.02, `resend_bias` → d), finish 1 − `w_resend` |

   - **Every send delivers one email.** With probability `p_t` the send times out:
     - framework v1: the agent sees the timeout;
     - framework v2: the framework silently re-sends (one more email, recorded on the
       tool span as `glassbox.tool.framework_retry`) and the agent sees "ok".
   - **Test items c1–c4** differ only in (`p_t`, `q_t`): (0.5, 0.5), (0.3, 0.6),
     (0.7, 0.4), (0.4, 0.3).
   - **Outcome:** emails sent, recorded as `0`, `1` or `2+`.
   - **Inert factors** (`log_level`, `trace_sampling`) are recorded only as root
     environment attributes.
5. **Family R pipeline, exactly specified.**
   - Retrieval: Experiment 5's bag-of-words cosine over the 8 documents, with
     `index = stale` dropping d1–d4. The top `top_k` documents are joined in rank order.
   - Prompt: Experiment 5's two templates. When `preamble` is on, `Answer with one
     word.\n` is prefixed.
   - P(correct) = sigmoid(margin), with GPT-2 small margins cached per distinct prompt.
   - Inert factors (`log_level`, `cache_mode`) are recorded only as root environment
     attributes. `top_k` is also recorded on the retrieval span, as in Experiment 5.
6. **B1 ownership map, made exact.** B1 takes the first divergence of
   `diff_traces(baseline run 0, candidate run 0)`, reusing GB's first runs, so there is
   no extra budget.
   - **Family R:**
     - aligned step `retrieval` → the changed factors among {`index`, `top_k`};
     - step `chat` → the changed factors among {`template`, `preamble`};
     - no divergence → no detection and no blame.
   - **Family S:**
     - a tool or decision step whose attributes include `glassbox.tool.framework_retry`
       in either run → `framework_retry`, if changed;
     - any other step → the changed factors among the four policy factors;
     - no divergence → no detection and no blame.
   - In both families, B1's **detection** = "a divergence exists".
7. **Ground truth.**
   - **Family R:** a factor's exact effect is |P_correct(baseline + only f) −
     P_correct(baseline)|. That is the TVD of the two-outcome distribution.
   - **Family S:** the exact TVD over {0, 1, 2+} from enumerating the decision and
     timeout tree.
   - **Fix check (M6):** the exact TVD between baseline and (candidate with the blamed
     factors reverted) must be ≤ 0.10.
