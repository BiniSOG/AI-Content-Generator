# Running the GPU stages on Kaggle

Music (ACE-Step 1.5) and moving shots (Wan 2.2) need a GPU, so they run in a Kaggle notebook. They read the same `storyboard.json` and write to the same log format. The local pipeline picks up what they produce:

- `outputs/kaggle/music/cand_N.wav`: score candidates, used by `python run.py music`
- `outputs/kaggle/clips/sNN.mp4`: Wan clips, used by `python run.py shots` (shots without a clip fall back to Ken Burns)
- `outputs/kaggle/runs_kaggle.jsonl`: log lines, merged into `runs.jsonl` with each line added only once

## 1. Pack the inputs (on your laptop)

Generate the keyframes first, then:

```bash
python run.py kaggle-pack
```

This writes `outputs/kaggle_input.zip`, which holds the storyboard, the Kaggle scripts, and the keyframes of the shots set to `"mode": "wan"`.

## 2. Create the notebook

1. On kaggle.com, upload `outputs/kaggle_input.zip` under **Datasets → New Dataset** and name it `film-input`.
2. Go to **Code → New Notebook**. In the right panel:
   - **Accelerator:** GPU T4 x2
   - **Internet:** On (this needs a phone-verified account)
   - **Add Input:** your `film-input` dataset

## 3. Cells to paste (one cell each)

**Cell 1: copy the scripts**
```python
import glob, shutil, os
src = os.path.dirname(glob.glob("/kaggle/input/**/storyboard.json", recursive=True)[0])
shutil.copytree(f"{src}/kaggle", "/kaggle/working/kaggle", dirs_exist_ok=True)
!nvidia-smi --query-gpu=name,memory.total --format=csv
```

**Cell 2: music with ACE-Step 1.5 (about 10–20 minutes including setup)**
```python
!curl -LsSf https://astral.sh/uv/install.sh | sh
!git clone -q https://github.com/ACE-Step/ACE-Step-1.5.git /kaggle/working/ACE-Step-1.5
%cd /kaggle/working/ACE-Step-1.5
!~/.local/bin/uv sync -q
!~/.local/bin/uv run python /kaggle/working/kaggle/ace_step_score.py
```

**Cell 3: Wan 2.2 hero shots (the model download is about 20 GB; each clip takes several minutes on a T4)**
```python
%cd /kaggle/working
!pip install -q -U diffusers transformers accelerate ftfy imageio-ffmpeg
!python /kaggle/working/kaggle/wan_shots.py
```
If it runs out of memory, restart and try `!WAN_SIZE=480 WAN_FRAMES=49 python /kaggle/working/kaggle/wan_shots.py`, then write the failure in FAILURES.md.

**Cell 4: zip the outputs**
```python
!cd /kaggle/working && zip -qr kaggle_outputs.zip outputs/kaggle && ls -la kaggle_outputs.zip
```

Download `kaggle_outputs.zip` from the Output panel on the right, then unzip it **into the repo root**. That gives you `outputs/kaggle/...`.

## 4. Back on your laptop

```bash
python run.py film
```

This merges the Kaggle log lines, uses the clips and the chosen score, and re-renders only the shots whose source changed.

Note the GPU minutes: Kaggle shows the quota you've used under *Settings → Accelerator*. Write that number in COSTS.md next to the logged `gpu_s`.
