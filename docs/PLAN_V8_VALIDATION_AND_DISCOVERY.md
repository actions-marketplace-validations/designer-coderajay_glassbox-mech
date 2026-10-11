# Glassbox V8: Validation, Compute and Customer Discovery Plan

*Version 8.0, written 2026-10-11. It supersedes "Glassbox: Post-V7 Validation and Customer
Discovery Plan" (the V8 draft) and continues `docs/PLAN_V7_FINAL_UNIFIED.md`. V7's
hard gates (§54 of the V7 plan) remain the definition of V7 being done.*

**Changes from the draft**
- §2 records V7's actual status as of today.
- §3 adds a compute policy: when to use free GPUs, when to rent one, and why AirLLM is
  not used for current experiments.
- §4 fixes the order of the remaining work. It follows the owner's standing rules:
  **no plan item is skipped**, and **customer interviews come last, with a fully
  working demo**.
- The draft's guardrails, measures and decision gates are kept, shortened in a few
  places, in §§5–9.

---

## 1. Purpose and decision question

The question V8 must answer:

> **Can Glassbox uncover, and help verify, a consequential AI failure that existing
> tools cannot adequately diagnose (or can do so materially faster), and is that worth
> enough for a team to use repeatedly and pay for?**

**The product thesis is still a hypothesis.** Synthetic or author-designed experiments
show behaviour only on the cases tested. They do not establish production reliability or
product–market fit.

---

## 2. Where V7 stands (2026-10-11)

