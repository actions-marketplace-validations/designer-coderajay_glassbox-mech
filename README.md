<div align="center">

<img src="docs/assets/og-image.png" alt="Glassbox — see inside the black box" width="820" style="max-width:100%;margin-bottom:8px;border-radius:12px"/>

# Glassbox

**Prove what your model actually did, and find out why your AI system changed.**

Trace the circuit behind a model's decision, measure how *faithful* that explanation is, and draft the EU AI Act **Annex IV** technical documentation from one function call, on open-weight models. A newer investigation layer compares runs of an AI system before and after a change and tests which change actually mattered.

[![PyPI version](https://img.shields.io/pypi/v/glassbox-mech-interp?color=blue)](https://pypi.org/project/glassbox-mech-interp/)
[![PyPI downloads](https://img.shields.io/pypi/dm/glassbox-mech-interp?color=blue&label=downloads%2Fmonth)](https://pypistats.org/packages/glassbox-mech-interp)
[![License: MIT core](https://img.shields.io/badge/Core-MIT-green.svg)](LICENSE) [![License: BSL 1.1](https://img.shields.io/badge/Compliance%20%2B%20Investigation-BSL%201.1-orange.svg)](LICENSE-COMMERCIAL)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![arXiv](https://img.shields.io/badge/arXiv-2603.09988-b31b1b?logo=arxiv)](https://arxiv.org/abs/2603.09988)
[![HuggingFace Space](https://img.shields.io/badge/🤗%20HuggingFace-Live%20Demo-yellow)](https://huggingface.co/spaces/designer-coderajay/Glassbox-AI-2.0-Mechanistic-Interpretability-tool)
[![Website](https://img.shields.io/badge/Website-glassbox--ai-blue)](https://repo-ashen-psi.vercel.app)

[**Website**](https://repo-ashen-psi.vercel.app) · [**Live Demo**](https://huggingface.co/spaces/designer-coderajay/Glassbox-AI-2.0-Mechanistic-Interpretability-tool) · [**Paper**](https://arxiv.org/abs/2603.09988) · [**PyPI**](https://pypi.org/project/glassbox-mech-interp/) · [**User Guide**](docs/USER_GUIDE.md) · [**What is proven**](ASSURANCE.md)

</div>

---

Most explainability tools describe a model **from the outside** and can't tell you whether the explanation is true. Glassbox reads the **inside**. It ranks every attention head by its causal effect on a decision, keeps the minimal circuit that drives it, and then *measures* how faithful that circuit is by re-running the model with parts ablated.

> **The finding behind the tool:** a model's confidence is essentially *uncorrelated* with how faithful its explanation is (**r = 0.009**). An auditor who relies on a confidence score is relying on something unrelated to faithfulness. Faithfulness has to be measured, not assumed.

**Two parts, two maturity levels:**

| Part | What it does | Status |
|---|---|---|
| **Circuit + faithfulness + Annex IV** | Explains one model decision and drafts documentation | Released on PyPI (`glassbox-mech-interp` 4.5.1) |
| **Investigation layer** (`glassbox/v7/`) | Explains why an AI system's behaviour changed between two versions | In this repository, **not yet in a PyPI release**; research stage (see [below](#investigating-why-an-ai-system-changed)) |

Every claim in this README is tracked, with its evidence and status, in [`ASSURANCE.md`](ASSURANCE.md).

---

## Install

```bash
pip install glassbox-mech-interp
```

Extras: `pip install "glassbox-mech-interp[compliance]"` (Annex IV engine) · `[jupyter]` (notebook widget) · `[dev]` (tests + lint).
No install? Try the **[live demo on Hugging Face](https://huggingface.co/spaces/designer-coderajay/Glassbox-AI-2.0-Mechanistic-Interpretability-tool)**.

To use the investigation layer, install from source:

```bash
git clone https://github.com/designer-coderajay/glassbox-mech.git
cd glassbox-mech
pip install -e ".[dev]"
```

## 60-second quickstart: explain one decision

```python
from transformer_lens import HookedTransformer
from glassbox import GlassboxV2

model = HookedTransformer.from_pretrained("gpt2")   # any open-weight transformer
gb    = GlassboxV2(model)

result = gb.analyze(
    prompt    = "When Mary and John went to the store, John gave a drink to",
    correct   = " Mary",
    incorrect = " John",
)

print(result["circuit"])         # [(9, 9), (9, 6), ...]  <- (layer, head)
print(result["faithfulness"])    # {'sufficiency': 1.0, 'comprehensiveness': 0.543, 'f1': 0.704, ...}
```

Measured on GPT-2 IOI with the current build: **suff 1.00 · comp 0.543 · F1 0.704 · Grade B**, in about 1.8 s on an Apple M1 Pro.

## What you get back

- **The circuit:** which attention heads causally drive the decision, ranked.
- **Faithfulness metrics and a grade (A–D):** sufficiency, comprehensiveness and their F1, *computed by ablation*, so they are reproducible rather than asserted.
- **A plain-English explanation** and a self-graded evidence tier.
- **An EU AI Act Annex IV file:** 9 sections, **8 auto-filled** from the evidence and content-hashed. §8 (Declaration of Conformity) is left for a human to sign.

```python
from glassbox import build_annex_iv_vault
vault = build_annex_iv_vault(gb_result=result, model_name="gpt2", provider="Acme Corp",
                             output_json="annex-iv.json", output_html="annex-iv.html")
```

## Honest by design

When a model can't do a task, Glassbox says so instead of inventing a clean story. Point it at raw GPT-2 for a credit decision and it finds no faithful circuit: **F1 0.00–0.08, Grade C, NON-COMPLIANT**. That refusal is intended; the tool won't certify what it can't explain. *("NON-COMPLIANT" here is Glassbox's own quality gate, not a legal ruling.)*

## Measured results

| | Value |
|---|---|
| **Method** | Attribution patching (activation difference × gradient): **3 forward passes**, not a search |
| **Speed** | About **1.8 s** for GPT-2 Small on an Apple M1 Pro (4.2 s on an 8-core CPU); **15–37× faster** than ACDC across the GPT-2 family, depending on circuit size and hardware (see `BENCHMARKS.md`) |
| **IOI benchmark** (GPT-2 Small, default circuit) | suff 1.00 · comp 0.543 · **F1 0.704 · Grade B** (1-head circuit). Full 26-head Wang et al. circuit: suff 1.00 · comp 0.47 · F1 0.64 |
| **Key finding** | Confidence–faithfulness correlation **r = 0.009** |
| **Validated scale** | **82M → 12B** across **9 architecture families** (10 model series) |
| **Quality** | **1,288 tests** passing, 76% coverage (full run 2026-10-12; see `docs/VALIDATION_LOG.md`) |

Full methodology and raw data: [`BENCHMARKS.md`](BENCHMARKS.md). Reproduce with `scripts/benchmark.py`.

## How it compares

| Approach | Faithfulness measured? | Needs open weights? | Speed (GPT-2) |
|---|---|---|---|
| **Glassbox** (attribution patching) | ✅ suff / comp / F1 | Yes | **1.8 s** |
| ACDC (Conmy et al. 2023) | ✅ | Yes | ~65 s |
| SHAP / LIME (black-box) | ❌ no guarantee | No (works on APIs) | varies |
| Confidence scores | ❌ (r = 0.009) | No | instant |

## Model coverage

Validated end-to-end on **nine architecture families** (ten model series; Yi uses the Llama architecture) from **82M to 12B**: GPT-2, Pythia/GPT-NeoX, GPT-Neo, OPT, Llama-3, Mistral, Gemma-2, Qwen2/2.5, Yi and Phi-3, with grouped-query attention and RMSNorm handled correctly.
- **Beyond about 13B:** gradient-based attribution needs a multi-GPU cluster. This is implemented but not yet validated live.
- **Closed APIs** (GPT-4, Claude, Gemini): only a weaker black-box tier is available, because faithfulness can't be measured without the weights.

See [`docs/VALIDATION_LOG.md`](docs/VALIDATION_LOG.md).

## EU AI Act: Annex IV

Providers of high-risk AI systems must draw up Annex IV technical documentation (Article 11). Glassbox auto-fills **8 of the 9 sections** from the model's measured behaviour. It maps to Article 13 (transparency), Article 72 (post-market monitoring) and Article 9 (risk), with a cross-walk to the NIST AI RMF and ISO/IEC 42001.

**Dates and penalties:**
- Under current law, high-risk obligations apply from **2 August 2026**.
- The Digital Omnibus (provisionally agreed 7 May 2026, pending adoption) would defer Annex III to **2 December 2027**. Plan against both dates.
- The penalty for documentation non-compliance is up to **€15M or 3% of global turnover** (Art. 99(4)).

> Glassbox produces **evidence and documentation**, not a conformity declaration. It is **not legal advice** and does not by itself make anyone compliant. The EU AI Act does not require mechanistic interpretability. See [Legal Notices](docs/USER_GUIDE.md#legal-notices--regulatory-disclaimer).

## Investigating why an AI system changed

*Research stage. In the repository, not yet in a PyPI release. Licensed under BSL 1.1.*

When a RAG assistant or an agent starts behaving differently after a week of changes (new index, edited prompt, new framework version), the investigation layer:

1. **Records** each run as a local trace: nested spans, tool calls and hashed content. Raw text is not stored by default.
2. **Compares** many runs before and after the change. A noise-aware group diff separates real differences from run-to-run sampling noise.
3. **Tests** each change alone and each change reverted alone, then reports which changes moved the outcome and which did not.
4. **Packages** the result as an evidence bundle with a sha256 manifest that anyone can verify.

Try the built-in demo, a small RAG incident with three simultaneous changes:

```bash
python -m glassbox.v7.investigate demo --out demo_out --scorer gpt2
```

It writes a plain-language `REPORT.md` and an evidence package. The same investigation is available as a tab in the Gradio demo (`dashboard/`).

### What has been tested so far

Each experiment was pre-registered: the protocol was committed before the code and the run, and the results were committed unchanged. All were designed and run by the author, with the cause known in advance; none has yet been reproduced independently.

| Experiment | Result | Status in [`ASSURANCE.md`](ASSURANCE.md) |
|---|---|---|
| 1. Controlled RAG fault (stale index) | First divergence at retrieval for 4/4 affected questions; silent on 4/4 unaffected; recovery confirmed 8/8 | Experimentally supported |
| 2. Real third-party bug (llama_index #21033) | Difference localised to retrieval; fix confirmed in a later version | Experimentally supported |
| 3. Group diff, single injected change, N = 30 | Localised in 0.79 of replications against a pre-declared 0.80 bar: **FAIL** | Refuted |
| 3b. Same, with redundant fields merged | 0.875 localised; false alarms ≤ 0.02 at every N from 10 to 50 | Experimentally supported |
| 4. Interventions, synthetic pipeline | Real cause blamed in 0.825 of replications; inert co-change blamed in ≤ 0.025 | Experimentally supported |
| 5. Interventions, GPT-2 RAG (3 co-changes) | Known fault blamed 4/4; zero-effect and inert changes never blamed. True template effects of 0.108 and 0.046 were **not** detected | Experimentally supported |
| 6. Same investigation on Pythia-160m, OPT-125m, Qwen2.5-0.5B | Every large true effect blamed (3/3, 3/3, 4/4); none of 36 zero effects. Detected effects of about 0.41; missed effects of about 0.16 | Experimentally supported |
| 7. Tool-using LLM agent (duplicate-email incident) | The agent almost never acted, so the test could not be scored: **INCONCLUSIVE** | Unresolved |
| 7b. Same incident with an instruction-tuned agent (Qwen2.5-3B-Instruct) | Large real cause blamed 4/4; inert change never blamed; hidden retries traced. **PASS** in two runs. The change was mostly "stopped sending", not duplicates. A mid-sized cause (about 0.34) was found 2/4 | Experimentally supported (second run matched every decision; 6th-decimal differences traced to floating-point summation order by a pre-registered check) |
| 8. Same fault on a second stack (LlamaIndex, traced by OpenInference/OpenTelemetry, imported from OTLP) | Import lossless 32/32; unchanged diff engine localised the fault 4/4, silent 4/4, recovery 8/8, deterministic 8/8; Glassbox traces pass the official OTLP schema 32/32 | Experimentally supported (retrieval only; one framework) |
| 9. Re-run 8 packaged experiments on Linux x86-64 (Kaggle) instead of the original macOS arm64 | 7/8 reproduced exactly (incl. Experiment 3's FAIL). Experiment 6: every decision the same, but one sampled run flipped from tiny float differences, so **FAIL** as pre-registered | Refuted (same-author; Gate 5 not met) |

**Not shown yet:**
- that it finds **unknown** causes in real production systems;
- that it works across frameworks in general (so far: one second stack, retrieval only);
- that it saves engineers time. There are **no external users so far**.

A first divergence shows *where* runs differ, not *why*. Causal statements need the controlled interventions above, case by case.

## How it works (circuit analysis)

1. **Discover:** rank every attention head by causal effect (attribution patching, 3 passes).
2. **Verify:** keep the minimal circuit, then measure sufficiency and comprehensiveness against full ablation.
3. **Document:** grade the result and write the content-hashed Annex IV file.

## Documentation

| | |
|---|---|
| **[User Guide](docs/USER_GUIDE.md)** | Full walkthrough, all examples, complete API reference |
| **[BENCHMARKS.md](BENCHMARKS.md)** | Methodology, hardware, reproducible numbers |
| **[ASSURANCE.md](ASSURANCE.md)** | Every claim with its evidence and status (supported, refuted, unresolved, planned) |
| **[Methodology & Assurance](docs/METHODOLOGY_AND_ASSURANCE.md)** | What's proven vs measured vs hypothesised |
| **[Trace spec](docs/v7/TRACE_SPEC.md)** | The investigation layer's trace format |
| **[CHANGELOG.md](CHANGELOG.md)** | Release history |
| **[Live docs site](https://repo-ashen-psi.vercel.app)** | Interactive overview |

## Limitations

- **White-box only for circuits:** circuit analysis needs weights, activations and gradients. Open models are fully supported; closed APIs get the black-box tier only.
- **Decisions, not free-form chat:** circuit analysis needs a contrast between two outcomes to attribute against.
- **Offline and sampled:** Glassbox audits representative decisions for documentation and monitoring. It is not a real-time monitor on every request.
- **Faithful ≠ fair:** it measures whether the explanation matches the computation, not whether the decision is correct or unbiased.
- **Investigation layer:**
  - so far validated only on small open-weight models and author-designed incidents;
  - small effects (about 0.16 and below at 30 runs per configuration) can be missed;
  - redaction of trace content is best-effort;
  - a hash manifest proves integrity, not truth.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and our [Code of Conduct](CODE_OF_CONDUCT.md), and run the suite with `pytest --cov=glassbox -v`.

## License

Glassbox is dual-licensed. [NOTICE](NOTICE) holds the authoritative file-by-file map.

| Component | License | Summary |
|---|---|---|
| Interpretability core (circuit discovery, faithfulness, everything not listed below), tests, examples, docs | **MIT** ([LICENSE](LICENSE)) | Use, modify and redistribute freely, including commercially |
| Compliance engine: `compliance.py`, `circuit_diff.py`, `risk_register.py`, `bias.py`, `audit_log.py`, `cross_model.py` | **BSL 1.1** ([LICENSE-COMMERCIAL](LICENSE-COMMERCIAL)) | See the summary below |
| Investigation layer: `glassbox/v7/`, `dashboard/v7_investigation.py` | **BSL 1.1** (from 2026-10-11) | See the summary below |

**BSL 1.1 summary:**
- **Free** for non-production use, and for production use inside your own organisation (for example, investigating or documenting your own AI systems).
- **Needs a commercial license** to offer a compliance, AI-governance, AI-investigation, debugging or observability service or product to third parties.
- **Converts to Apache-2.0** four years after each version is first published.
- Copies of `cross_model.py` and the investigation layer obtained before 2026-10-11 remain under the terms they were published with.

The circuit-discovery and faithfulness core stays MIT and is never feature-gated. For commercial licensing, contact mahale.ajay01@gmail.com. Academic and non-profit research use may qualify for a no-cost license.

## Citation

```bibtex
@article{mahale2026causally,
  title         = {Causally Grounded Mechanistic Interpretability for LLMs with Faithful Natural-Language Explanations},
  author        = {Mahale, Ajay Pravin},
  year          = {2026},
  eprint        = {2603.09988},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CL},
  doi           = {10.48550/arXiv.2603.09988}
}
```

---

<div align="center">
<sub>See inside the black box: causal circuits, measured faithfulness, EU AI Act Annex IV, and evidence for why an AI system changed.</sub>
</div>
