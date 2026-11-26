"""Offline end-to-end test: replaces the hosted model calls with fakes, runs every stage,
then checks caching (a second run regenerates nothing; changing one line regenerates one shot).
    python tests/test_offline.py"""
import json, os, shutil, subprocess, sys, tempfile, wave
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
tmp = Path(tempfile.mkdtemp(prefix="film-test-"))
for p in ("pipeline", "schema", "storyboard.json", "ETHICS.md"):
    src = REPO / p
    if src.is_dir():
        shutil.copytree(src, tmp / p)
    elif src.exists():
        shutil.copy(src, tmp / p)
sys.path.insert(0, str(tmp))
os.chdir(tmp)

from pipeline import common, providers, narration, keyframes, script, shots, music, assemble  # noqa: E402

calls = []


def fake_tts(text, *, model, voice, style, out_wav, stage="narration", shot=None, cache_key=None, **kw):
    calls.append(("tts", shot))
    secs = 2.0 + len(text) / 25
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=f=220:d={secs}",
                    "-ar", "24000", "-ac", "1", str(out_wav)], check=True)
    common.log_call(stage=stage, shot=shot, provider="fake", model=model, params={}, seed=None,
                    latency_s=0.01, status="ok", attempts=1, cache_key=cache_key)
    return out_wav


def fake_img(prompt, *, sb, seed, out_png, **kw):
    calls.append(("img", kw.get("shot")))
    from PIL import Image
    Image.new("RGB", (1024, 1024), ((seed * 37) % 255, 120, 80)).save(out_png)
    common.log_call(stage="keyframes", shot=kw.get("shot"), provider="fake", model=sb["models"]["image"],
                    params={}, seed=seed, latency_s=0.01, status="ok", attempts=1)
    return out_png, sb["models"]["image"]


def fake_text(prompt, **kw):
    calls.append(("text", kw.get("shot")))
    # fake Amharic (Ethiopic script) that still changes with the English line
    return "ትርጉም " + "".join("ሀለሐመሠረሰቀበተ"[ord(c) % 10] for c in prompt.rsplit("\n", 1)[-1] if c.isalpha())[:40]


narration.gemini_tts = fake_tts
keyframes.cf_image_with_fallback = fake_img
script.gemini_text = fake_text


def full_run():
    sb = common.load_storyboard()
    script.run(sb); narration.run(sb); keyframes.run(sb); shots.run(sb); music.run(sb); assemble.run(sb)


full_run()
for f in ("film_16x9.mp4", "film_9x16.mp4", "subtitles.srt"):
    assert (tmp / "outputs/final" / f).exists(), f
dur = common.duration_of(tmp / "outputs/final/film_16x9.mp4")
print(f"film length {dur:.1f}s")
n_first = len(calls)

calls.clear(); full_run()
assert calls == [], f"second run should be fully cached, got {calls}"

sb = json.loads((tmp / "storyboard.json").read_text())
sb["shots"][3]["narration"]["en"] = sb["shots"][3]["narration"]["en"] + " Off they went!"
sb["shots"][3]["narration"].pop("locked", None)  # a locked line is never re-translated
(tmp / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False, indent=2))
calls.clear(); full_run()
assert sorted(calls) == [("text", "s04"), ("tts", "s04")], calls
lines = (tmp / "runs.jsonl").read_text().splitlines()
assert all({"model", "params", "seed", "latency_s"} <= json.loads(l).keys() for l in lines)
print(f"OK: first run {n_first} model calls; cached re-run 0; one-line edit -> {calls}")
print("test dir:", tmp)
