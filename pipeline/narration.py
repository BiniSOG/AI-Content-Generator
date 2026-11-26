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
    lang = sb["language"]["narration"]
    lang_name = sb["language"].get("narration_name", lang)
    problems = [p for s in sb["shots"] for p in spoken_problems(s, lang)]
    if problems:
        raise SystemExit(f"[narration] not every line is in {lang_name}, so the voice would not be fully "
                         f"{lang_name}:\n  " + "\n  ".join(problems) +
                         "\nFix: fill narration.spoken (python run.py script, or tools/apply_am_translations.py).")
    manifest_path = d / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    changed = []
    for s in sb["shots"]:
        text = s["narration"]["en"] if lang == "en" else s["narration"]["spoken"]
        key = cache_key(text, voice, style, model, lang_name, "tts-v2")
        target = d / f"{s['id']}-{key}.wav"
        if cached(target) and is_silent(target):
            dur, mx = audio_stats(target)
            say(STAGE, f"{s['id']}: cached audio is silent ({dur:.1f}s, peak {mx} dB); regenerating")
            target.unlink()
        if (only is None or s["id"] in only) and not cached(target):
            say(STAGE, f"{s['id']}: generating ({len(text)} chars)")
            gemini_tts(text, model=model, voice=voice, style=style, out_wav=target,
                       shot=s["id"], cache_key=key, lang_name=lang_name)
            changed.append(s["id"])
        if cached(target):
            link_current(target, d / f"{s['id']}.wav")
            manifest[s["id"]] = {"file": target.name, "key": key, "duration_s": round(duration_of(target), 3)}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    total = sum(v["duration_s"] for k, v in manifest.items() if any(s["id"] == k for s in sb["shots"]))
    say(STAGE, f"{len(changed)} regenerated" + (f": {', '.join(changed)}" if changed else " (all cached)")
        + f"; total narration {total:.1f}s")
    return changed


_SCRIPT_RANGES = {"am": ("\u1200", "\u139F"), "ti": ("\u1200", "\u139F")}  # Ethiopic (Ge'ez) script


def spoken_problems(shot: dict, lang: str) -> list[str]:
    """Why a shot's spoken line is not fully in the narration language (empty list = fine)."""
    if lang == "en":
        return []
    sp = (shot["narration"].get("spoken") or "").strip()
    if not sp:
        return [f"{shot['id']}: no {lang} line (narration.spoken is empty); it would be read in English"]
    rng = _SCRIPT_RANGES.get(lang)
    if rng:
        letters = [ch for ch in sp if ch.isalpha()]
        native = sum(rng[0] <= ch <= rng[1] for ch in letters)
        latin = [w for w in sp.split() if any("a" <= ch.lower() <= "z" for ch in w)]
        if letters and native / len(letters) < 0.95 or latin:
            return [f"{shot['id']}: line contains non-{lang} words: {' '.join(latin) or sp[:40]}"]
    return []


def durations() -> dict[str, float]:
    p = out_dir("narration") / "manifest.json"
    return {k: v["duration_s"] for k, v in json.loads(p.read_text()).items()} if p.exists() else {}
