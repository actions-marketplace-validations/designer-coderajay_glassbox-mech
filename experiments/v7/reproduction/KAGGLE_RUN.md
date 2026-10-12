# Running V7 Experiment 9 (reproduction in an independent environment) on Kaggle

Attempt 2. Use this after `PROTOCOL.md` Addendum 1 is committed. Attempt 1 ran out of
disk; see the addendum.

There are two notebooks. Each is a Kaggle "Save Version → Save & Run All (Commit)" batch
run on **CPU** with **Internet on**, and each is pasted as **one** `%%bash` code cell
(the first line must be `%%bash`).

- **Notebook A** covers the fast packages: Experiments 4, 3b, 2, 8 and 1.
- **Notebook B** covers the model-heavier ones: Experiments 5, 6 and 3.

What each cell does (Addendum 1):
1. **One shared environment.** It creates one Python 3.11 venv in `/tmp` with
   torch 2.10.0 (CPU build) and the other recipe pins.
2. **Per package:**
   - check out the **recipe commit** as a git worktree in `/tmp`, link its `.venv-repro`
     to the shared venv, and point the editable install at it;
   - run the recipe's **run commands exactly**;
   - point the editable install back at `main` and compare;
   - delete the worktree.
3. **Output.** Reports, logs, the fresh `results.json` files, the commit, the environment
   freeze, `lscpu` and disk usage are kept in `/kaggle/working/reports`, zipped as
   `repro_A.zip` / `repro_B.zip`.

Download the zip from the saved version's **Output** tab.

## Notebook A (Experiments 4, 3b, 2, 8, 1)

```
%%bash
set -uo pipefail
W=/kaggle/working
T=/tmp/repro
MAIN=$T/glassbox-mech
PY=$T/py/bin/python
REST='"numpy==1.26.4" "scipy==1.17.1" "einops==0.8.2" "transformer-lens==2.17.0" "transformers==4.57.6" "pyarrow==23.0.0" "datasets==4.5.0" "pandas==3.0.0" pytest'
rm -rf $T $W/reports && mkdir -p $T $W/reports
git clone -q https://github.com/designer-coderajay/glassbox-mech.git $MAIN
git -C $MAIN log -1 --format='%H %s' | tee $W/reports/main.commit.txt
pip install -q uv
uv venv $T/py --python 3.11 -q
uv pip install -q --python $PY --index-url https://download.pytorch.org/whl/cpu "torch==2.10.0"
eval uv pip install -q --python $PY $REST
uv pip install -q --python $PY -e $MAIN --no-deps
uv pip freeze --python $PY > $W/reports/env_freeze.txt
lscpu | head -20 | tee $W/reports/lscpu.txt
df -h /tmp $W | tee $W/reports/disk_start.txt
CPU="$(lscpu | grep 'Model name' | sed 's/Model name:[[:space:]]*//') / Linux x86-64 / Kaggle CPU"
prep () {
  git -C $MAIN worktree add -q $T/wt/$1 $2
  git -C $T/wt/$1 log -1 --format='%H %s' > $W/reports/$1.commit.txt
  ln -s $T/py $T/wt/$1/.venv-repro
  uv pip install -q --python $PY -e $T/wt/$1 --no-deps
}
cmp () {
  p=$1; shift
  uv pip install -q --python $PY -e $MAIN --no-deps
  mkdir -p $W/reports/$p.fresh
  for f in "$@"; do cp "$f" $W/reports/$p.fresh/$(echo "$f" | sed "s|$T/wt/$p/||; s|/|__|g") 2>/dev/null; done
  (cd $MAIN && $PY -m glassbox.v7.reproduce compare evidence/$p "$@" --reproducer "Ajay Pravin Mahale (author)" --environment "$CPU" --out $W/reports/$p.json) 2>&1 | tee $W/reports/$p.compare.txt
  git -C $MAIN worktree remove --force $T/wt/$p
  df -h /tmp $W | tail -2
}

prep v7-exp4-interventions ad75d43
(cd $T/wt/v7-exp4-interventions && .venv-repro/bin/python experiments/v7/intervention/run.py --out repro/exp4) > $W/reports/v7-exp4-interventions.log 2>&1
cmp v7-exp4-interventions $T/wt/v7-exp4-interventions/repro/exp4/results.json

prep v7-exp3b-noise-baseline-merge 55e8bcf
(cd $T/wt/v7-exp3b-noise-baseline-merge && .venv-repro/bin/python experiments/v7/noise_baseline_3b/run.py --out repro/exp3b) > $W/reports/v7-exp3b-noise-baseline-merge.log 2>&1
cmp v7-exp3b-noise-baseline-merge $T/wt/v7-exp3b-noise-baseline-merge/repro/exp3b/results.json

for v in 0.14.17 0.14.19; do uv venv ~/.glassbox-venvs/li-$v --python 3.11 -q; uv pip install -q --python ~/.glassbox-venvs/li-$v/bin/python "llama-index-core==$v"; done
prep v7-exp2-llama-dedup 72cb710
(cd $T/wt/v7-exp2-llama-dedup && for v in 0.14.17 0.14.19; do for p in sync async; do for r in r1 r2; do ~/.glassbox-venvs/li-$v/bin/python experiments/v7/llama_dedup/subject.py --path $p --run $r --out repro/exp2; done; done; done && .venv-repro/bin/python experiments/v7/llama_dedup/evaluate.py --results repro/exp2) > $W/reports/v7-exp2-llama-dedup.log 2>&1
cmp v7-exp2-llama-dedup $T/wt/v7-exp2-llama-dedup/repro/exp2/results.json

uv venv ~/.glassbox-venvs/exp8-stack-b --python 3.11 -q
uv pip install -q --python ~/.glassbox-venvs/exp8-stack-b/bin/python "llama-index-core==0.14.19" "openinference-instrumentation-llama-index==4.6.0" "opentelemetry-sdk==1.45.1" "opentelemetry-exporter-otlp-proto-common==1.45.1" "opentelemetry-proto==1.45.1"
prep v7-exp8-cross-stack 226a4eb
(cd $T/wt/v7-exp8-cross-stack && ~/.glassbox-venvs/exp8-stack-b/bin/python experiments/v7/cross_stack/subject.py record --out repro/exp8 && ~/.glassbox-venvs/exp8-stack-b/bin/python experiments/v7/cross_stack/subject.py schema-check --out repro/exp8 && .venv-repro/bin/python experiments/v7/cross_stack/evaluate.py --results repro/exp8) > $W/reports/v7-exp8-cross-stack.log 2>&1
cmp v7-exp8-cross-stack $T/wt/v7-exp8-cross-stack/repro/exp8/results.json

prep v7-exp1-rag-fault aedfebf
(cd $T/wt/v7-exp1-rag-fault && .venv-repro/bin/python experiments/v7/rag_fault/run.py --out repro/exp1) > $W/reports/v7-exp1-rag-fault.log 2>&1
cmp v7-exp1-rag-fault $T/wt/v7-exp1-rag-fault/repro/exp1/results.json

df -h /tmp $W | tee $W/reports/disk_end.txt
cd $W && zip -qr repro_A.zip reports && ls -la reports && grep -h VERDICT reports/*.compare.txt
```

