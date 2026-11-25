"""Generate N score candidates with ACE-Step 1.5 from storyboard.json music fields.
Run inside the ACE-Step-1.5 checkout on Kaggle (see kaggle/README.md):
    uv run python /kaggle/working/kaggle/ace_step_score.py
Writes /kaggle/working/outputs/kaggle/music/cand_N.wav and log lines."""
import glob, json, os, shutil, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _log import log

SB = json.load(open(glob.glob("/kaggle/input/**/storyboard.json", recursive=True)[0]))
OUTD = Path("/kaggle/working/outputs/kaggle/music"); OUTD.mkdir(parents=True, exist_ok=True)
m = SB["music"]
seeds = m.get("seeds") or [101, 202, 303]
seeds = seeds[: m["candidates"]]

from acestep.handler import AceStepHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

dit = AceStepHandler()
dit.initialize_service(project_root=os.getcwd(), config_path="acestep-v15-turbo", device="cuda")
llm = None
try:  # the LM planner is optional; T4s may not run the vllm backend, so fall back to DiT-only
    from acestep.llm_inference import LLMHandler
    llm = LLMHandler()
    llm.initialize(checkpoint_dir=os.path.join(os.getcwd(), "checkpoints"), lm_model_path="acestep-5Hz-lm-0.6B",
                   backend=os.environ.get("ACE_LM_BACKEND", "pt"), device="cuda")
except Exception as e:
    print("LM planner unavailable, continuing DiT-only:", e)
    llm = None

for i, seed in enumerate(seeds, 1):
    params = GenerationParams(task_type="text2music", caption=m["caption"], lyrics="[Instrumental]",
                              instrumental=True, bpm=m["bpm"], keyscale=m["key"], duration=m["duration_s"],
                              seed=seed, inference_steps=8, shift=3.0)
    cfg = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[seed], audio_format="wav")
    t0 = time.time()
    status, err, out = "ok", None, None
    try:
        res = generate_music(dit, llm, params, cfg, save_dir=str(OUTD / f"raw_{i}"))
        if not res.success:
            raise RuntimeError(res.error)
        out = OUTD / f"cand_{i}.wav"
        shutil.copyfile(res.audios[0]["path"], out)
    except Exception as e:
        status, err = "error", str(e)[:500]
    dt = time.time() - t0
    log(stage="music", shot=None, model="ACE-Step-1.5 (acestep-v15-turbo)",
        params={"caption": m["caption"], "bpm": m["bpm"], "key": m["key"], "duration": m["duration_s"],
                "steps": 8, "shift": 3.0, "lm": llm is not None},
        seed=seed, latency_s=round(dt, 2), gpu_s=round(dt, 2), status=status, error=err,
        output=str(out) if out else None)
print("done:", sorted(p.name for p in OUTD.glob("cand_*")))
