"""Stage 4 - moving shots. For each shot and each aspect ratio, render a 24 fps clip:
  * motion.mode == "wan" and a Wan 2.2 clip exists in outputs/kaggle/clips/<id>.mp4 -> use it
    (cropped to the aspect, held on its last frame if shorter than the shot);
  * otherwise a Ken Burns move over the keyframe (the planned fallback, not an afterthought).
Wan runs on Kaggle (kaggle/wan_shots.py) because it needs a GPU; this stage only consumes clips.
Shot length = max(storyboard duration, narration length + lead-in + tail) so picture is cut to the voice."""
from __future__ import annotations

import json
from pathlib import Path

from .common import (OUT, cache_key, cached, duration_of, ffmpeg, file_hash, link_current, load_storyboard,
                     log_call, out_dir, say)
from . import narration

STAGE = "shots"
TAIL_S = 0.7
KB_ZOOM = 0.12


def shot_lengths(sb: dict) -> dict[str, float]:
    nd = narration.durations()
    out = {}
    for s in sb["shots"]:
        lead = s["narration"].get("lead_in_s", 0.4)
        need = nd.get(s["id"], 0) + lead + TAIL_S
        out[s["id"]] = round(max(s["duration_s"], need), 2)
    return out


def _kenburns_filter(kind: str, w: int, h: int, frames: int, zoom: float = KB_ZOOM) -> str:
    n = max(frames - 1, 1)
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    z_end = 1 + zoom
    if kind == "zoom_in":
        z, x, y = f"1+{zoom}*on/{n}", cx, cy
    elif kind == "zoom_out":
        z, x, y = f"{z_end}-{zoom}*on/{n}", cx, cy
    elif kind == "pan_right":
        z, x, y = f"{z_end}", f"(iw-iw/zoom)*on/{n}", cy
    elif kind == "pan_left":
        z, x, y = f"{z_end}", f"(iw-iw/zoom)*(1-on/{n})", cy
    elif kind == "pan_up":
        z, x, y = f"{z_end}", cx, f"(ih-ih/zoom)*(1-on/{n})"
    else:  # static
        z, x, y = "1", cx, cy
    # upscale first so zoompan's integer rounding does not jitter
    return (f"scale={w*2}:{h*2}:flags=lanczos,"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps=24,"
            f"format=yuv420p")


def _fit_blur(w: int, h: int) -> str:
    """Whole image fitted to the width, centred over a blurred, darkened copy filling the frame:
    nobody at the edges of a group shot is cut off in the vertical version."""
    return (f"split[a][b];[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"boxblur=24:2,eq=brightness=-0.10[bg];[b]scale={w}:{h}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2")


def _frame(w: int, h: int, fit: str) -> str:
    return _fit_blur(w, h) if fit == "blur" and h > w else _crop_to(w, h)


def _crop_to(w: int, h: int) -> str:
    # centre crop the source to the target aspect ratio
    return f"crop='min(iw,ih*{w}/{h})':'min(ih,iw*{h}/{w})'"


def render_kenburns(img: Path, kind: str, w: int, h: int, seconds: float, out: Path, fit: str = "crop") -> None:
    frames = int(round(seconds * 24))
    fitted = fit == "blur" and h > w
    # a gentler move on fitted group shots, so the people at the edges stay in frame
    vf = _frame(w, h, fit) + "," + _kenburns_filter(kind, w, h, frames, KB_ZOOM * (0.35 if fitted else 1))
    ffmpeg(["-loop", "1", "-i", str(img), "-vf", vf, "-frames:v", str(frames), "-r", "24",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-an", str(out)])


def render_clip(clip: Path, w: int, h: int, seconds: float, out: Path, fit: str = "crop") -> None:
    # trim a weak first 0.25 s, crop (or fit) to aspect, hold last frame if the clip is short
    vf = (f"trim=start=0.25,setpts=PTS-STARTPTS,{_frame(w, h, fit)},scale={w}:{h}:flags=lanczos,fps=24,"
          f"tpad=stop_mode=clone:stop_duration={seconds},format=yuv420p")
    ffmpeg(["-i", str(clip), "-vf", vf, "-t", f"{seconds}", "-r", "24", "-c:v", "libx264",
            "-preset", "veryfast", "-crf", "18", "-an", str(out)])


def render_placeholder(w: int, h: int, seconds: float, out: Path) -> None:
    ffmpeg(["-f", "lavfi", "-i", f"color=c=0x2a1d14:s={w}x{h}:r=24:d={seconds}", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-an", str(out)])


def run(sb: dict | None = None, only: set[str] | None = None) -> list[str]:
    import time
    sb = sb or load_storyboard()
    lengths = shot_lengths(sb)
    kf_meta_p = OUT / "keyframes" / "manifest.json"
    kf_meta = json.loads(kf_meta_p.read_text()) if kf_meta_p.exists() else {}
    o = sb.get("output", {})
    aspects = {"16x9": tuple(o.get("horizontal", [1280, 720])), "9x16": tuple(o.get("vertical", [720, 1280]))}
    changed = []
    for s in sb["shots"]:
        sid = s["id"]
        kf = OUT / "keyframes" / kf_meta[sid]["file"] if sid in kf_meta else None
        if kf_meta.get(sid, {}).get("stale"):
            say(STAGE, f"{sid}: WARNING keyframe is stale (last generation failed)")
        clip = OUT / "kaggle" / "clips" / f"{sid}.mp4"
        use_wan = s["motion"]["mode"] == "wan" and clip.exists()
        src_hash = file_hash(clip) if use_wan else (file_hash(kf) if kf and kf.exists() else "none")
        for tag, (w, h) in aspects.items():
            d = out_dir("shots", tag)
            fit = s["motion"].get("vertical_fit", "crop")
            key = cache_key(src_hash, use_wan, s["motion"]["kenburns"], lengths[sid], w, h, KB_ZOOM, fit)
            target = d / f"{sid}-{key}.mp4"
            if (only is None or sid in only) and not cached(target):
                t0 = time.time()
                if use_wan:
                    render_clip(clip, w, h, lengths[sid], target, fit)
                    how = "wan clip"
                elif kf and kf.exists():
                    render_kenburns(kf, s["motion"]["kenburns"], w, h, lengths[sid], target, fit)
                    how = f"kenburns {s['motion']['kenburns']}"
                else:
                    render_placeholder(w, h, lengths[sid], target)
                    how = "placeholder (no keyframe yet)"
                log_call(stage=STAGE, shot=sid, provider="local", model="ffmpeg", params={"how": how, "w": w, "h": h,
                         "seconds": lengths[sid]}, seed=None, latency_s=time.time() - t0, status="ok",
                         attempts=1, cache_key=key, output=str(target))
                say(STAGE, f"{sid} {tag}: {how}, {lengths[sid]}s")
                if sid not in changed:
                    changed.append(sid)
            if cached(target):
                link_current(target, d / f"{sid}.mp4")
    say(STAGE, f"{len(changed)} shot(s) rendered" + (f": {', '.join(changed)}" if changed else " (all cached)")
        + f"; picture length {sum(lengths.values()):.1f}s + end card")
    return changed
