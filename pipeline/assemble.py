"""Stage 6 - assembly (FFmpeg, deterministic). From the storyboard and the stage outputs:
  1. timeline: shot start times from shot lengths (picture is cut to the voice)
  2. voice track: each shot's narration placed at its start + lead-in, loudness-matched
  3. music: score trimmed to length, faded, ducked under the voice with sidechaincompress
  4. mix, then two-pass loudnorm to -14 LUFS / -1 dBTP
  5. picture: concat shots + end card, burn English subtitles (safe area aware), export 16:9 and 9:16
Also builds the radio cut (narration + music on black) used for the first user test."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .common import OUT, cache_key, cached, duration_of, ffmpeg, ffmpeg_capture, file_hash, load_storyboard, log_call, out_dir, say
from . import narration, shots, subtitles

STAGE = "assemble"


# ---------------------------------------------------------------- audio
def timeline(sb: dict) -> tuple[dict[str, float], float]:
    lengths = shots.shot_lengths(sb)
    starts, t = {}, 0.0
    for s in sb["shots"]:
        starts[s["id"]] = round(t, 3)
        t += lengths[s["id"]]
    return starts, t


def build_voice(sb: dict, starts: dict, total: float, out: Path) -> Path:
    nd = OUT / "narration"
    inputs, filt = [], []
    for i, s in enumerate(sb["shots"]):
        wav = nd / f"{s['id']}.wav"
        if not wav.exists():
            raise SystemExit(f"[assemble] missing {wav}; run: python run.py narration")
        inputs += ["-i", str(wav)]
        ms = int((starts[s["id"]] + s["narration"].get("lead_in_s", 0.4)) * 1000)
        filt.append(f"[{i}]aresample=48000,aformat=channel_layouts=mono,adelay={ms}:all=1[v{i}]")
    n = len(sb["shots"])
    filt.append("".join(f"[v{i}]" for i in range(n)) +
                f"amix=inputs={n}:normalize=0,apad,atrim=0:{total:.3f},loudnorm=I=-16:TP=-2:LRA=7,"
                f"aresample=48000,aformat=channel_layouts=stereo[out]")
    ffmpeg(inputs + ["-filter_complex", ";".join(filt), "-map", "[out]", str(out)])
    return out


def build_mix(sb: dict, voice: Path, total: float, out: Path) -> Path:
    m = sb["music"]
    duck = m.get("duck", {})
    score = OUT / "music" / "score.wav"
    if not score.exists():
        raise SystemExit("[assemble] missing outputs/music/score.wav; run: python run.py music")
    fade_out = max(total - 4, 0)
    sc = (f"sidechaincompress=threshold={duck.get('threshold', 0.02)}:ratio={duck.get('ratio', 6)}:"
          f"attack={duck.get('attack_ms', 300)}:release={duck.get('release_ms', 1500)}")
    filt = (f"[1]aloop=loop=-1:size=2e9,atrim=0:{total:.3f},volume={m.get('music_db', -6)}dB,"
            f"afade=t=in:d=2,afade=t=out:st={fade_out:.3f}:d=4[mus];"
            f"[0]asplit=2[vox][key];"
            f"[mus][key]{sc}[ducked];"
            f"[vox][ducked]amix=inputs=2:normalize=0[mix]")
    tmp = out.with_suffix(".premaster.wav")
    ffmpeg(["-i", str(voice), "-i", str(score), "-filter_complex", filt, "-map", "[mix]", str(tmp)])
    return loudnorm_2pass(tmp, out, sb.get("output", {}).get("target_lufs", -14),
                          sb.get("output", {}).get("true_peak_db", -1))


def loudnorm_2pass(src: Path, dst: Path, lufs: float, tp: float) -> Path:
    err = ffmpeg_capture(["-i", str(src), "-af", f"loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json",
                          "-f", "null", "-"])
    j = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    af = (f"loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:"
          f"measured_LRA={j['input_lra']}:measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    ffmpeg(["-i", str(src), "-af", af, "-ar", "48000", str(dst)])
    (dst.with_suffix(".loudness.json")).write_text(json.dumps({"pass1": j, "target_lufs": lufs, "true_peak": tp}, indent=2))
    return dst


# ---------------------------------------------------------------- picture
def end_card_png(sb: dict, w: int, h: int, out: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (w, h), (24, 17, 12))
    dr = ImageDraw.Draw(img)
    scale = min(w, h) / 720

    def font(sz):
        try:
            return ImageFont.load_default(size=int(sz * scale))
        except TypeError:
            return ImageFont.load_default()

    big, small = font(64), font(24)
    title = sb["end_card"]["text"]
    lines = sb["end_card"].get("credits", [])
    tw = dr.textlength(title, font=big)
    y = h * 0.36
    dr.text(((w - tw) / 2, y), title, fill=(240, 214, 170), font=big)
    y += 100 * scale
    for ln in lines:
        lw = dr.textlength(ln, font=small)
        dr.text(((w - lw) / 2, y), ln, fill=(200, 190, 175), font=small)
        y += 36 * scale
    img.save(out)
    return out


def end_card_clip(sb: dict, w: int, h: int, d: Path) -> Path:
    png = end_card_png(sb, w, h, d / f"endcard_{w}x{h}.png")
    out = d / f"endcard_{w}x{h}.mp4"
    sec = sb["end_card"]["duration_s"]
    ffmpeg(["-loop", "1", "-i", str(png), "-vf", f"fps=24,fade=t=in:d=0.6,format=yuv420p", "-t", str(sec),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(out)])
    return out


def export(sb: dict, tag: str, w: int, h: int, mix: Path, srt: Path, total: float, out: Path) -> Path:
    tmp = out_dir("tmp")
    lst = tmp / f"concat_{tag}.txt"
    clips = [OUT / "shots" / tag / f"{s['id']}.mp4" for s in sb["shots"]]
    for c in clips:
        if not c.exists():
            raise SystemExit(f"[assemble] missing {c}; run: python run.py shots")
    card = end_card_clip(sb, w, h, tmp)
    lst.write_text("".join(f"file '{c.resolve().as_posix()}'\n" for c in clips + [card]))
    # subtitles: libass sizes are relative to a 288-line script; vertical needs a higher margin (safe area)
    vertical = h > w
    style = ("FontName=DejaVu Sans,FontSize=9,MarginV=70,MarginL=20,MarginR=20" if vertical
             else "FontName=DejaVu Sans,FontSize=17,MarginV=22")
    style += ",PrimaryColour=&H00F0F4F8,OutlineColour=&H80000000,BorderStyle=1,Outline=1.4,Shadow=0"
    # run ffmpeg from the srt's folder so the filter path has no drive letter / colon (Windows-safe)
    import subprocess
    card_len = sb["end_card"]["duration_s"]
    vf = f"subtitles={srt.name}:force_style='{style}',format=yuv420p"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "concat", "-safe", "0", "-i", str(lst.resolve()), "-i", str(mix.resolve()),
           "-vf", vf, "-af", f"apad=pad_dur={card_len}",
           "-map", "0:v", "-map", "1:a", "-t", f"{total + card_len:.3f}",
           "-r", "24", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out.resolve())]
    p = subprocess.run(cmd, cwd=srt.parent, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg export failed:\n" + p.stderr[-2000:])
    return out


# ---------------------------------------------------------------- entry points
def _inputs_key(sb: dict, extra) -> str:
    files = sorted((OUT / "shots").glob("*/s??.mp4")) + sorted((OUT / "narration").glob("s??.wav"))
    score = OUT / "music" / "score.wav"
    hashes = [file_hash(f) for f in files] + ([file_hash(score)] if score.exists() else [])
    return cache_key(hashes, sb["music"], sb["end_card"], sb.get("output"),
                     [s["narration"]["en"] for s in sb["shots"]], extra)


def run(sb: dict | None = None, only=None) -> list[str]:
    sb = sb or load_storyboard()
    t0 = time.time()
    d = out_dir("final")
    starts, total = timeline(sb)
    key = _inputs_key(sb, "final")
    stamp = d / "inputs.key"
    o = sb.get("output", {})
    outs = {"16x9": (tuple(o.get("horizontal", [1280, 720])), d / "film_16x9.mp4"),
            "9x16": (tuple(o.get("vertical", [720, 1280])), d / "film_9x16.mp4")}
    if stamp.exists() and stamp.read_text() == key and all(p.exists() for _, p in outs.values()):
        say(STAGE, "nothing changed since last assembly (cached)")
        return []
    voice = build_voice(sb, starts, total, d / "voice.wav")
    mix = build_mix(sb, voice, total, d / "mix.wav")
    vd = narration.durations()
    srt = subtitles.build_srt(sb, starts, vd, d / "subtitles_en.srt")
    for tag, ((w, h), path) in outs.items():
        export(sb, tag, w, h, mix, srt, total, path)
        say(STAGE, f"wrote {path.relative_to(OUT.parent)} ({duration_of(path):.1f}s)")
    (d / "timeline.json").write_text(json.dumps({"starts": starts, "picture_s": total,
                                                 "with_end_card_s": total + sb["end_card"]["duration_s"]}, indent=2))
    stamp.write_text(key)
    log_call(stage=STAGE, provider="local", model="ffmpeg", params={"exports": list(outs)}, seed=None,
             latency_s=time.time() - t0, status="ok", attempts=1, cache_key=key, output=str(d))
    film_len = total + sb["end_card"]["duration_s"]
    if not 60 <= film_len <= 90:
        say(STAGE, f"WARNING: film is {film_len:.1f}s; the brief asks for 60-90s. Adjust shot durations or lines.")
    return ["final"]


def radio_cut(sb: dict | None = None) -> Path:
    """Narration over (placeholder) music on a black screen with subtitles: the cheapest prototype."""
    sb = sb or load_storyboard()
    t0 = time.time()
    d = out_dir("radio_cut")
    starts, total = timeline(sb)
    voice = build_voice(sb, starts, total, d / "voice.wav")
    mix = build_mix(sb, voice, total, d / "radio_cut.wav")
    srt = subtitles.build_srt(sb, starts, narration.durations(), d / "subtitles_en.srt")
    ffmpeg(["-i", str(mix), "-c:a", "libmp3lame", "-q:a", "3", str(d / "radio_cut.mp3")])
    import subprocess
    out = d / "radio_cut.mp4"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
           f"color=c=black:s=1280x720:r=24:d={total:.3f}", "-i", str(mix.resolve()),
           "-vf", "subtitles=subtitles_en.srt:force_style='FontSize=18,MarginV=30'",
           "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
           str(out.resolve())]
    p = subprocess.run(cmd, cwd=d, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-1500:])
    log_call(stage="radio_cut", provider="local", model="ffmpeg", params={}, seed=None,
             latency_s=time.time() - t0, status="ok", attempts=1, output=str(out))
    say("radio_cut", f"wrote outputs/radio_cut/radio_cut.mp4 and .mp3 ({total:.1f}s)")
    return out
