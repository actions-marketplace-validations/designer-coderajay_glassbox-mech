# Running Experiment 7b on a free Kaggle notebook (Addendum 1)

*Use a **CPU** session; the code runs on CPU (`device="cpu"`), as on the Mac.
Third-party sources (not Kaggle's own docs) report about 29–30 GB RAM and 4 CPU cores
for free notebooks. Check what your session shows in the first cell. The notebook
needs **Internet ON** (Settings, Internet), which may require phone verification of
your Kaggle account.*

## Cells (run in order)

```python
# 1. Machine facts, recorded in RESULTS.md
!nproc; free -g; python -V
```

```python
# 2. Code at the exact committed revision (replace COMMIT with the hash you pushed)
!git clone https://github.com/designer-coderajay/glassbox-mech.git
%cd glassbox-mech
!git checkout COMMIT
!git log -1 --format='%H %s'
```

```python
# 3. The same pinned stack as CI and the Mac
!pip install -q "numpy==1.26.4" "scipy==1.17.1" "einops==0.8.2" "torch==2.10.0" \
    "transformer-lens==2.17.0" "transformers==4.57.6" "pyarrow==23.0.0" \
    "datasets==4.5.0" "pandas==3.0.0" pytest
!pip install -q -e . --no-deps
!pip freeze | grep -iE "^(torch|transformer-lens|transformers|numpy|pyarrow|datasets)=="
```

```python
# 4. Mechanics tests (fake scorers, fast)
!python -m pytest -q tests/test_v7_agent_b.py tests/test_v7_agent.py
```

```python
# 5. The run (progress lines appear as it goes; output also saved to run_log.txt)
!python experiments/v7/agent_b/run.py --out experiments/v7/agent_b/results 2>&1 | tee run_log.txt
```

## Afterwards

1. Download `experiments/v7/agent_b/results/results.json` and `run_log.txt` from the
   notebook's file browser (output panel).
2. On the Mac, put them at `experiments/v7/agent_b/results/results.json` and
   `experiments/v7/agent_b/results/kaggle_run_log.txt`. Do not edit either file.
3. Commit them unchanged, then paste the run output into the chat for the write-up.

If cell 3 fails (for example, if Kaggle's Python version has no wheel for a pinned
package), stop and report the error. Do not change versions without recording them.
