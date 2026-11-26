"""Subtitles from the storyboard narration, timed to the measured narration audio.
language.subtitles: "en" (narration.en), "am" (narration.spoken) or "am+en" (spoken on top, English
smaller underneath, paired sentence by sentence).
At most 2 lines of ~40 characters per cue; long lines are split at sentence/comma boundaries
and timed in proportion to their length."""
from __future__ import annotations

import re
import textwrap
from pathlib import Path

MAX_CHARS = 40
MAX_CHARS_ETHIOPIC = 30  # Ge'ez letters are wider


def subtitle_font(mode: str) -> str:
    """A font that has Ethiopic letters when Amharic is on screen (DejaVu Sans has none, so the
    letters would be drawn as empty boxes)."""
    import shutil
    import subprocess
    import sys
    if mode == "en":
        return "DejaVu Sans"
    if sys.platform.startswith("win"):
        return "Nyala"          # ships with Windows; Ebrima also has Ethiopic
    if sys.platform == "darwin":
        return "Kefa"           # ships with macOS
    if shutil.which("fc-list"):
        out = subprocess.run(["fc-list", ":lang=am", "family"], capture_output=True, text=True).stdout
        fams = [l.split(",")[0].strip() for l in out.splitlines() if l.strip()]
        for pref in ("Noto Sans Ethiopic", "Abyssinica SIL", "Noto Serif Ethiopic"):
            if pref in fams:
                return pref
        if fams:
            return fams[0]
    raise SystemExit("[subtitles] no font with Amharic (Ethiopic) letters found. Install one, e.g. "
                     "'sudo apt install fonts-noto-core' or 'fonts-sil-abyssinica', or set language.subtitles to en.")


def _sentences_ethiopic(text: str) -> list[str]:
    """Sentences (ending in ። ! ?), each split further at ፣ ፤ ፦ so a cue fits on two lines."""
    out = []
    for sent in [p.strip() for p in re.findall(r"[^።!?]+[።!?]?[»”]?", text) if p.strip(" »”")]:
        if len(sent) <= 2 * MAX_CHARS_ETHIOPIC:
            out.append(sent)
            continue
        buf = ""
        for piece in re.split(r"(?<=[፣፤፦])\s*", sent):
            if buf and len(buf) + len(piece) + 1 > 2 * MAX_CHARS_ETHIOPIC:
                out.append(buf)
                buf = piece
            else:
                buf = f"{buf} {piece}".strip()
        if buf:
            out.append(buf)
    return out


def _split_words(text: str, n: int) -> list[str]:
    """Split text into n pieces of similar length at word boundaries (used to give each Amharic
    cue a matching share of the English line when the sentence counts differ)."""
    words = text.split()
    if n <= 1 or len(words) < n:
        return [text] + [""] * (n - 1)
    target = len(text) / n
    pieces, buf = [], []
    for w in words:
        buf.append(w)
        if len(pieces) < n - 1 and len(" ".join(buf)) >= target:
            pieces.append(" ".join(buf))
            buf = []
    pieces.append(" ".join(buf))
    return pieces + [""] * (n - len(pieces))


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


def _wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width))  # never drop text


def build_srt(sb: dict, starts: dict[str, float], voice_dur: dict[str, float], path: Path) -> Path:
    mode = sb["language"].get("subtitles", "en")
    cues = []
    for s in sb["shots"]:
        sid = s["id"]
        t0 = starts[sid] + s["narration"].get("lead_in_s", 0.4)
        dur = max(voice_dur.get(sid, 2.5), 1.2)
        en = s["narration"]["en"]
        am = s["narration"].get("spoken") or en
        if mode == "en":
            pairs = [(None, c) for c in _chunks(en)]
        elif mode == "am":
            pairs = [(c, None) for c in _sentences_ethiopic(am)]
        else:  # am+en: pair sentence by sentence when the counts match, else one cue for the shot
            a, e = _sentences_ethiopic(am), _chunks(en)
            if len(a) != len(e):
                e = _split_words(en, len(a))
            pairs = list(zip(a, e))
        weights = [len(a or "") + len(e or "") for a, e in pairs]
        total = sum(weights) or 1
        t = t0
        for (a, e), w in zip(pairs, weights):
            span = dur * w / total
            lines = []
            if a:
                lines.append(_wrap(a, MAX_CHARS_ETHIOPIC))
            if e:
                # English under the Amharic: 80 % size, slightly dimmer (libass override tags)
                lines.append(("{\\fscx80\\fscy80\\1c&HC8D2DC&}" if a else "") + _wrap(e, MAX_CHARS + 8 if a else MAX_CHARS))
            cues.append((t, t + span, "\n".join(lines)))
            t += span
    with open(path, "w", encoding="utf-8") as f:
        for i, (a, b, txt) in enumerate(cues, 1):
            f.write(f"{i}\n{_ts(a)} --> {_ts(b)}\n{txt}\n\n")
    return path
