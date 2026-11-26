"""Stage 2 - narration: one WAV per shot from Gemini TTS. Cache key = spoken text + voice +
style + model, so editing one line regenerates only that shot's audio."""
from __future__ import annotations

import json

from .common import audio_stats, cache_key, cached, duration_of, is_silent, link_current, load_storyboard, out_dir, say
from .providers import gemini_tts

STAGE = "narration"


def run(sb: dict | None = None, only: set[str] | None = None) -> list[str]:
    sb = sb or load_storyboard()
    d = out_dir("narration")
    model = sb["models"]["tts"]
    voice = sb.get("voice", {}).get("name", "Kore")
    style = sb.get("voice", {}).get("style")
    manifest_path = d / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    changed = []
    for s in sb["shots"]:
        text = s["narration"].get("spoken") or s["narration"]["en"]
        key = cache_key(text, voice, style, model)
        target = d / f"{s['id']}-{key}.wav"
        if cached(target) and is_silent(target):
            dur, mx = audio_stats(target)
            say(STAGE, f"{s['id']}: cached audio is silent ({dur:.1f}s, peak {mx} dB); regenerating")
            target.unlink()
        if (only is None or s["id"] in only) and not cached(target):
            say(STAGE, f"{s['id']}: generating ({len(text)} chars)")
            gemini_tts(text, model=model, voice=voice, style=style, out_wav=target,
                       shot=s["id"], cache_key=key)
            changed.append(s["id"])
        if cached(target):
            link_current(target, d / f"{s['id']}.wav")
            manifest[s["id"]] = {"file": target.name, "key": key, "duration_s": round(duration_of(target), 3)}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    total = sum(v["duration_s"] for k, v in manifest.items() if any(s["id"] == k for s in sb["shots"]))
    say(STAGE, f"{len(changed)} regenerated" + (f": {', '.join(changed)}" if changed else " (all cached)")
        + f"; total narration {total:.1f}s")
    return changed


def durations() -> dict[str, float]:
    p = out_dir("narration") / "manifest.json"
    return {k: v["duration_s"] for k, v in json.loads(p.read_text()).items()} if p.exists() else {}
