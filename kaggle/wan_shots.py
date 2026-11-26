"""Animate the keyframes of shots with motion.mode == "wan" using Wan 2.2 TI2V-5B (diffusers).
Draft settings for a T4 (16 GB, no bf16): 640x640, 81 frames (~3.4 s at 24 fps), fp16, CPU offload.
Saves each clip as soon as it finishes, so a session timeout loses only the clip in progress.
    python /kaggle/working/kaggle/wan_shots.py            # all wan shots
    SHOTS=s03 python /kaggle/working/kaggle/wan_shots.py  # one shot"""
import glob, json, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _log import log

import torch
from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
from diffusers.utils import export_to_video, load_image

ROOT_IN = Path(glob.glob("/kaggle/input/**/storyboard.json", recursive=True)[0]).parent
SB = json.load(open(ROOT_IN / "storyboard.json"))
OUTD = Path("/kaggle/working/outputs/kaggle/clips"); OUTD.mkdir(parents=True, exist_ok=True)
MODEL = SB["models"].get("video", "Wan-AI/Wan2.2-TI2V-5B-Diffusers")
W = H = int(os.environ.get("WAN_SIZE", 640))
FRAMES = int(os.environ.get("WAN_FRAMES", 81))
STEPS = int(os.environ.get("WAN_STEPS", 30))
only = set(os.environ["SHOTS"].split(",")) if os.environ.get("SHOTS") else None

vae = AutoencoderKLWan.from_pretrained(MODEL, subfolder="vae", torch_dtype=torch.float32)
pipe = WanImageToVideoPipeline.from_pretrained(MODEL, vae=vae, torch_dtype=torch.float16)
pipe.enable_model_cpu_offload()
try:
    pipe.vae.enable_tiling()
except Exception:
    pass

for s in SB["shots"]:
    if s["motion"]["mode"] != "wan" or (only and s["id"] not in only):
        continue
    out = OUTD / f"{s['id']}.mp4"
    if out.exists():
        print("skip (exists)", out); continue
    kf = ROOT_IN / "keyframes" / f"{s['id']}.png"
    img = load_image(str(kf)).resize((W, H))
    prompt = s["motion"].get("video_prompt") or "gentle slow motion, static camera"
    neg = ("fast motion, morphing, warping, flicker, distorted face, extra fingers, text, watermark, "
           + SB["style"].get("negative", ""))
    t0 = time.time(); status, err = "ok", None
    try:
        g = torch.Generator("cpu").manual_seed(s["seed"])
        frames = pipe(image=img, prompt=prompt, negative_prompt=neg, height=H, width=W, num_frames=FRAMES,
                      guidance_scale=5.0, num_inference_steps=STEPS, generator=g).frames[0]
        export_to_video(frames, str(out), fps=24)
    except Exception as e:
        status, err = "error", f"{type(e).__name__}: {str(e)[:400]}"
        torch.cuda.empty_cache()
    dt = time.time() - t0
    log(stage="shots", shot=s["id"], model=MODEL, params={"w": W, "h": H, "frames": FRAMES, "steps": STEPS,
        "guidance": 5.0, "dtype": "fp16", "offload": "model_cpu", "prompt": prompt},
        seed=s["seed"], latency_s=round(dt, 2), gpu_s=round(dt, 2), status=status, error=err,
        output=str(out) if status == "ok" else None)
print("clips:", sorted(p.name for p in OUTD.glob("*.mp4")))