## Notebook B (Experiments 5, 6, 3)

```
%%bash
set -uo pipefail
W=/kaggle/working
T=/tmp/repro
MAIN=$T/glassbox-mech
PY=$T/py/bin/python
REST='"numpy==1.26.4" "scipy==1.17.1" "einops==0.8.2" "transformer-lens==2.17.0" "transformers==4.57.6" "pyarrow==23.0.0" "datasets==4.5.0" "pandas==3.0.0" pytest'
rm -rf $T $W/reports && mkdir -p $T $W/reports
git clone -q https://github.com/designer-coderajay/glassbox-mech.git $MAIN
git -C $MAIN log -1 --format='%H %s' | tee $W/reports/main.commit.txt
pip install -q uv
uv venv $T/py --python 3.11 -q
uv pip install -q --python $PY --index-url https://download.pytorch.org/whl/cpu "torch==2.10.0"
eval uv pip install -q --python $PY $REST
uv pip install -q --python $PY -e $MAIN --no-deps
uv pip freeze --python $PY > $W/reports/env_freeze.txt
lscpu | head -20 | tee $W/reports/lscpu.txt
df -h /tmp $W | tee $W/reports/disk_start.txt
CPU="$(lscpu | grep 'Model name' | sed 's/Model name:[[:space:]]*//') / Linux x86-64 / Kaggle CPU"
prep () {
  git -C $MAIN worktree add -q $T/wt/$1 $2
  git -C $T/wt/$1 log -1 --format='%H %s' > $W/reports/$1.commit.txt
  ln -s $T/py $T/wt/$1/.venv-repro
  uv pip install -q --python $PY -e $T/wt/$1 --no-deps
}
cmp () {
  p=$1; shift
  uv pip install -q --python $PY -e $MAIN --no-deps
  mkdir -p $W/reports/$p.fresh
  for f in "$@"; do cp "$f" $W/reports/$p.fresh/$(echo "$f" | sed "s|$T/wt/$p/||; s|/|__|g") 2>/dev/null; done
  (cd $MAIN && $PY -m glassbox.v7.reproduce compare evidence/$p "$@" --reproducer "Ajay Pravin Mahale (author)" --environment "$CPU" --out $W/reports/$p.json) 2>&1 | tee $W/reports/$p.compare.txt
  git -C $MAIN worktree remove --force $T/wt/$p
  df -h /tmp $W | tail -2
}

prep v7-exp5-real-interventions e47cf4e
(cd $T/wt/v7-exp5-real-interventions && .venv-repro/bin/python experiments/v7/real_intervention/run.py --out repro/exp5) > $W/reports/v7-exp5-real-interventions.log 2>&1
cmp v7-exp5-real-interventions $T/wt/v7-exp5-real-interventions/repro/exp5/results.json

prep v7-exp6-cross-model 3314c58
(cd $T/wt/v7-exp6-cross-model && .venv-repro/bin/python experiments/v7/cross_model/run.py --out repro/exp6) > $W/reports/v7-exp6-cross-model.log 2>&1
cmp v7-exp6-cross-model $T/wt/v7-exp6-cross-model/repro/exp6/results.json

prep v7-exp3-noise-baseline 3cf24ac
(cd $T/wt/v7-exp3-noise-baseline && .venv-repro/bin/python experiments/v7/noise_baseline/part_a.py --out repro/exp3/part_a; .venv-repro/bin/python experiments/v7/noise_baseline/part_b.py --out repro/exp3/part_b) > $W/reports/v7-exp3-noise-baseline.log 2>&1
cmp v7-exp3-noise-baseline $T/wt/v7-exp3-noise-baseline/repro/exp3/part_a/results.json $T/wt/v7-exp3-noise-baseline/repro/exp3/part_b/results.json

df -h /tmp $W | tee $W/reports/disk_end.txt
cd $W && zip -qr repro_B.zip reports && ls -la reports && grep -h VERDICT reports/*.compare.txt
```
