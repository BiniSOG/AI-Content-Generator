"""Fill narration.spoken with hand-written Amharic and lock it (the script stage then skips
the translation API for these lines). Used because the Gemini text models returned HTTP 503
for every request on 2026-11-25 (FAILURES.md F03).

Only applies a line if the shot's English text still matches the one it was translated from,
so it never overwrites a line you have since changed. Have a native speaker check every line.

    python tools/apply_am_translations.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SB = ROOT / "storyboard.json"

AM = {
    "s01": ("In my grandmother's village, the day began before the sun.",
            "በአያቴ መንደር ቀኑ የሚጀምረው ከፀሐይ በፊት ነበር።"),
    "s02": ("Every morning, Etenesh roasted coffee over charcoal, the way her mother taught her.",
            "በየማለዳው እቴነሽ እናቷ እንዳስተማረቻት ቡናውን በከሰል እሳት ላይ ትቆላ ነበር።"),
    "s03": ("She said you could hear when the beans were ready. They crackle, like they are laughing.",
            "ቡናው ሲበስል ይሰማል ትል ነበር። እንደሚስቅ ይንጣጣል።"),
    "s04": ("She carried the smoke around the room, so everyone could greet it.",
            "ሁሉም ሰው ጭሱን እንዲቀበለው በቤቱ ውስጥ ታዞረው ነበር።"),
    "s05": ("I watched her hands. Hands that had done this ten thousand times.",
            "እጆቿን እመለከት ነበር። ይህንን አሥር ሺህ ጊዜ የሠሩ እጆች።"),
    "s06": ("The first cup is called abol. Strong, like the morning.",
            "የመጀመሪያው ስኒ አቦል ይባላል። እንደ ማለዳው ጠንካራ።"),
    "s07": ("One day she put the jebena in my hands. Slowly, she said. Coffee is not about the coffee.",
            "አንድ ቀን ጀበናውን በእጄ ሰጠችኝ። ቀስ ብለሽ አለችኝ። ቡና ስለ ቡናው አይደለም።"),
    "s08": ("It is about who comes to sit with you.",
            "አብሮሽ ሊቀመጥ ስለሚመጣው ሰው ነው።"),
    "s09": ("Now I roast coffee far from home. And every morning, the smoke still finds me. So does she.",
            "አሁን ከቤቴ ርቄ ቡና እቆላለሁ። በየማለዳውም ጭሱ አሁንም ያገኘኛል። እሷም እንደዚሁ።"),
}

sb = json.loads(SB.read_text(encoding="utf-8"))
applied, skipped = [], []
for s in sb["shots"]:
    if s["id"] not in AM:
        continue
    en, am = AM[s["id"]]
    n = s["narration"]
    if n["en"].strip() != en:
        skipped.append(s["id"])
        continue
    n["spoken"] = am
    n["locked"] = True
    n.pop("spoken_source_hash", None)
    applied.append(s["id"])

SB.write_text(json.dumps(sb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"applied + locked: {', '.join(applied) or '-'}")
if skipped:
    print(f"skipped (you changed the English line, so translate these yourself and add \"locked\": true): {', '.join(skipped)}")
print("Next: python run.py radio-cut   (have a native speaker check every Amharic line)")
sys.exit(0)
