# Running a V7 experiment on a Colab GPU

*Runbook for the V8 phase B GPU sanity check (`experiments/v7/gpu_check/`). Later GPU
experiments reuse steps 1–4.*

Each step is one Colab cell. Paste it, run it, and check the expected output before
going on. If a step does not show what is expected, **stop** and keep the output. A
setup failure is an infrastructure failure under the protocol (re-run in a new
session); it is never patched mid-run.

Nothing here needs a token or a login beyond your Google account. The repository is
public and GPT-2 small downloads without an HF token.

## 1. GPU runtime

In the Colab menu: **Runtime → Change runtime type → a GPU (e.g. T4) → Save**. Then:

```
!nvidia-smi
```

Expected: a table naming a GPU. If it says no device was found, the runtime has no GPU;
change it and start again.

## 2. Get the code at the exact commit

Replace `RUN_COMMIT` with the commit that added `experiments/v7/gpu_check/run.py`
(the owner records it when committing).

```
!git clone https://github.com/designer-coderajay/glassbox-mech.git
%cd glassbox-mech
!git checkout RUN_COMMIT
!git log -1 --oneline
```

Expected: the last line shows that commit.

## 3. Install the pinned stack

These are the versions the CI uses (`.github/workflows/ci.yml`). Glassbox itself is
installed from the checkout with `--no-deps`, so pip cannot swap the pins.

```
!python3 --version
!pip install -q "numpy==1.26.4" "scipy==1.17.1" "einops==0.8.2" "torch==2.10.0" "transformer-lens==2.17.0" "transformers==4.57.6" "pyarrow==23.0.0" "datasets==4.5.0" "pandas==3.0.0" pytest
!pip install -q -e . --no-deps
```

Expected: no line starting with `ERROR:`. Warnings about Colab's own preinstalled
packages are normal; every experiment step runs in a fresh `python3` process, so
those packages are not imported.

If an install fails because a pinned version has no build for Colab's Python version
(shown by the first line), stop and send the output. The pins are then changed in a
dated addendum before anything runs.

## 4. Check the GPU from torch, and run the tests

```
!python3 -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
!python3 -m pytest -q tests/test_v7_gpu_check.py tests/test_v7_compute.py
```

Expected: torch `2.10.0`, a CUDA version, `True`, a GPU name; then all tests passing.

## 5. Run the check

```
!python3 experiments/v7/gpu_check/run.py --out experiments/v7/gpu_check/results
```

Expected: it ends with `overall: PASS`, `overall: FAIL` or
`overall: INFRASTRUCTURE_FAILURE`, plus the path of `results.json`. **Any of the three
is a result to keep.** Do not re-run because of a FAIL.

If the session disconnects before this line appears, nothing was produced. Start again
from step 1 in a new session and mention the disconnect when sending the results.

## 6. Download the results

```
!cd experiments/v7/gpu_check && zip -r gpu_check_results.zip results
from google.colab import files
files.download("experiments/v7/gpu_check/gpu_check_results.zip")
```

On your Mac, unzip it into `experiments/v7/gpu_check/` so that
`experiments/v7/gpu_check/results/results.json` and `run.log` exist. Do not edit them.
They are committed unchanged, and `RESULTS.md` is written afterwards.
