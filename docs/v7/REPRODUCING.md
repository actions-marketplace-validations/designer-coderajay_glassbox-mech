# Reproducing a Glassbox V7 result independently

This guide is for someone **other than the author** who is willing to check a V7 result.
An independent reproduction is the only thing that lets a result in
[`ASSURANCE.md`](../../ASSURANCE.md) reach the status `REPRODUCED`. The author's own
re-runs (Experiments 9 and 9b) do not.

**What is asked of you.** About 30–60 minutes and a computer with Python 3.11 and Git.
No GPU and no accounts are needed, and no data leaves your machine. You decide whether
your name appears in the record.

## 1. Pick an experiment

Short, model-free ones are the best start:

| Package | What it tests | Typical run time |
|---|---|---|
| `v7-exp4-interventions` | Controlled interventions on a synthetic pipeline | minutes |
| `v7-exp3b-noise-baseline-merge` | Noise-aware group diff | minutes |
| `v7-exp8-cross-stack` | OpenTelemetry/OpenInference traces from LlamaIndex, imported and diffed | minutes (two venvs) |
| `v7-exp1-rag-fault` | Stale-index fault in a GPT-2 RAG pipeline | about 5–15 min; downloads GPT-2 small |

Run times are rough estimates from the author's runs; yours will differ.

## 2. Get the plan

```
git clone https://github.com/designer-coderajay/glassbox-mech.git
cd glassbox-mech
python3 -m venv .venv-main
.venv-main/bin/pip install -e .
.venv-main/bin/python -m glassbox.v7.reproduce plan evidence/v7-exp4-interventions
```

The install pulls in PyTorch and the pinned stack, which is a large download.

`plan` first checks that the evidence package is intact (every file's sha256). Then it
prints the exact steps:
1. check out the commit whose code produced the packaged result, in a separate folder;
2. create a Python 3.11 environment with the pinned packages;
3. run the recipe command (it writes to `repro/`);
4. compare.

## 3. Run it

Follow the printed steps in a **second clone** checked out at the printed commit. If
your machine has no `python3.11`, any way of getting Python 3.11 works (for example,
`uv venv --python 3.11`). Please note how you did it.

## 4. Compare and send the report

From the first clone (current `main`):

```
.venv-main/bin/python -m glassbox.v7.reproduce compare evidence/v7-exp4-interventions <second-clone>/repro/exp4/results.json --reproducer "Your Name (or an alias)" --environment "your OS, CPU, Python" --out reproduction_report.json
```

**Verdicts:**
- `REPRODUCED`: everything identical, with floats within 10⁻⁴.
- `DECISIONS_ONLY`: only floats differ.
- `NOT_REPRODUCED`: something else differs.

Each report also carries a decision-level verdict. **Every outcome is useful,
including `NOT_REPRODUCED`.**

Send `reproduction_report.json` and, if you can, your terminal log to the author:
mahale.ajay01@gmail.com, or open a GitHub issue. Tell us how you want to be named:
full name, alias, or not at all.

## 5. What happens with your report

- It is committed unchanged under `experiments/v7/independent/`, with the name you
  chose.
- If it is `REPRODUCED` and you are independent of the author, the experiment's
  ASSURANCE row can move to `REPRODUCED`, naming you as the reproducer.
- If it is not, the row says so.

**Independent** means you were not involved in designing or running the experiment, and
you ran it on your own machine.

**Privacy.** The report contains your chosen name, the environment text you typed, and
a platform string. Nothing else about you is recorded.