| Gate (V7 §54) | Status | Evidence |
|---|---|---|
| 1 Standardised trace | Met | trace.py; Experiments 1–7 |
| 2 Framework-independent diff (two stacks) | **Open** | Only one in-repo stack so far |
| 3 Real failure localisation | **Open** | Exp 2 (llama_index #21033) is a start, not a blind case |
| 4 Controlled intervention | Met (synthetic + real model, author-chosen factors) | Exp 4, Exp 5 |
| 5 Reproduction in an independent environment | **Open** | |
| 6 External users (≥ 5 real investigations) | **Open**: phase F | |
| 7 Cross-model | Met (local open-weight models) | Exp 6 (Pythia-160m, OPT-125m, Qwen2.5-0.5B) |
| 8 Agent | **Pending Experiment 7b** | Exp 7 INCONCLUSIVE (V3.7 UNRESOLVED) |
| 9 Evidence package | Met | `evidence/` packages Exp 3–6 |
| 10 Security / privacy | **Open** | |
| 11 Investigation benchmark | **Open** | |
| 12 Repeat usage | **Open**: phase F | |

**Experiment 7b (running on Kaggle CPU).** These competence values come from the run log
and must be confirmed against `results.json` before they are written anywhere else:

| Model | Competence (threshold 0.6) |
|---|---|
| Qwen2.5-0.5B-Instruct | 0.3276 (not competent) |
| Qwen2.5-1.5B-Instruct | 0.5246 (not competent) |
| Qwen2.5-3B-Instruct | 0.6865 (competent, so selected) |

The overall 7b result (PASS / FAIL / INCONCLUSIVE) is **not known yet**.

---

## 3. Compute policy (new)

### 3.1 Principle

The device is part of an experiment's protocol. Floating-point results on GPU differ
slightly from CPU results, so the exact distributions can differ in the last digits.
Therefore:

1. **An experiment that has been pre-registered keeps its device.** Experiment 7b was
   registered (Addendum 1) as `device="cpu"` and **finishes on CPU**. Moving it to a GPU
   part-way through would be a protocol deviation, so it will not be done.
2. **Every new protocol states its device before it is committed.** That covers the
   machine type, GPU model, dtype, and the torch / CUDA / driver versions. RESULTS.md
   records what was actually used.
3. **CPU vs GPU agreement becomes evidence, not a nuisance.** Re-running one finished
   experiment on a different device and comparing within a pre-declared tolerance is an
   independent-environment reproduction. It counts toward Gate 5 (phase C).

### 3.2 Order of preference (budget: about €100/month)

| Choice | When | Notes |
|---|---|---|
| 1. Kaggle notebook, **GPU T4/P100** | Default for all new model experiments | Free. A third-party source says the quota is about 30 GPU-hours/week; **check the quota shown in Kaggle's settings**. Sessions are time-limited, and outputs must be downloaded, since the session has no persistence. |
| 2. Google Colab free GPU | Backup when the Kaggle quota is used up | Free, but availability is not guaranteed and runtimes can be cut off. Runs must be resumable or short. |
| 3. Kaggle / Colab CPU | Small models, or experiments already registered on CPU | Slow. Exp 7b on 3B takes about 25–30 min per case. |
| 4. Rented GPU (hourly cloud) | Only if 1–3 cannot fit or finish the run | **Needs the owner's approval of the cost first**, with a stated cost cap within budget. RESULTS.md records the provider, machine type and cost. Tokens are entered by the owner. |

**Rough fit (approximate, not verified):** a 3B model in fp32 is about 12 GB of weights.
That should fit on a 16 GB T4/P100. A 7B model in fp32 will not fit, and would need fp16
on a larger GPU; switching dtype also changes numbers and must be pre-registered.

**Speed:** the GPU speed-up for this workload is likely large, but it is **not
measured**. Measure it on the first GPU run and record it; do not quote a guess.

### 3.3 Code change needed (test-first)

The scorers currently hard-code `device="cpu"`, for example in `demo_rag.py`
`GPT2Scorer`. Before the first GPU experiment:
- add a `--device {cpu,cuda}` option and a `--dtype` option, both defaulting to the
  current behaviour;
- record the device, GPU name, dtype, torch and CUDA versions in `results.json`;
- write tests first, using a fake scorer, so that no GPU is needed in CI.

Experiments already published do not change.

### 3.4 AirLLM: assessed, not adopted for current experiments

AirLLM (`lyogavin/airllm`, Apache-2.0) loads a model **one layer at a time from disk**,
so that very large models fit on small GPUs. Its size and VRAM numbers are the project's
own claims and have not been verified here.

It is not used now, for three reasons:
1. **It saves memory; it does not add speed.** Streaming layers from disk on every
   forward pass is generally slower than holding a model that already fits in memory.
   Our current models (≤ 3B) fit, so AirLLM would most likely make runs slower. This
   is my inference from how it works and has not been measured.
2. **It does not provide TransformerLens hooks.** Glassbox scorers use
   `HookedTransformer`. Changing the inference engine changes the scorer, which means a
   **new experiment** with its own protocol, not a speed-up of an existing one.
3. **Pinned stack.** It would add dependencies, such as `transformers` and possibly
   `bitsandbytes` versions, that may conflict with the pinned stack that made CI green.

**Possible later use (phase E, optional):** a behaviour-only (Level 1) check that the
investigation layer works on a large open-weight model (≥ 30B), using AirLLM purely as a
log-probability scorer. That would need its own pre-registration, a licence check of the
model weights, and a separate environment. Mechanistic (Level 4) claims would not be
made from it.

---

## 4. Order of work (no step is skipped)

Each experiment follows the standing sequence: **protocol committed → code committed
(test-first) → run → results committed unchanged → RESULTS.md + ASSURANCE.md →
evidence package.** FAIL is reported as FAIL, and INCONCLUSIVE as INCONCLUSIVE.

### Phase A: close Experiment 7b (Gate 8)
- [ ] Finish the CPU run on Kaggle. Download `results.json` and the run log at once.
- [ ] Commit them unchanged. Write RESULTS.md, recording the Kaggle machine (4 CPU,
      31 GB RAM, Python 3.11.17 venv via uv, commit 2eb6aac), all three competence values,
      and that the model-3 run cost nothing (it ran on free Kaggle CPU).
- [ ] Update ASSURANCE V3.8 and build the evidence package.
- [ ] Update `KAGGLE_RUN.md` with the py311/uv and editable-install steps that worked.

### Phase B: GPU readiness (§3.3)
- [ ] Add `--device` / `--dtype` to the scorers test-first, and record them in results.
- [ ] Add a Kaggle GPU runbook. Measure and record the speed of one short run.

### Phase C: reproduction (Gate 5)
- [ ] Add a one-command "reproduce from evidence package" path.
- [ ] Pre-register an independent-environment reproduction: re-run one completed
      experiment (e.g. Exp 5 or Exp 6) on a different machine and device, with a stated
      tolerance and pass rule.

### Phase D: second stack (Gate 2)
- [ ] Import traces from a second, different execution stack through an
      OpenTelemetry-compatible ingestion path, and diff them with the same engine.
- [ ] Test compatibility before claiming it.

### Phase E: technical validation and benchmark (Gates 3, 11), from the draft §4
- [ ] **Known-fault cases.**
  - RAG: stale index, retrieval configuration change, prompt regression, and fix
    verification.
  - Agent: wrong tool, skipped tool, wrong order, early stop, and answering without
    acting.
- [ ] **Negative controls** (no meaningful fault) to measure false positives.
- [ ] **Blind-diagnosis cases**: the cause is hidden from the investigator until the
      diagnosis is recorded (Gate 3).
- [ ] **Repeatability tests** under documented conditions.
- [ ] Record for every case: detection, false positives, diagnosis accuracy, time to a
      useful finding, fix verification, human assistance, reproducibility, and scope.
      Report denominators, failures and exclusions.
- [ ] Optional: large-model behaviour-only check (§3.4).

### Phase F: security, release, demo (Gate 10 + demo)
- [ ] Security/privacy document: redaction is best-effort unless validated, and
      hashing is not signing.
- [ ] Release; Space requirements on gradio 5.
- [ ] A fully working demo, covering one RAG and one agent investigation end to end.

### Phase G: customer discovery and design partners (Gates 6, 12), last
- [ ] 10–15 conversations, about past incidents, not opinions of the idea (questions
      in §6).
- [ ] 3–5 scoped design-partner trials; at least one real external failure if
      permitted.
- [ ] Workflow comparison on the same incident, against the partner's current process.
- [ ] Ask the strongest candidate for a paid pilot.
- [ ] Interview preparation happens here, with the finished demo.

**Recorded trade-off.** The draft recommended running discovery in parallel with the
technical work. The owner chose to run it last, with a working demo. The risk of that
choice is building validation for a problem that customers rank low. It will be revisited
only if the owner decides to.

### Phase H: paper
- [ ] Written only from committed results. Every citation goes through the citation
      ledger, verified.

---

## 5. Guardrails (kept from the draft)

- **Initial customer hypothesis:** teams running open-weight models in production,
  especially RAG and tool-using agents. This is a hypothesis to test.
- **Three separate claims.** Regression **detection**, failure **diagnosis** and
  **mechanistic explanation** are separate claims. Success at one does not establish the
  others.
- **No assumed link to mechanistic interpretability.** Do not assume it can diagnose
  application-layer faults (stale index, orchestration, tool wiring).
- **Evidence limits:**
  - A trace difference is evidence of a difference, not of a cause.
  - A hash manifest supports integrity checks; it does not prove the claim or act as a
    signature.
- **Honest reporting:** keep negative and inconclusive results. Never tune a benchmark
  after seeing its results and then call it pre-registered.
- **What doesn't count as evidence:** praise, free usage, downloads and stars are not
  willingness to pay.
- **Regulatory claims:** no claim of legal certification, and no claim that the EU AI
  Act requires mechanistic interpretability.

## 6. Discovery questions (kept from the draft)

1. What was the most recent AI regression or failure you investigated?
2. What changed before it appeared?
3. How did you discover it?
4. What tools, logs, traces and tests did you use?
5. How long did the diagnosis take, and who was involved?
6. What made the cause hard to find?
7. What was the operational or business impact?
8. How did you verify the fix?
9. What does your current workflow fail to explain or preserve?
10. How often does this happen?
11. Have you paid (for tools, time, or external help) to address it?
12. Could we use a sanitised real failure to compare workflows?

**Design-partner terms:**
- one time-limited investigation;
- success criteria agreed in advance;
- data access, retention and deletion agreed in writing;
- separate, explicit permission for any public case study;
- no promise that Glassbox will find the cause.

**Outreach:** warm introductions and opt-in communities first. Check the German/EU rules
on B2B email before any unsolicited message.

## 7. Decision gates (founder rules, not industry benchmarks)

**Continue** if:
- Glassbox finds or explains a consequential failure that the current workflow misses,
  or reaches a defensible diagnosis materially faster;
- the result is repeatable in scope, and the fix is verifiable by rerun;
- prospects commit time, data or money (a paid pilot is stronger evidence than praise);
- there is a reason for repeat use.

**Narrow or reposition** if:
- detection works but diagnosis is unreliable; or
- the value sits in one area only (RAG, or tool calls); or
- teams value evidence capture and fix verification more than model internals; or
- existing tools cover most of the workflow.

**Reconsider the thesis** if:
- existing tools are adequate; or
- controlled tests show no advantage; or
- diagnosis fails blind tests or negative controls; or
- serious prospects won't share a problem, run a trial, or commit to a paid next step;
  or
- integration is too costly.

## 8. Minimum evidence package before strong external claims

- Versions, environment and device; reproduction commands.
- Completed, failed, inconclusive and not-run experiments, all listed.
- Baseline and changed-run artifacts; the fault-injection protocol and criteria.
- Blind-test and negative-control results.
- Diagnosis and fix-verification evidence.
- Limitations and alternative explanations.
- Customer feedback kept separate from technical results; permission status for any
  external data.

## 9. What not to do

- No large dashboard or "Founder OS" before customer evidence.
- No rebuilding of generic observability, CRM or analytics.
- No moving a pre-registered experiment to new hardware mid-run, and no quoting an
  unmeasured speed-up.
- No calling a symptom a root cause, or a narrow experiment broad understanding.
- No hiding a failed experiment behind a later success.
- No claims of production readiness from selected passing tests.
