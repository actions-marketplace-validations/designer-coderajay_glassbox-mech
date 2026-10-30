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

Replace `RUN_COMMIT` with the commit the protocol names for this attempt (for
attempt 2, the commit that adds Addendum 1).

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
!pip uninstall -y -q torchvision torchaudio
```

Expected: no error after the last two commands. pip prints a long block headed
`ERROR: pip's dependency resolver ...` listing Colab's own packages (opencv, jax,
gradio and so on). That block is a **warning about packages we don't use**, and it is
normal.

Colab's preinstalled `torchvision` and `torchaudio` are built for a newer torch. Left
installed, they break `import transformers` (see the gpu_check protocol, Addendum 1).
Glassbox needs neither, so they are removed.

If an install fails because a pinned version has no build for Colab's Python version
(shown by the first line), stop and send the output. The pins are then changed in a
dated addendum before anything runs.

## 4. Check the GPU from torch, and run the tests

```
!python3 -c "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
!python3 -m pytest -q tests/test_v7_gpu_check.py tests/test_v7_compute.py
!python3 -c "from transformer_lens import HookedTransformer; m = HookedTransformer.from_pretrained('gpt2', device='cuda'); print('gpt2 loaded on', m.cfg.device)"
```

Expected:
- torch `2.10.0`, a CUDA version, `True` and a GPU name;
- all tests passing;
- `gpt2 loaded on cuda`.

The tests use fakes, so the last line is the real check that the model stack works.

## 5. Run the check

```
!python3 experiments/v7/gpu_check/run.py --out experiments/v7/gpu_check/attempt2
```

Expected: it ends with `overall: PASS`, `overall: FAIL` or
`overall: INFRASTRUCTURE_FAILURE`, plus the path of `results.json`. **Any of the three
is a result to keep.** Do not re-run because of a FAIL.

If the session disconnects before this line appears, nothing was produced. Start again
from step 1 in a new session and mention the disconnect when sending the results.

## 6. Download the results

```
!cd experiments/v7/gpu_check && zip -r gpu_check_results.zip attempt2
from google.colab import files
files.download("experiments/v7/gpu_check/gpu_check_results.zip")
```

On your Mac, unzip it into `experiments/v7/gpu_check/` so that
`experiments/v7/gpu_check/attempt2/results.json` and `run.log` exist. (A later
attempt uses the next free name, `attempt3`, and so on, everywhere above.) Do not edit them.
They are committed unchanged, and `RESULTS.md` is written afterwards.
