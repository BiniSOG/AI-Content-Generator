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


def _gemini_post(model: str, body: dict, *, log: dict, timeout: int):
    """POST to the first model in the fallback chain that answers. Each model gets 2 attempts
    (the last one gets 4) before moving on; every attempt chain is logged under the model it used.
    Returns (response, model_used)."""
    key = need_env("GEMINI_API_KEY")
    chain = _fallbacks(model)
    last = None
    for i, m in enumerate(chain):
        is_last = i == len(chain) - 1
        try:
            r = http_call("POST", f"{GEMINI}/models/{m}:generateContent",
                          headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                          json=body, timeout=timeout, max_attempts=4 if is_last else 2,
                          log={**log, "model": m, "extra": {"requested_model": model}})
            if m != model:
                say(log.get("stage", "gemini"), f"used fallback model {m} (requested {model})")
            return r, m
        except CallFailed as e:
            last = e
            if not is_last:
                say(log.get("stage", "gemini"), f"{m} unavailable ({str(e)[:60]}); trying {chain[i+1]}")
    raise last


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


def gemini_list_models() -> list[str]:
    key = need_env("GEMINI_API_KEY")
    import requests
    r = requests.get(f"{GEMINI}/models", headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=60)
    r.raise_for_status()
    return [m["name"].removeprefix("models/") for m in r.json().get("models", [])]


# ---------------------------------------------------------------- Gemini TTS
def gemini_tts(text: str, *, model: str, voice: str, style: str | None, out_wav: Path,
               stage: str = "narration", shot: str | None = None, cache_key: str | None = None) -> Path:
    spoken = f"{style}\n\n{text}" if style else text
    body = {
        "contents": [{"parts": [{"text": spoken}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    r, _ = _gemini_post(model, body, timeout=180,
                        log=dict(stage=stage, shot=shot, provider="gemini",
                                 params={"voice": voice, "style": style, "chars": len(text)},
                                 seed=None, cache_key=cache_key, output=str(out_wav),
                                 units=len(text), unit="chars"))
    data = r.json()
    try:
        part = next(p for p in data["candidates"][0]["content"]["parts"] if "inlineData" in p)
    except (KeyError, IndexError, StopIteration):
        raise CallFailed(f"no audio in TTS response: {json.dumps(data)[:400]}")
    pcm = base64.b64decode(part["inlineData"]["data"])
    mime = part["inlineData"].get("mimeType", "")
    m = re.search(r"rate=(\d+)", mime)
    rate = int(m.group(1)) if m else 24000
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    if pcm[:4] == b"RIFF":
        out_wav.write_bytes(pcm)
    else:  # raw 16-bit little-endian mono PCM
        with wave.open(str(out_wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)
    return out_wav


# ---------------------------------------------------------------- Cloudflare FLUX
def cf_image(prompt: str, *, model: str, seed: int, out_png: Path, width: int = 1024, height: int = 1024,
             steps: int = 4, refs: list[Path] | None = None, stage: str = "keyframes",
             shot: str | None = None, cache_key: str | None = None) -> Path:
    acct = need_env("CF_ACCOUNT_ID")
    token = need_env("CF_API_TOKEN")
    url = f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"width": width, "height": height, "steps": steps,
              "refs": [str(p.name) for p in (refs or [])], "prompt_chars": len(prompt)}
    log = dict(stage=stage, shot=shot, provider="cloudflare", model=model, params=params, seed=seed,
               cache_key=cache_key, output=str(out_png), units=1, unit="image")

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
        log = {**log, "seed": None, "extra": {"requested_seed": seed, "seed_supported": False}}
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
