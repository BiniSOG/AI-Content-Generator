"""Controlled experiments: each changes ONE thing with the seed fixed, writes its outputs to
outputs/experiments/<id>/ and a result.json (every model call is also in runs.jsonl).
You look/listen and write the verdict in EXPERIMENTS.md. Already-run experiments are skipped.

  python run.py experiments            # run all that have not run yet
  python run.py experiments --only e07 # run one (delete its folder to re-run)"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .common import CallFailed, OUT, duration_of, ffmpeg, ffmpeg_capture, load_storyboard, out_dir, say, shot_by_id
from .keyframes import shot_prompt
from .providers import cf_image, gemini_text, gemini_tts
from . import shots as shots_stage

EXP = {}


def experiment(eid: str, hypothesis: str):
    def deco(fn):
        EXP[eid] = (hypothesis, fn)
        return fn
    return deco


def _img(sb, prompt, seed, out, model=None, refs=None):
    return cf_image(prompt, model=model or sb["models"]["image"], seed=seed, out_png=out, width=768, height=768,
                    refs=refs, stage="experiment")


@experiment("e01", "Appending the fixed style block makes a shot look like the rest of the film; without it the model drifts to a generic photo look.")
def e01(sb, d):
    s = shot_by_id(sb, "s02")
    with_style = shot_prompt(sb, s)
    without = with_style.replace(sb["style"]["block"], "").replace(". .", ".")
    _img(sb, with_style, s["seed"], d / "A_with_style.png")
    _img(sb, without, s["seed"], d / "B_without_style.png")
    return {"changed": "style block present vs removed", "fixed": f"seed {s['seed']}, model, shot s02"}


@experiment("e02", "Conditioning on the character reference image keeps the tortoise and the rabbit recognisable better than describing her in text alone.")
def e02(sb, d):
    s = shot_by_id(sb, "s04")
    p = shot_prompt(sb, s)
    refs = [OUT / "refs" / f"{c}.png" for c in s["characters"] if (OUT / "refs" / f"{c}.png").exists()]
    if not refs:
        raise SystemExit("e02 needs reference sheets: run `python run.py keyframes --ref-only` first")
    _img(sb, p, s["seed"], d / "A_with_refs.png", refs=refs)
    _img(sb, p, s["seed"], d / "B_text_only.png")
    return {"changed": "reference images on vs off", "fixed": f"seed {s['seed']}, prompt, shot s04"}


@experiment("e03", "FLUX.2 klein follows long prompts (props, clothing details) better than FLUX.1 schnell at similar speed.")
def e03(sb, d):
    s = shot_by_id(sb, "s06")
    p = shot_prompt(sb, s)
    t = {}
    for tag, model in (("A_klein", sb["models"]["image"]), ("B_schnell", sb["models"]["image_alt"])):
        t0 = time.time()
        _img(sb, p, s["seed"], d / f"{tag}.png", model=model)
        t[tag] = round(time.time() - t0, 2)
    return {"changed": "model", "fixed": f"seed {s['seed']}, prompt s06", "latency_s": t}


@experiment("e04", "Seed changes composition far more than identity; picking the best of 3 seeds is cheaper than rewriting the prompt.")
def e04(sb, d):
    s = shot_by_id(sb, "s07")
    p = shot_prompt(sb, s)
    refs = [OUT / "refs" / f"{c}.png" for c in s["characters"] if (OUT / "refs" / f"{c}.png").exists()]
    for seed in (s["seed"], s["seed"] + 1000, s["seed"] + 2000):
        _img(sb, p, seed, d / f"seed_{seed}.png", refs=refs or None)
    return {"changed": "seed only", "fixed": "prompt s07, model, refs"}


def _tts(sb, text, out, voice=None, style="__default__"):
    st = sb.get("voice", {}).get("style") if style == "__default__" else style
    gemini_tts(text, model=sb["models"]["tts"], voice=voice or sb.get("voice", {}).get("name", "Kore"),
               style=st, out_wav=out, stage="experiment", lang_name=sb["language"].get("narration_name"))
    return round(duration_of(out), 2)


@experiment("e05", "A short style instruction (calm, warm, unhurried) slows the delivery and makes it sound less like an announcement.")
def e05(sb, d):
    line = shot_by_id(sb, "s07")["narration"]
    text = line.get("spoken") or line["en"]
    return {"changed": "style instruction off vs on", "fixed": "voice, text s07",
            "duration_s": {"A_no_style": _tts(sb, text, d / "A_no_style.wav", style=None),
                           "B_style": _tts(sb, text, d / "B_style.wav")}}


@experiment("e06", "Voice choice matters less than the style instruction: two voices with the same instruction sound closer than one voice with and without it.")
def e06(sb, d):
    line = shot_by_id(sb, "s07")["narration"]
    text = line.get("spoken") or line["en"]
    return {"changed": "voice", "fixed": "style instruction, text s07",
            "duration_s": {v: _tts(sb, text, d / f"voice_{v}.wav", voice=v) for v in ("Kore", "Sulafat", "Aoede")}}


@experiment("e07", "Gemini TTS handles Amharic acceptably but Afaan Oromo and Tigrinya worse; back-translation shows where meaning is lost.")
def e07(sb, d):
    src = shot_by_id(sb, "s07")["narration"]["en"]
    out = {}
    for code, name in (("am", "Amharic"), ("om", "Afaan Oromo"), ("ti", "Tigrinya"), ("en", "English")):
        try:
            text = src if code == "en" else gemini_text(
                f"Translate into natural spoken {name}. Return only the translation.\n\n{src}",
                model=sb["models"]["text"], stage="experiment")
            dur = _tts(sb, text, d / f"{code}.wav")
            back = src if code == "en" else gemini_text(
                f"Translate this {name} text into English literally. Return only the translation.\n\n{text}",
                model=sb["models"]["text"], stage="experiment")
            out[code] = {"text": text, "back_translation": back, "duration_s": dur}
        except (CallFailed, Exception) as e:
            out[code] = {"error": str(e)[:300]}
    return {"changed": "language", "fixed": "voice, style, source line s07", "per_language": out,
            "listen_for": "ask a native speaker of each language to rate 1-5 and note mispronounced words"}


def _voice_and_music(sb, d):
    from .assemble import build_voice, timeline
    starts, total = timeline(sb)
    voice = build_voice(sb, starts, total, d / "voice.wav")
    return voice, total


def _measure(path: Path) -> float:
    err = ffmpeg_capture(["-i", str(path), "-af", "ebur128", "-f", "null", "-"])
    tail = err[err.rfind("Integrated loudness"):]
    try:
        return float(tail.split("I:")[1].split("LUFS")[0])
    except (IndexError, ValueError):
        return float("nan")


@experiment("e08", "Ratio 6 ducking keeps the voice clear without the music 'pumping'; ratio 2 leaves music too loud under speech, ratio 12 pumps.")
def e08(sb, d):
    voice, total = _voice_and_music(sb, d)
    score = OUT / "music" / "score.wav"
    res = {}
    for ratio in (2, 6, 12):
        mus = d / f"music_ducked_r{ratio}.wav"
        ffmpeg(["-i", str(voice), "-i", str(score), "-filter_complex",
                f"[1]atrim=0:{total:.2f},volume=-6dB[m];[m][0]sidechaincompress=threshold=0.02:ratio={ratio}:attack=300:release=1500[o]",
                "-map", "[o]", str(mus)])
        mix = d / f"mix_r{ratio}.wav"
        ffmpeg(["-i", str(voice), "-i", str(mus), "-filter_complex", "[0][1]amix=inputs=2:normalize=0", str(mix)])
        res[f"ratio_{ratio}"] = {"music_only_LUFS": _measure(mus), "mix_LUFS": _measure(mix)}
    res["voice_LUFS"] = _measure(voice)
    return {"changed": "sidechain ratio", "fixed": "threshold 0.02, attack 300, release 1500, same score", "measured": res}


@experiment("e09", "On a close-up of hands, a slow zoom-in reads as attention while a pan reads as searching; zoom fits the beat better.")
def e09(sb, d):
    kf = OUT / "keyframes" / "s05.png"
    if not kf.exists():
        raise SystemExit("e09 needs keyframe s05: run `python run.py keyframes` first")
    for kind in ("zoom_in", "pan_right", "static"):
        shots_stage.render_kenburns(kf, kind, 720, 1280, 6, d / f"{kind}.mp4")
    return {"changed": "Ken Burns move", "fixed": "keyframe s05, 6 s, 9:16"}


def run(only: set[str] | None = None) -> None:
    sb = load_storyboard()
    for eid, (hyp, fn) in EXP.items():
        if only and eid not in only:
            continue
        d = out_dir("experiments", eid)
        if (d / "result.json").exists():
            say("experiments", f"{eid} already ran (delete outputs/experiments/{eid} to re-run)")
            continue
        say("experiments", f"{eid}: {hyp}")
        t0 = time.time()
        try:
            res = fn(sb, d)
            res.update(hypothesis=hyp, seconds=round(time.time() - t0, 1),
                       outputs=sorted(p.name for p in d.iterdir() if p.name != "result.json"))
            (d / "result.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
            say("experiments", f"{eid}: done -> outputs/experiments/{eid}/ (write your verdict in EXPERIMENTS.md)")
        except SystemExit as e:
            say("experiments", f"{eid}: skipped: {e}")
        except CallFailed as e:
            say("experiments", f"{eid}: FAILED: {str(e)[:200]} (note it in FAILURES.md)")
