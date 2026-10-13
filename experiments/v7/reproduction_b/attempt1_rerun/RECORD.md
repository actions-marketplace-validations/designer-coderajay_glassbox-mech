# Experiment 9b, attempt 1 re-run (2026-10-13): record

`reports/` is the `exp9b-reports` artifact of this re-run, extracted unchanged. The
zip's sha256 is `dfcff50ff5df5308df442f10c3e2d71f2aaebbd899327b834f6c63f337983bae`.

## What it is

- **How it was started:** GitHub's **"Re-run jobs"** on Actions run `38303022533`
  (`reports/run.txt`: "attempt 2").
- **Why it is not attempt 2:** a GitHub re-run reuses the original commit `6c08ddc` and
  therefore the **unfixed** workflow (`reports/main.commit.txt`). It is not the
  attempt 2 of Addendum 1, which must start from the commit carrying the fix
  (`20fcea2`).

## Outcome: same defect, same 7 results

| Package | Verdict | Decisions verdict |
|---|---|---|
| v7-exp4-interventions | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp3b-noise-baseline-merge | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp2-llama-dedup | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp8-cross-stack | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp1-rag-fault | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp5-real-interventions | REPRODUCED | DECISIONS_REPRODUCED |
| v7-exp6-cross-model | DECISIONS_ONLY | DECISIONS_REPRODUCED |
| v7-exp3-noise-baseline | **not run** (step stopped after Experiment 6, as in attempt 1) | — |

- Every package that ran has the same decisions verdict as in attempt 1.
- Under Addendum 1 item 4, these 7 comparisons join the cross-attempt consistency
  check. They do not count towards B1 or B2.
