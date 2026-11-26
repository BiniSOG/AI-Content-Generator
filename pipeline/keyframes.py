"""Stage 3 - keyframes. First a reference image per character (the character sheet),
then one keyframe per shot conditioned on the references of the characters in it.
Every prompt = shot prompt + character descriptions + the fixed style block, so nothing
is re-described differently between shots.

Cache key = full prompt + seed + model + size + hash of each reference image, so changing a
character reference correctly regenerates every shot that uses that character, and only those."""
from __future__ import annotations

import json
from pathlib import Path

from .common import CallFailed, cache_key, cached, file_hash, link_current, load_storyboard, out_dir, say
from .providers import SEED_USED, QuotaExhausted, cf_image_with_fallback, gemini_inspect

STAGE = "keyframes"
MAX_PROMPT = 2048  # Workers AI FLUX prompt limit
SIZE = 1024  # square, subject centred: both 16:9 and 9:16 are cropped from it


REF_STYLE = ("realistic photograph, soft even daylight, true-to-life skin tones and natural texture, sharp focus "
             "on every face, no text, no letters, no watermark")
REF_FRAMING = ("Full body, facing the camera at a slight three-quarter angle, the whole face clearly visible, "
               "plain soft warm neutral background")


def ref_prompt(sb: dict, ch: dict) -> str:
    # One clear image, not a two-panel sheet: the shots copy identity from it, and a two-panel
    # sheet used as a reference tends to make the shots come out as two panels.
    framing = ch.get("ref_framing") or REF_FRAMING
    return f"Character reference image of fictional people. {ch['description']}. {framing}. {REF_STYLE}"


def shot_prompt(sb: dict, shot: dict) -> str:
    chars = {c["id"]: c for c in sb["characters"]}
    who = " ".join(f"{chars[c].get('short') or chars[c]['description']}." for c in shot["characters"])
    setting = sb["style"].get("setting")
    parts = ([setting] if setting else []) + [shot["image_prompt"]]
    if who:
        parts.append(f"Characters (match the reference images exactly): {who}")
    parts.append(sb["style"]["block"])
    prompt = " ".join(p.strip().rstrip(".") + "." for p in parts)
    if len(prompt) > MAX_PROMPT:
        raise SystemExit(f"[keyframes] {shot['id']}: prompt is {len(prompt)} chars; Cloudflare's limit is "
                         f"{MAX_PROMPT}. Shorten image_prompt or the character 'short' text.")
    # No "Avoid: <negative>" here: FLUX has no negative prompt, so those words (deformed hands,
    # extra fingers...) went into the *positive* prompt. style.negative is still used by Wan.
    return prompt


def refs(sb: dict, regenerate: set[str] | None = None) -> list[str]:
    d = out_dir("refs")
    changed = []
    for ch in sb["characters"]:
        prompt = ref_prompt(sb, ch)
        seed = ch.get("ref_seed", 1)
        key = cache_key(prompt, seed, sb["models"]["image"], SIZE)
        target = d / f"{ch['id']}-{key}.png"
        if not cached(target) or (regenerate and ch["id"] in regenerate):
            say(STAGE, f"reference sheet for {ch['id']} (seed {seed})")
            try:
                generate_checked(sb, prompt, seed, target, ch.get("count", 1), f"ref:{ch['id']}",
                                 width=SIZE, height=SIZE, stage=STAGE, shot=f"ref:{ch['id']}", cache_key=key)
            except QuotaExhausted as e:
                raise SystemExit(f"[keyframes] stopped at the reference for {ch['id']}: {e}")
            changed.append(ch["id"])
        link_current(target, d / f"{ch['id']}.png")
    say(STAGE, f"references: {len(changed)} generated, look at outputs/refs/*.png")
    return changed


COUNT_RETRY_STEPS = (1000, 2000)  # fixed alternate seeds; each try costs a FLUX image from the daily allowance


def count_people(sb: dict, png: Path, shot: str) -> int | None:
    """How many people Gemini sees in the image; None if the check could not run."""
    q = ("Count the people in this image. Count every person whose face or body is visible, even partly, "
         "including people at the edges or in the background. Do not count paintings or reflections. "
         'Answer as JSON: {"people": <integer>}')
    try:
        a = gemini_inspect(q, [("image/png", png.read_bytes())], model=sb["models"]["text"], stage=STAGE, shot=shot)
        return int(a["people"])
    except Exception as e:
        say(STAGE, f"{shot}: people-count check failed ({str(e)[:80]}); look at the image yourself")
        return None


