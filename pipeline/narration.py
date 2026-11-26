"""Stage 2 - narration: one WAV per shot from Gemini TTS. Cache key = spoken text + voice +
style + model, so editing one line regenerates only that shot's audio."""
from __future__ import annotations

import json

from .common import (audio_stats, cache_key, cached, duration_of, ffmpeg, is_silent, link_current, load_storyboard,
                     out_dir, say)
from .providers import QuotaExhausted, gemini_inspect, gemini_tts
from .common import CallFailed

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
    check_on = sb.get("voice", {}).get("check_language", True)
    tempo = float(sb.get("voice", {}).get("tempo", 1.0))
    max_pause = float(sb.get("voice", {}).get("max_pause_s", 0.45))
    missing = []
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
            try:
                gemini_tts(text, model=model, voice=voice, style=style, out_wav=target,
                           shot=s["id"], cache_key=key, lang_name=lang_name,
                           check=None if lang == "en" or not check_on else _language_check(sb, s["id"], text, lang_name))
                changed.append(s["id"])
            except QuotaExhausted as e:
                missing.append(s["id"])
                say(STAGE, f"{s['id']}: not generated: {str(e)[:160]}")
                continue
        if cached(target):
            final = tighten(target, tempo, max_pause)
            link_current(final, d / f"{s['id']}.wav")
            manifest[s["id"]] = {"file": final.name, "raw": target.name, "key": key,
                                 "duration_s": round(duration_of(final), 3),
                                 "raw_duration_s": round(duration_of(target), 3)}
    manifest_path.write_text(json.dumps(manifest, indent=2))
    if missing:
        raise SystemExit(f"[narration] {len(changed)} line(s) made this run; still missing: {', '.join(missing)}.\n"
                         f"The daily Gemini TTS free quota is used up. Everything made so far is cached, so the "
                         f"same command continues where it stopped once the quota resets (midnight Pacific "
                         f"time), or right away if you enable billing for the API key in Google AI Studio.")
    total = sum(v["duration_s"] for k, v in manifest.items() if any(s["id"] == k for s in sb["shots"]))
    say(STAGE, f"{len(changed)} regenerated" + (f": {', '.join(changed)}" if changed else " (all cached)")
        + f"; total narration {total:.1f}s (tempo {tempo:g}, pauses up to {max_pause:g}s)")
    say(STAGE, "per line: " + ", ".join(f"{k} {v['duration_s']:.1f}s" for k, v in manifest.items()
                                        if any(s['id'] == k for s in sb['shots'])))
    if total > 80:
        say(STAGE, f"WARNING: {total:.0f}s of narration makes the film longer than 90 s. Raise voice.tempo "
                   f"(e.g. 1.2) or lower voice.max_pause_s in storyboard.json; that costs no API calls.")
    return changed


def tighten(raw, tempo: float, max_pause: float):
    """Trim silence at both ends, shorten pauses longer than max_pause, and speed up by `tempo`
    (pitch kept). Derived from the cached TTS file, so changing these costs no API call."""
    out = raw.with_name(f"{raw.stem}-t{tempo:g}-p{max_pause:g}.wav")
    if cached(out):
        return out
    af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
          "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.1,areverse,"
          f"silenceremove=stop_periods=-1:stop_duration={max_pause + 0.25:g}:stop_threshold=-45dB:"
          f"stop_silence={max_pause:g}")
    if abs(tempo - 1.0) > 1e-3:
        af += f",atempo={tempo:g}"
    ffmpeg(["-i", str(raw), "-af", af, str(out)])
    return out


def _language_check(sb: dict, sid: str, text: str, lang_name: str):
    """Returns a check for gemini_tts: listen to the audio and reject it if anything other than
    the narration language is spoken (e.g. the model read its English directions aloud)."""
    def check(wav) -> str | None:
        q = (f"Listen to this narration. It should contain ONLY this {lang_name} text, spoken in {lang_name}:\n"
             f"{text}\n\nAnswer as JSON: {{\"spoken_language\": \"<English name of the main language heard, "
             f"e.g. Amharic>\", "
             f"\"other_language_heard\": true or false, \"other_words\": \"<any words heard in another "
             f"language, e.g. English, or empty>\"}}")
        try:
            a = gemini_inspect(q, [("audio/wav", wav.read_bytes())], model=sb["models"]["text"],
                               stage=STAGE, shot=sid)
        except CallFailed as e:
            say(STAGE, f"{sid}: could not run the language check ({str(e)[:80]}); keeping the audio, listen to it")
            return None
        heard = str(a.get("spoken_language", "")).strip().lower()
        names = {lang_name.lower(), sb["language"]["narration"].lower()} | _LANG_ALIASES.get(sb["language"]["narration"], set())
        lang_ok = heard in names or any(n in heard for n in names if len(n) > 3)
        other = str(a.get("other_words") or "").strip(" -")
        if not lang_ok or (a.get("other_language_heard") and other):
            return (f"audio is not purely {lang_name} (heard: {a.get('spoken_language')}; "
                    f"other words: {a.get('other_words') or '-'})")
        say(STAGE, f"{sid}: language check OK ({lang_name} only)")
        return None
    return check


_LANG_ALIASES = {"am": {"am", "amh", "amharic", "አማርኛ"}, "ti": {"ti", "tir", "tigrinya", "ትግርኛ"},
                 "om": {"om", "orm", "oromo", "afaan oromoo"}}

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
