"""Stage 1 - script: fills narration.spoken (the line in the narration language) from the
English source line. Cached per line: only lines whose English text changed are re-translated.
A human-corrected line is protected with "locked": true."""
from __future__ import annotations

from .common import cache_key, load_storyboard, save_storyboard, say
from .providers import gemini_text

STAGE = "script"

PROMPT = """You are translating narration for a short film into {lang}.
Translate the line below into natural, spoken {lang} that a native speaker would say aloud.
Keep it short and easy to speak. Keep names (Etenesh, Liya) and the words jebena and abol as they are.
Return ONLY the translated line, with no quotes, notes or transliteration.

Full script for context:
{context}

Line to translate:
{line}"""


def run(sb: dict | None = None, only: set[str] | None = None) -> list[str]:
    sb = sb or load_storyboard()
    lang = sb["language"]["narration"]
    lang_name = sb["language"].get("narration_name", lang)
    model = sb["models"]["text"]
    context = "\n".join(s["narration"]["en"] for s in sb["shots"])
    changed = []
    for s in sb["shots"]:
        if only and s["id"] not in only:
            continue
        n = s["narration"]
        if lang == "en":
            if n.get("spoken") != n["en"]:
                n["spoken"] = n["en"]
                changed.append(s["id"])
            continue
        key = cache_key(n["en"], lang, model)
        if n.get("locked") or (n.get("spoken") and n.get("spoken_source_hash") == key):
            continue
        say(STAGE, f"{s['id']}: translating to {lang_name}")
        n["spoken"] = gemini_text(PROMPT.format(lang=lang_name, context=context, line=n["en"]),
                                  model=model, stage=STAGE, shot=s["id"], cache_key=key)
        n["spoken_source_hash"] = key
        changed.append(s["id"])
        save_storyboard(sb)  # save as we go so a crash loses nothing
    say(STAGE, f"{len(changed)} line(s) translated" + (f": {', '.join(changed)}" if changed else " (all cached)"))
    return changed
