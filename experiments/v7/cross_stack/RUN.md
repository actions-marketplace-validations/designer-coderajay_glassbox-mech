# Running V7 Experiment 8 (cross-stack, Hard Gate 2)

Run these only **after** `PROTOCOL.md` (with its addenda) and the code are committed.
Run them from the repo root. Stack B's venv lives outside the repo, in
`~/.glassbox-venvs`.

## 1. Create stack B's pinned environment

```
python3 -m venv ~/.glassbox-venvs/exp8-stack-b
~/.glassbox-venvs/exp8-stack-b/bin/pip install -q "llama-index-core==0.14.19" "openinference-instrumentation-llama-index==4.6.0" "opentelemetry-sdk==1.45.1" "opentelemetry-exporter-otlp-proto-common==1.45.1" "opentelemetry-proto==1.45.1"
~/.glassbox-venvs/exp8-stack-b/bin/pip list | grep -i -E "llama-index-core|openinference|opentelemetry|protobuf"
```

The licences are recorded automatically in `results/stack_b_env.json`. Expected:
llama-index-core MIT; OpenInference and OpenTelemetry Apache-2.0; protobuf BSD-3-Clause.

## 2. Record stack B's traces (32 OTLP files)

```
~/.glassbox-venvs/exp8-stack-b/bin/python experiments/v7/cross_stack/subject.py record --out experiments/v7/cross_stack/results
```

## 3. S7: export Experiment 1's traces and parse them with the official OTLP schema

```
~/.glassbox-venvs/exp8-stack-b/bin/python experiments/v7/cross_stack/subject.py schema-check --out experiments/v7/cross_stack/results
```

## 4. Evaluate (main environment, the one that runs the Glassbox tests)

```
python3 experiments/v7/cross_stack/evaluate.py --results experiments/v7/cross_stack/results
```

Commit `results/` unchanged (OTLP files, imported traces, `schema_check.json`,
`stack_b_env.json`, `results.json`), whether the overall result is PASS or FAIL.
