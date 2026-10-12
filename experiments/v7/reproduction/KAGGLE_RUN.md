# Running V7 Experiment 9 (reproduction in an independent environment) on Kaggle

Run only **after** `PROTOCOL.md` is committed. Two notebooks, each a Kaggle "Save
Version → Save & Run All (Commit)" batch run on **CPU** with **Internet on**. Each one
paste is a single `%%bash` cell.

- **Notebook A** covers the fast packages: Experiments 4, 3b, 2, 8 and 1.
- **Notebook B** covers the model-heavier ones: Experiments 5, 6 and 3.

Each cell:
1. clones the current `main`, prints its commit, and sets up a Python 3.11 venv with the
   pinned stack (for the `compare` step);
2. for each package, checks out the **recipe commit** in its own git worktree, builds a
   Python 3.11 venv there with the same pins (the uv equivalent of the recipe's setup,
   per PROTOCOL §3), runs the recipe's **run commands exactly**, and compares with
   `python -m glassbox.v7.reproduce compare`;
3. writes everything (commit, `uv pip freeze`, run log, comparison output and report) to
   `/kaggle/working/reports`, zipped as `repro_A.zip` / `repro_B.zip`.

Download the zip from the saved version's **Output** tab and commit its contents
unchanged under `experiments/v7/reproduction/reports/`.

## Notebook A (Experiments 4, 3b, 2, 8, 1)

```
%%bash
set -uo pipefail
W=/kaggle/working
MAIN=$W/glassbox-mech
PINS='"numpy==1.26.4" "scipy==1.17.1" "einops==0.8.2" "torch==2.10.0" "transformer-lens==2.17.0" "transformers==4.57.6" "pyarrow==23.0.0" "datasets==4.5.0" "pandas==3.0.0" pytest'
cd $W && rm -rf glassbox-mech wt reports && git clone -q https://github.com/designer-coderajay/glassbox-mech.git
git -C $MAIN log -1 --format='%H %s'
pip install -q uv
uv venv $W/main --python 3.11 -q
eval uv pip install -q --python $W/main/bin/python $PINS
uv pip install -q --python $W/main/bin/python -e $MAIN --no-deps
lscpu | head -20
CPU="$(lscpu | grep 'Model name' | sed 's/Model name:[[:space:]]*//') / Linux x86-64 / Kaggle CPU"
mkdir -p $W/reports
prep () {
  rm -rf $W/wt/$1
  git -C $MAIN worktree add -q $W/wt/$1 $2
  git -C $W/wt/$1 log -1 --format='%H %s' > $W/reports/$1.commit.txt
  uv venv $W/wt/$1/.venv-repro --python 3.11 -q
  eval uv pip install -q --python $W/wt/$1/.venv-repro/bin/python $PINS
  uv pip install -q --python $W/wt/$1/.venv-repro/bin/python -e $W/wt/$1 --no-deps
  uv pip freeze --python $W/wt/$1/.venv-repro/bin/python > $W/reports/$1.freeze.txt
}
cmp () {
  p=$1; shift
  (cd $MAIN && $W/main/bin/python -m glassbox.v7.reproduce compare evidence/$p "$@" --reproducer "Ajay Pravin Mahale (author)" --environment "$CPU" --out $W/reports/$p.json) 2>&1 | tee $W/reports/$p.compare.txt
}

prep v7-exp4-interventions ad75d43
(cd $W/wt/v7-exp4-interventions && .venv-repro/bin/python experiments/v7/intervention/run.py --out repro/exp4) > $W/reports/v7-exp4-interventions.log 2>&1
cmp v7-exp4-interventions $W/wt/v7-exp4-interventions/repro/exp4/results.json

prep v7-exp3b-noise-baseline-merge 55e8bcf
(cd $W/wt/v7-exp3b-noise-baseline-merge && .venv-repro/bin/python experiments/v7/noise_baseline_3b/run.py --out repro/exp3b) > $W/reports/v7-exp3b-noise-baseline-merge.log 2>&1
cmp v7-exp3b-noise-baseline-merge $W/wt/v7-exp3b-noise-baseline-merge/repro/exp3b/results.json

for v in 0.14.17 0.14.19; do uv venv ~/.glassbox-venvs/li-$v --python 3.11 -q; uv pip install -q --python ~/.glassbox-venvs/li-$v/bin/python "llama-index-core==$v"; done
prep v7-exp2-llama-dedup 72cb710
(cd $W/wt/v7-exp2-llama-dedup && for v in 0.14.17 0.14.19; do for p in sync async; do for r in r1 r2; do ~/.glassbox-venvs/li-$v/bin/python experiments/v7/llama_dedup/subject.py --path $p --run $r --out repro/exp2; done; done; done && .venv-repro/bin/python experiments/v7/llama_dedup/evaluate.py --results repro/exp2) > $W/reports/v7-exp2-llama-dedup.log 2>&1
cmp v7-exp2-llama-dedup $W/wt/v7-exp2-llama-dedup/repro/exp2/results.json

uv venv ~/.glassbox-venvs/exp8-stack-b --python 3.11 -q
uv pip install -q --python ~/.glassbox-venvs/exp8-stack-b/bin/python "llama-index-core==0.14.19" "openinference-instrumentation-llama-index==4.6.0" "opentelemetry-sdk==1.45.1" "opentelemetry-exporter-otlp-proto-common==1.45.1" "opentelemetry-proto==1.45.1"
prep v7-exp8-cross-stack 226a4eb
(cd $W/wt/v7-exp8-cross-stack && ~/.glassbox-venvs/exp8-stack-b/bin/python experiments/v7/cross_stack/subject.py record --out repro/exp8 && ~/.glassbox-venvs/exp8-stack-b/bin/python experiments/v7/cross_stack/subject.py schema-check --out repro/exp8 && .venv-repro/bin/python experiments/v7/cross_stack/evaluate.py --results repro/exp8) > $W/reports/v7-exp8-cross-stack.log 2>&1
cmp v7-exp8-cross-stack $W/wt/v7-exp8-cross-stack/repro/exp8/results.json

prep v7-exp1-rag-fault aedfebf
(cd $W/wt/v7-exp1-rag-fault && .venv-repro/bin/python experiments/v7/rag_fault/run.py --out repro/exp1) > $W/reports/v7-exp1-rag-fault.log 2>&1
cmp v7-exp1-rag-fault $W/wt/v7-exp1-rag-fault/repro/exp1/results.json

cd $W && zip -qr repro_A.zip reports && ls -la reports && grep -h VERDICT reports/*.compare.txt
```

