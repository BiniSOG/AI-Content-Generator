"""Shared plumbing for every stage: paths, storyboard loading + validation,
content-hash caching, retried HTTP calls, and the runs.jsonl call log.

Rule of the pipeline: a stage reads storyboard.json, computes a cache key from
exactly the inputs it uses, and only calls a model when no output exists for
that key. Every model call (success or failure) appends one line to runs.jsonl.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORYBOARD = ROOT / "storyboard.json"
SCHEMA = ROOT / "schema" / "storyboard.schema.json"
OUT = ROOT / "outputs"
RUNS = ROOT / "runs.jsonl"
PRICES = ROOT / "pipeline" / "prices.json"

RUN_ID = os.environ.get("RUN_ID") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:4]


# ---------------------------------------------------------------- env / io
def load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def need_env(name: str) -> str:
    load_env()
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"[config] {name} is not set. Copy .env.example to .env and fill it in.")
    return v


def out_dir(*parts: str) -> Path:
    p = OUT.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def say(stage: str, msg: str) -> None:
    print(f"[{stage}] {msg}", flush=True)


# ---------------------------------------------------------------- storyboard
def load_storyboard(validate: bool = True) -> dict:
    sb = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    if validate:
        validate_storyboard(sb)
    return sb


def validate_storyboard(sb: dict) -> None:
    import jsonschema
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(sb), key=lambda e: list(e.path))
    problems = [f"  - {'/'.join(map(str, e.path)) or '(root)'}: {e.message}" for e in errors]
    # Cross-field rules the schema cannot express
    ids = [s["id"] for s in sb.get("shots", [])]
    if len(ids) != len(set(ids)):
        problems.append("  - shots: duplicate shot ids")
    char_ids = {c["id"] for c in sb.get("characters", [])}
    for s in sb.get("shots", []):
        for c in s.get("characters", []):
            if c not in char_ids:
                problems.append(f"  - shots/{s['id']}: unknown character '{c}'")
    for cue in sb.get("music", {}).get("cues", []):
        if cue["at_shot"] not in ids:
            problems.append(f"  - music/cues: unknown shot '{cue['at_shot']}'")
    for c in sb.get("characters", []):
        if c.get("real_person"):
            ethics = (ROOT / "ETHICS.md").read_text(encoding="utf-8") if (ROOT / "ETHICS.md").exists() else ""
            if f"CONSENT:{c['id']}" not in ethics:
                problems.append(f"  - characters/{c['id']}: real_person=true but no 'CONSENT:{c['id']}' record in ETHICS.md")
    if problems:
        sys.exit("[validate] storyboard.json is invalid:\n" + "\n".join(problems))


def save_storyboard(sb: dict) -> None:
    validate_storyboard(sb)
    STORYBOARD.write_text(json.dumps(sb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def shot_by_id(sb: dict, sid: str) -> dict:
    for s in sb["shots"]:
        if s["id"] == sid:
            return s
    sys.exit(f"no shot {sid}")


# ---------------------------------------------------------------- caching
def cache_key(*parts) -> str:
    """Stable hash of exactly the inputs a stage uses. Change any input -> new key -> regenerate."""
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def cached(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def link_current(src: Path, dst: Path) -> None:
    """Point the stable name (e.g. s03.png) at the hashed file (s03-<key>.png)."""
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    shutil.copyfile(src, dst)


# ---------------------------------------------------------------- logging
def _price(model: str, units: float, unit: str) -> float | None:
    try:
        table = json.loads(PRICES.read_text(encoding="utf-8"))["models"]
    except Exception:
        return None
    entry = table.get(model)
    if not entry or entry.get("unit") != unit:
        return None
    return round(units * entry["usd_per_unit"], 6)


def log_call(*, stage: str, provider: str, model: str, params: dict, seed, latency_s: float,
             status: str, attempts: int, shot: str | None = None, cache_key: str | None = None,
             output: str | None = None, units: float | None = None, unit: str | None = None,
             gpu_s: float | None = None, error: str | None = None, extra: dict | None = None) -> None:
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "run_id": RUN_ID,
        "stage": stage,
        "shot": shot,
        "provider": provider,
        "model": model,
        "params": params,
        "seed": seed,
        "latency_s": round(latency_s, 3),
        "gpu_s": gpu_s,
        "status": status,
        "attempts": attempts,
        "cost_usd_free_tier": 0.0,
        "cost_usd_list_price": _price(model, units, unit) if units is not None and unit else None,
        "units": units,
        "unit": unit,
        "cache_key": cache_key,
        "output": output,
        "error": error,
    }
    if extra:
        rec.update(extra)
    with open(RUNS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- HTTP with retries
class CallFailed(Exception):
    pass


def http_call(method: str, url: str, *, log: dict, max_attempts: int = 4, timeout: int = 180, **kwargs):
    """requests wrapper: retries 429/5xx/timeouts with exponential backoff, logs exactly
    one runs.jsonl line for the logical call (with attempt count), raises CallFailed."""
    import requests
    t0 = time.time()
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.request(method, url, timeout=timeout, **kwargs)
            if r.status_code == 429 or r.status_code >= 500:
                last_err = f"HTTP {r.status_code}: {r.text[:300]}"
                wait = min(60, 2 ** attempt * 2)
                ra = r.headers.get("Retry-After")
                if ra and ra.isdigit():
                    wait = min(90, int(ra))
                say(log.get("stage", "http"), f"attempt {attempt} failed ({last_err[:80]}), retrying in {wait}s")
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                last_err = f"HTTP {r.status_code}: {r.text[:500]}"
                break  # client error: retrying will not help
            log_call(**log, latency_s=time.time() - t0, status="ok", attempts=attempt)
            return r
        except requests.RequestException as e:
            last_err = f"{type(e).__name__}: {e}"
            wait = min(60, 2 ** attempt * 2)
            say(log.get("stage", "http"), f"attempt {attempt} error ({last_err[:80]}), retrying in {wait}s")
            time.sleep(wait)
    log_call(**log, latency_s=time.time() - t0, status="error", attempts=attempt, error=last_err)
    raise CallFailed(last_err)


# ---------------------------------------------------------------- ffmpeg
def ffmpeg(args: list[str], quiet: bool = True) -> None:
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH. Install it (see README).")
    cmd = ["ffmpeg", "-y", "-hide_banner"] + (["-loglevel", "error"] if quiet else []) + args
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg failed:\n" + " ".join(cmd) + "\n" + p.stderr[-2000:])


def ffmpeg_capture(args: list[str]) -> str:
    p = subprocess.run(["ffmpeg", "-hide_banner"] + args, capture_output=True, text=True)
    return p.stderr


def duration_of(path: Path) -> float:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True)
    return float(p.stdout.strip())