def generate_checked(sb: dict, prompt: str, seed: int, target: Path, want: int | None, label: str, **kw) -> tuple[str, int]:
    """Generate an image; if `want` people are expected and Gemini counts a different number, try the
    next fixed seeds and keep the first image with the right count. Returns (model_used, seed_used)."""
    _, used = cf_image_with_fallback(prompt, sb=sb, seed=seed, out_png=target, **kw)
    seed = SEED_USED.get(str(target), seed)  # a content-filter retry may have changed it
    if want is None:
        return used, seed
    n = count_people(sb, target, label)
    if n is None or n == want:
        if n is not None:
            say(STAGE, f"{label}: {n} people, as expected")
        return used, seed
    for step in COUNT_RETRY_STEPS:
        say(STAGE, f"{label}: counted {n} people, expected {want}; trying seed {seed + step}")
        alt = target.with_name(target.stem + f"-alt{step}.png")
        _, used2 = cf_image_with_fallback(prompt, sb=sb, seed=seed + step, out_png=alt, **kw)
        real = SEED_USED.get(str(alt), seed + step)
        n = count_people(sb, alt, label)
        if n == want:
            alt.replace(target)
            say(STAGE, f"{label}: seed {real} has {want} people; using it")
            return used2, real
        alt.unlink(missing_ok=True)
    say(STAGE, f"{label}: WARNING no seed gave {want} people; kept seed {seed}. Look at it, change the seed "
               f"in storyboard.json or simplify the prompt")
    return used, seed


def ref_candidates(sb: dict, only: set[str] | None = None, n: int = 4) -> None:
    """Render n reference sheets per character at different seeds, so you can pick the face
    that looks right and put its seed in characters[].ref_seed."""
    d = out_dir("refs") / "candidates"
    for ch in sb["characters"]:
        if only and ch["id"] not in only:
            continue
        prompt = ref_prompt(sb, ch)
        base = ch.get("ref_seed", 1)
        for i in range(n):
            seed = base + i * 111
            target = d / f"{ch['id']}-seed{seed}.png"
            if cached(target) or list(d.glob(f"{target.stem}-*.png")):
                continue
            say(STAGE, f"candidate {ch['id']} seed {seed}")
            try:
                cf_image_with_fallback(prompt, sb=sb, seed=seed, out_png=target, width=SIZE, height=SIZE,
                                       stage=STAGE, shot=f"refcand:{ch['id']}")
            except QuotaExhausted as e:
                raise SystemExit(f"[keyframes] stopped: {e}")
                want = ch.get("count", 1)
                if want > 1:
                    n = count_people(sb, target, f"refcand:{ch['id']}")
                    tag = "OK" if n == want else f"WRONG{n}"
                    target.replace(target.with_name(f"{target.stem}-{tag}.png"))
                    say(STAGE, f"  {n} people counted (need {want}) -> {tag}")
            except Exception as e:
                say(STAGE, f"  failed: {str(e)[:120]}")
    say(STAGE, f"look at {d}/ ; put the seed you like in storyboard.json characters[].ref_seed, "
               "then: python run.py keyframes --ref-only")


def run(sb: dict | None = None, only: set[str] | None = None, ref_only: bool = False) -> list[str]:
    sb = sb or load_storyboard()
    refs(sb)
    if ref_only:
        return []
    d = out_dir("keyframes")
    ref_dir = out_dir("refs")
    golden = sb["style"].get("golden_ref")
    changed, failed = [], []
    meta_path = d / "manifest.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    for s in sb["shots"]:
        ref_files = [ref_dir / f"{c}.png" for c in s["characters"]]
        if golden and Path(golden).exists():
            ref_files.append(Path(golden))
        prompt = shot_prompt(sb, s)
        key = cache_key(prompt, s["seed"], sb["models"]["image"], SIZE, [file_hash(r) for r in ref_files])
        target = d / f"{s['id']}-{key}.png"
        if (only is None or s["id"] in only) and not cached(target):
            say(STAGE, f"{s['id']}: generating (seed {s['seed']}, {len(ref_files)} ref(s))")
            try:
                used, seed_used = generate_checked(sb, prompt, s["seed"], target, s.get("people_count"), s["id"],
                                                   width=SIZE, height=SIZE, refs=ref_files, stage=STAGE,
                                                   shot=s["id"], cache_key=key)
                meta[s["id"]] = {"file": target.name, "key": key, "model": used, "seed": seed_used}
                changed.append(s["id"])
            except QuotaExhausted as e:
                meta_path.write_text(json.dumps(meta, indent=2))
                raise SystemExit(f"[keyframes] stopped at {s['id']}: {e}\nDone so far: "
                                 f"{', '.join(changed) or 'none new'} (kept in the cache).")
            except CallFailed as e:
                say(STAGE, f"{s['id']}: FAILED after retries: {str(e)[:200]}")
                failed.append(s["id"])
                if s["id"] in meta:
                    meta[s["id"]]["stale"] = True  # older keyframe is used until a rerun succeeds
        if cached(target):
            link_current(target, d / f"{s['id']}.png")
            meta.setdefault(s["id"], {"file": target.name, "key": key})
            meta[s["id"]].update(file=target.name, key=key, stale=False)
    meta_path.write_text(json.dumps(meta, indent=2))
    say(STAGE, f"{len(changed)} regenerated" + (f": {', '.join(changed)}" if changed else " (all cached)")
        + (f"; FAILED: {', '.join(failed)} (rerun later, cache keeps the rest)" if failed else ""))
    if failed:
        raise SystemExit(f"[keyframes] {', '.join(failed)} failed; not continuing to a film with missing "
                         f"pictures. Run the same command again (finished shots are cached).")
    return changed