## Notebook B (Experiments 5, 6, 3)

```
%%bash
set -uo pipefail
W=/kaggle/working
MAIN=$W/glassbox-mech
PINS='"numpy==1.26.4" "scipy==1.17.1" "einops==0.8.2" "torch==2.10.0" "transformer-lens==2.17.0" "transformers==4.57.6" "pyarrow==23.0.0" "datasets==4.5.0" "pandas==3.0.0" pytest'
cd $W && rm -rf glassbox-mech wt reports && git clone -q https://github.com/designer-coderajay/glassbox-mech.git
git -C $MAIN log -1 --format='%H %s'
pip install -q uv
uv venv $W/main --python 3.11 -q
eval uv pip install -q --python $W/main/bin/python $PINS
uv pip install -q --python $W/main/bin/python -e $MAIN --no-deps
lscpu | head -20
CPU="$(lscpu | grep 'Model name' | sed 's/Model name:[[:space:]]*//') / Linux x86-64 / Kaggle CPU"
mkdir -p $W/reports
prep () {
  rm -rf $W/wt/$1
  git -C $MAIN worktree add -q $W/wt/$1 $2
  git -C $W/wt/$1 log -1 --format='%H %s' > $W/reports/$1.commit.txt
  uv venv $W/wt/$1/.venv-repro --python 3.11 -q
  eval uv pip install -q --python $W/wt/$1/.venv-repro/bin/python $PINS
  uv pip install -q --python $W/wt/$1/.venv-repro/bin/python -e $W/wt/$1 --no-deps
  uv pip freeze --python $W/wt/$1/.venv-repro/bin/python > $W/reports/$1.freeze.txt
}
cmp () {
  p=$1; shift
  (cd $MAIN && $W/main/bin/python -m glassbox.v7.reproduce compare evidence/$p "$@" --reproducer "Ajay Pravin Mahale (author)" --environment "$CPU" --out $W/reports/$p.json) 2>&1 | tee $W/reports/$p.compare.txt
}

prep v7-exp5-real-interventions e47cf4e
(cd $W/wt/v7-exp5-real-interventions && .venv-repro/bin/python experiments/v7/real_intervention/run.py --out repro/exp5) > $W/reports/v7-exp5-real-interventions.log 2>&1
cmp v7-exp5-real-interventions $W/wt/v7-exp5-real-interventions/repro/exp5/results.json

prep v7-exp6-cross-model 3314c58
(cd $W/wt/v7-exp6-cross-model && .venv-repro/bin/python experiments/v7/cross_model/run.py --out repro/exp6) > $W/reports/v7-exp6-cross-model.log 2>&1
cmp v7-exp6-cross-model $W/wt/v7-exp6-cross-model/repro/exp6/results.json

prep v7-exp3-noise-baseline 3cf24ac
(cd $W/wt/v7-exp3-noise-baseline && .venv-repro/bin/python experiments/v7/noise_baseline/part_a.py --out repro/exp3/part_a; .venv-repro/bin/python experiments/v7/noise_baseline/part_b.py --out repro/exp3/part_b) > $W/reports/v7-exp3-noise-baseline.log 2>&1
cmp v7-exp3-noise-baseline $W/wt/v7-exp3-noise-baseline/repro/exp3/part_a/results.json $W/wt/v7-exp3-noise-baseline/repro/exp3/part_b/results.json

cd $W && zip -qr repro_B.zip reports && ls -la reports && grep -h VERDICT reports/*.compare.txt
```
