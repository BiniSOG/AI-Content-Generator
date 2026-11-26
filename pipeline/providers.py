"""Thin clients for the hosted models. Every function goes through common.http_call,
so every call is retried and logged to runs.jsonl."""
from __future__ import annotations

import base64
import io
import json
import re
import wave
from pathlib import Path

from .common import CallFailed, http_call, need_env, say

GEMINI = "https://generativelanguage.googleapis.com/v1beta"


def _fallbacks(model: str) -> list[str]:
    """Primary model first, then the fallbacks listed in storyboard.json models.text_fallbacks /
    models.tts_fallbacks. Used when a model is overloaded (HTTP 503) or rate-limited."""
    from .common import STORYBOARD
    try:
        m = json.loads(STORYBOARD.read_text(encoding="utf-8"))["models"]
    except Exception:
        return [model]
    for primary, alts in ((m.get("text"), m.get("text_fallbacks", [])), (m.get("tts"), m.get("tts_fallbacks", []))):
        if model == primary:
            return [model] + [a for a in alts if a != model]
    return [model]


# model -> time until which it is considered busy (503 / 429 / timeout). Shared by every call in
# this process, so a run of 9 lines doesn't re-try the same overloaded models 9 times.
_BUSY_UNTIL: dict[str, float] = {}
BUSY_COOLDOWN_S = 180


def _gemini_post(model: str, body: dict, *, log: dict, timeout: int, rounds: int = 4,
                 exclude: set[str] | None = None):
    """POST to the first model in the fallback chain that answers.

    - A 503 means *that model* is overloaded, so each model is tried once per round and the
      pipeline only waits (5, 15, 30 s) after a whole round failed.
    - A model that was busy in the last BUSY_COOLDOWN_S seconds is tried *after* the others,
      so once a fallback works, the following calls go straight to it. The primary is tried
      first again when its cooldown ends.
    - Early rounds use a shorter timeout (half), so a hanging model costs 45 s, not 90 s.
    - Models answering a non-retryable 4xx are dropped. Returns (response, model_used)."""
    import time
    key = need_env("GEMINI_API_KEY")
    chain = [m for m in _fallbacks(model) if m not in (exclude or set())]
    if not chain:
        raise CallFailed(f"no models left to try (excluded: {', '.join(sorted(exclude or []))})")
    stage = log.get("stage", "gemini")
    waits = [5, 15, 30]
    last = None
    errors: dict[str, str] = {}
    for rnd in range(rounds):
        now = time.time()
        busy = [m for m in chain if _BUSY_UNTIL.get(m, 0) > now]
        order = [m for m in chain if m not in busy] + busy
        if busy and rnd == 0 and len(busy) < len(chain):
            say(stage, f"skipping recently busy model(s) for now: {', '.join(busy)}")
        t_out = timeout if rnd == rounds - 1 else max(30, timeout // 2)
        for m in order:
            try:
                r = http_call("POST", f"{GEMINI}/models/{m}:generateContent",
                              headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                              json=body, timeout=t_out, max_attempts=1,
                              log={**log, "model": m, "extra": {"requested_model": model, "round": rnd + 1}})
                _BUSY_UNTIL.pop(m, None)
                if m != model:
                    say(stage, f"used fallback model {m} (requested {model})")
                return r, m
            except CallFailed as e:
                last = e
                errors[m] = str(e)[:160]
                retryable = e.status is None or e.status == 429 or e.status >= 500
                if retryable:
                    _BUSY_UNTIL[m] = time.time() + BUSY_COOLDOWN_S
                else:
                    chain.remove(m)
                say(stage, f"{m} unavailable ({str(e)[:90]})" + ("" if retryable else "; dropping it"))
        if not chain:
            break
        if rnd < rounds - 1:
            wait = waits[min(rnd, len(waits) - 1)]
            say(stage, f"all models busy (round {rnd + 1}/{rounds}); retrying the chain in {wait}s")
            time.sleep(wait)
    summary = "; ".join(f"{m}: {err}" for m, err in errors.items())
    raise CallFailed(f"every model in the chain failed after {rnd + 1} round(s) -- {summary}",
                     status=getattr(last, "status", None))


# ---------------------------------------------------------------- Gemini text
def gemini_text(prompt: str, *, model: str, stage: str, shot: str | None = None,
                cache_key: str | None = None, temperature: float = 0.4) -> str:
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature}}
    r, _ = _gemini_post(model, body, timeout=90,
                        log=dict(stage=stage, shot=shot, provider="gemini",
                                 params={"temperature": temperature, "prompt_chars": len(prompt)},
                                 seed=None, cache_key=cache_key, units=len(prompt) / 4, unit="input_tokens_est"))
    data = r.json()
    try:
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
    except (KeyError, IndexError):
        raise CallFailed(f"unexpected Gemini response: {json.dumps(data)[:400]}")


