"""Stage 5 - music. ACE-Step 1.5 runs on Kaggle (kaggle/ace_step_score.py) and writes
candidates to outputs/kaggle/music/cand_N.wav plus their log lines. This stage:
  * merges the Kaggle log lines into runs.jsonl (once each),
  * takes the candidate named in storyboard music.chosen,
  * or, before any score exists, makes an obvious placeholder pad for the radio cut.
Output: outputs/music/score.wav, loudness-matched so mixing decisions are creative, not repairs."""
from __future__ import annotations

import json
import time

from .common import OUT, RUNS, cache_key, cached, ffmpeg, file_hash, link_current, load_storyboard, log_call, out_dir, say

STAGE = "music"
PRE_LUFS = -20  # music sits below the voice before ducking


def merge_kaggle_logs() -> int:
    seen = set()
    if RUNS.exists():
        for line in RUNS.read_text(encoding="utf-8").splitlines():
            try:
                cid = json.loads(line).get("call_id")
                if cid:
                    seen.add(cid)
            except json.JSONDecodeError:
                pass
    added = 0
    for f in sorted((OUT / "kaggle").glob("**/runs_kaggle.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("call_id") in seen:
                continue
            with open(RUNS, "a", encoding="utf-8") as out:
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            seen.add(rec.get("call_id"))
            added += 1
    if added:
        say(STAGE, f"merged {added} Kaggle log line(s) into runs.jsonl")
    return added


def candidates() -> list:
    d = OUT / "kaggle" / "music"
    return sorted([p for p in d.glob("cand_*") if p.suffix in {".wav", ".flac", ".mp3"}]) if d.exists() else []


def run(sb: dict | None = None, only=None, placeholder_ok: bool = True) -> list[str]:
    sb = sb or load_storyboard()
    merge_kaggle_logs()
    d = out_dir("music")
    m = sb["music"]
    cands = candidates()
    chosen = next((c for c in cands if c.name == m.get("chosen")), None)
    if chosen is None and cands:
        chosen = cands[0]
        say(STAGE, f"music.chosen not set; using {chosen.name} for now. Listen to all {len(cands)} and set it.")
    if chosen is not None:
        key = cache_key(file_hash(chosen), PRE_LUFS)
        src_desc = chosen.name
    else:
        if not placeholder_ok:
            raise SystemExit("[music] no ACE-Step candidates in outputs/kaggle/music/. Run the Kaggle notebook.")
        key = cache_key("placeholder", m["duration_s"], PRE_LUFS)
        src_desc = "PLACEHOLDER pad (not the final score)"
    target = d / f"score-{key}.wav"
    if not cached(target):
        t0 = time.time()
        if chosen is not None:
            ffmpeg(["-i", str(chosen), "-af", f"loudnorm=I={PRE_LUFS}:TP=-2:LRA=11", "-ar", "48000", "-ac", "2", str(target)])
        else:
            dur = m["duration_s"]
            # soft C-minor pad from sine tones; clearly a placeholder
            tones = [130.81, 155.56, 196.00, 261.63]
            inputs = []
            for f in tones:
                inputs += ["-f", "lavfi", "-i", f"sine=frequency={f}:duration={dur}"]
            mix = "".join(f"[{i}]" for i in range(len(tones)))
            af = (f"{mix}amix=inputs={len(tones)},tremolo=f=0.15:d=0.4,lowpass=f=900,"
                  f"afade=t=in:d=3,afade=t=out:st={dur-4}:d=4,loudnorm=I={PRE_LUFS}")
            ffmpeg(inputs + ["-filter_complex", af, "-ar", "48000", "-ac", "2", str(target)])
        log_call(stage=STAGE, provider="local", model="ffmpeg", params={"source": src_desc}, seed=None,
                 latency_s=time.time() - t0, status="ok", attempts=1, cache_key=key, output=str(target))
        say(STAGE, f"score prepared from {src_desc}")
    else:
        say(STAGE, f"score cached ({src_desc})")
    link_current(target, d / "score.wav")
    return [src_desc]
