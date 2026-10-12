# Experiment 9, attempt 1 (2026-10-12): record

**No zip was downloaded from this attempt.** This record is transcribed from the
notebook output the owner pasted into the working session. It is reproduced in substance,
not byte for byte.

## Setup

- **Notebook A**, Kaggle "Save & Run All" on CPU.
- **main:** `fe8103ac784a7bd146f6d21c166a6dd46a344884`.
- **Machine:** Intel(R) Xeon(R) CPU @ 2.20GHz, 4 CPUs, AVX2.
- **Environment:** a separate venv per package, each with the default (CUDA) build of
  torch 2.10.0.

## Output

- `v7-exp4-interventions`: `artifacts/measurements/results.json: REPRODUCED`, then
  `VERDICT: REPRODUCED`.
- `v7-exp3b-noise-baseline-merge`, `v7-exp2-llama-dedup`, `v7-exp8-cross-stack` and
  `v7-exp1-rag-fault`: the venv installation failed with `No space left on device (os
  error 28)` while copying torch / nvidia wheels into `/kaggle/working`. The worktree
  checkouts also failed for lack of space. None of these packages ran. Their compare
  step raised `FileNotFoundError` for the missing `repro/.../results.json`.
- Notebook B was not started.

This is classified as an infrastructure failure (PROTOCOL §3 item 4 and Addendum 1).