def gemini_inspect(question: str, media: list[tuple[str, bytes]], *, model: str, stage: str,
                   shot: str | None = None) -> dict:
    """Ask a Gemini text model about an image or a sound (inline data) and get JSON back.
    Used for automatic checks: count the people in a keyframe, check the narration language."""
    parts = [{"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}} for mime, data in media]
    parts.append({"text": question})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}}
    r, _ = _gemini_post(model, body, timeout=90,
                        log=dict(stage=stage, shot=shot, provider="gemini", params={"check": question[:80]},
                                 seed=None, cache_key=None, units=len(question) / 4, unit="input_tokens_est"))
    data = r.json()
    try:
        txt = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
        txt = txt.strip("`").removeprefix("json").strip()
        return json.loads(txt)
    except (KeyError, IndexError, json.JSONDecodeError):
        raise CallFailed(f"unexpected inspection answer: {json.dumps(data)[:300]}")


def gemini_list_models() -> list[str]:
    key = need_env("GEMINI_API_KEY")
    import requests
    r = requests.get(f"{GEMINI}/models", headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=60)
    r.raise_for_status()
    return [m["name"].removeprefix("models/") for m in r.json().get("models", [])]


# ---------------------------------------------------------------- Gemini TTS
def tts_prompt(text: str, style: str | None, lang_name: str | None) -> str:
    """The text sent to the TTS model. The direction and the transcript are clearly separated, and the
    model is told to speak ONLY the transcript, in its language: with the old "style + blank line + text"
    form, TTS models sometimes read the English direction aloud before the line."""
    if not style and not lang_name:
        return text
    lang = lang_name or "the transcript's language"
    direction = (f"Read the transcript below aloud in {lang}, as a native {lang} speaker with natural "
                 f"{lang} pronunciation and rhythm. Speak only the transcript, word for word. Do not say these "
                 f"directions aloud and do not translate anything.")
    if style:
        direction += f" Delivery: {style}"
    return f"{direction}\n\nTRANSCRIPT:\n{text}"


