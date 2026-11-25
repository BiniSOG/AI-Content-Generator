"""English subtitles from storyboard narration.en, timed to the measured narration audio.
At most 2 lines of ~40 characters per cue; long lines are split at sentence/comma boundaries
and timed in proportion to their length."""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

MAX_CHARS = 40


def _chunks(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
    out = []
    for p in parts:
        if len(p) <= 2 * MAX_CHARS:
            out.append(p)
        else:  # split at commas, then hard-wrap
            buf = ""
            for piece in re.split(r"(?<=,)\s+", p):
                if len(buf) + len(piece) + 1 <= 2 * MAX_CHARS:
                    buf = f"{buf} {piece}".strip()
                else:
                    if buf:
                        out.append(buf)
                    buf = piece
            if buf:
                out.append(buf)
    return out


def _ts(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def build_srt(sb: dict, starts: dict[str, float], voice_dur: dict[str, float], path: Path) -> Path:
    cues = []
    for s in sb["shots"]:
        sid = s["id"]
        t0 = starts[sid] + s["narration"].get("lead_in_s", 0.4)
        dur = max(voice_dur.get(sid, 2.5), 1.2)
        chunks = _chunks(s["narration"]["en"])
        total = sum(len(c) for c in chunks)
        t = t0
        for c in chunks:
            span = dur * len(c) / total
            lines = textwrap.wrap(c, MAX_CHARS)[:2]
            cues.append((t, t + span, "\n".join(lines)))
            t += span
    with open(path, "w", encoding="utf-8") as f:
        for i, (a, b, txt) in enumerate(cues, 1):
            f.write(f"{i}\n{_ts(a)} --> {_ts(b)}\n{txt}\n\n")
    return path
