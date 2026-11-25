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


# ---------------------------------------------------------------- Gemini text
def gemini_text(prompt: str, *, model: str, stage: str, shot: str | None = None,
                cache_key: str | None = None, temperature: float = 0.4) -> str:
    key = need_env("GEMINI_API_KEY")
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature}}
    r = http_call("POST", f"{GEMINI}/models/{model}:generateContent",
                  headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                  json=body,
                  log=dict(stage=stage, shot=shot, provider="gemini", model=model,
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
    key = need_env("GEMINI_API_KEY")
    spoken = f"{style}\n\n{text}" if style else text
    body = {
        "contents": [{"parts": [{"text": spoken}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    r = http_call("POST", f"{GEMINI}/models/{model}:generateContent",
                  headers={"x-goog-api-key": key, "Content-Type": "application/json"},
                  json=body, timeout=240,
                  log=dict(stage=stage, shot=shot, provider="gemini", model=model,
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
        body = {"prompt": prompt, "seed": seed, "steps": min(steps, 8)}
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