def gemini_tts(text: str, *, model: str, voice: str, style: str | None, out_wav: Path,
               stage: str = "narration", shot: str | None = None, cache_key: str | None = None,
               lang_name: str | None = None, check=None) -> Path:
    """Speak `text` to out_wav. A model that answers HTTP 200 but with silent or near-empty audio
    (seen when a TTS model doesn't really support the language, e.g. Amharic) counts as a failure,
    and the next model in models.tts_fallbacks is tried."""
    from .common import is_silent, audio_stats
    spoken = tts_prompt(text, style, lang_name)
    body = {
        "contents": [{"parts": [{"text": spoken}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    # ~0.04 s per character is very fast speech; less than that means the audio is truncated.
    min_s = max(0.8, min(len(text) * 0.04, 4.0))
    tried: set[str] = set()
    while True:
        r, used = _gemini_post(model, body, timeout=180, exclude=tried,
                               log=dict(stage=stage, shot=shot, provider="gemini",
                                        params={"voice": voice, "style": style, "chars": len(text),
                                                "language": lang_name},
                                        seed=None, cache_key=cache_key, output=str(out_wav),
                                        units=len(text), unit="chars"))
        _write_tts_audio(r.json(), out_wav)
        dur, mx = audio_stats(out_wav)
        if is_silent(out_wav, min_s=min_s):
            problem = f"unusable audio ({dur:.1f}s, peak {mx} dB) for {len(text)} chars"
        else:
            problem = check(out_wav) if check else None
            if not problem:
                return out_wav
        tried.add(used)
        say(stage, f"{used}: {problem}; trying the next TTS model")
        out_wav.unlink(missing_ok=True)


def _write_tts_audio(data: dict, out_wav: Path) -> None:
    try:
        part = next(p for p in data["candidates"][0]["content"]["parts"] if "inlineData" in p)
    except (KeyError, IndexError, StopIteration):
        raise CallFailed(f"no audio in TTS response: {json.dumps(data)[:400]}")
    raw = base64.b64decode(part["inlineData"]["data"])
    mime = part["inlineData"].get("mimeType", "").lower()
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if raw[:4] == b"RIFF":
        out_wav.write_bytes(raw)
    elif "l16" in mime or "pcm" in mime or not mime:
        # raw 16-bit little-endian mono PCM (what Gemini TTS normally returns)
        m = re.search(r"rate=(\d+)", mime)
        rate = int(m.group(1)) if m else 24000
        with wave.open(str(out_wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(raw)
    else:
        # a compressed format (mp3/ogg/...): let ffmpeg decode it instead of writing noise
        from .common import ffmpeg
        ext = {"audio/mpeg": ".mp3", "audio/mp3": ".mp3", "audio/ogg": ".ogg", "audio/opus": ".opus",
               "audio/flac": ".flac", "audio/aac": ".aac"}.get(mime.split(";")[0], ".bin")
        tmp = out_wav.with_suffix(ext)
        tmp.write_bytes(raw)
        ffmpeg(["-i", str(tmp), "-ac", "1", "-ar", "24000", str(out_wav)])
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------- Cloudflare FLUX
FLAGGED_SEED_STEPS = (0, 1000, 2000)  # deterministic alternate seeds tried when an output is flagged


def cf_image(prompt: str, *, model: str, seed: int, out_png: Path, **kw) -> Path:
    """Workers AI sometimes flags a harmless output (HTTP 400, code 3030 "Your output has been
    flagged"). The same prompt+seed gives the same image, so a plain retry fails again; instead we
    retry with seed+1000, seed+2000. The sequence is fixed, so the result is still reproducible,
    and the seed actually used is logged (extra.seed_used)."""
    last = None
    for step in FLAGGED_SEED_STEPS:
        try:
            out = _cf_image_once(prompt, model=model, seed=seed + step, requested_seed=seed,
                                 out_png=out_png, **kw)
            if step:
                say(kw.get("stage", "keyframes"), f"output was flagged at seed {seed}; used seed {seed + step}")
            return out
        except CallFailed as e:
            if "3030" not in str(e) or "flux-2" not in model:  # schnell ignores seed: nothing to vary
                raise
            last = e
            say(kw.get("stage", "keyframes"), f"output flagged by Cloudflare's filter at seed {seed + step}; trying another seed")
    raise last


def _cf_image_once(prompt: str, *, model: str, seed: int, out_png: Path, width: int = 1024, height: int = 1024,
             steps: int = 4, refs: list[Path] | None = None, stage: str = "keyframes",
             shot: str | None = None, cache_key: str | None = None, requested_seed: int | None = None) -> Path:
    acct = need_env("CF_ACCOUNT_ID")
    token = need_env("CF_API_TOKEN")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"width": width, "height": height, "steps": steps,
              "refs": [str(p.name) for p in (refs or [])], "prompt_chars": len(prompt)}
    log = dict(stage=stage, shot=shot, provider="cloudflare", model=model, params=params, seed=seed,
               cache_key=cache_key, output=str(out_png), units=1, unit="image",
               extra={"requested_seed": requested_seed if requested_seed is not None else seed, "seed_used": seed})

    if "flux-2" in model:
        # FLUX.2 on Workers AI takes multipart form-data; reference images go in input_image_N.
        fields = {"prompt": (None, prompt), "seed": (None, str(seed)), "width": (None, str(width)),
                  "height": (None, str(height)), "steps": (None, str(steps))}
        for i, ref in enumerate(refs or []):
            fields[f"input_image_{i}"] = (ref.name, ref.read_bytes(), "image/png")
        r = http_call("POST", url, headers=headers, files=fields, log=log)
    else:
        # FLUX.1 schnell on Workers AI rejects a "seed" field (HTTP 400), so its outputs are
        # not seed-reproducible; the log records seed=None for it (see FAILURES.md).
        body = {"prompt": prompt, "steps": min(steps, 8)}
        log = {**log, "seed": None, "extra": {"requested_seed": seed, "seed_used": None, "seed_supported": False}}
        r = http_call("POST", url, headers=headers, json=body, log=log)

    ctype = r.headers.get("Content-Type", "")
    if ctype.startswith("image/"):
        raw = r.content
    else:
        data = r.json()
        res = data.get("result", data)
        b64 = res.get("image") if isinstance(res, dict) else None
        if not b64:
            raise CallFailed(f"no image in Cloudflare response: {json.dumps(data)[:400]}")
        raw = base64.b64decode(b64)
    from PIL import Image
    out_png.parent.mkdir(parents=True, exist_ok=True)
    Image.open(io.BytesIO(raw)).convert("RGB").save(out_png)
    return out_png


def cf_image_with_fallback(prompt: str, *, sb: dict, **kw) -> tuple[Path, str]:
    """Try the primary image model; if it fails after retries, fall back to image_alt.
    Returns (path, model_used)."""
    primary = sb["models"]["image"]
    alt = sb["models"].get("image_alt")
    try:
        return cf_image(prompt, model=primary, **kw), primary
    except CallFailed as e:
        if not alt:
            raise
        say(kw.get("stage", "keyframes"), f"{primary} failed ({str(e)[:120]}); falling back to {alt}")
        kw.pop("refs", None)  # schnell is text-only
        return cf_image(prompt, model=alt, **kw), alt
