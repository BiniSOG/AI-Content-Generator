"""Fill narration.spoken with hand-written Amharic and lock it (the script stage then skips
the translation API for these lines). Written by hand for the bundle-of-sticks story
(storyboard.json already holds them, locked); run this to restore them after editing.

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
    "s01": ("In a village in the highlands, an old farmer, Abba Tesfaye, lay sick in his bed.",
            "በደጋው መንደር ውስጥ፣ አባ ተስፋዬ የሚባሉ አንድ አዛውንት ገበሬ ታመው በአልጋቸው ላይ ተኝተው ነበር።"),
    "s02": ("He knew his time was near. And one thing troubled him more than his illness.",
            "ጊዜያቸው እንደቀረበ ያውቁ ነበር። ከሕመማቸው በላይ ግን አንድ ነገር ያሳስባቸው ነበር።"),
    "s03": ("His five sons were strong, but they always quarrelled: over the land, over the oxen, over everything.",
            "አምስቱ ልጆቻቸው ብርቱዎች ነበሩ፤ ግን ሁልጊዜ ይጣሉ ነበር፦ በመሬቱ፣ በበሬዎቹ፣ በሁሉም ነገር።"),
    "s04": ("So he called all five of his sons to his bedside.",
            "ስለዚህ አምስቱንም ልጆቻቸውን ወደ አልጋቸው አጠገብ ጠሯቸው።"),
    "s05": ("He gave them a bundle of sticks, tied tightly together. 'Break it,' he said.",
            "በጥብቅ የታሰረ አንድ እስር እንጨት ሰጧቸው። «ስበሩት» አሉ።"),
    "s06": ("One by one, each son tried with all his strength. No one could break it.",
            "አንድ በአንድ እያንዳንዱ ልጅ በሙሉ ኃይሉ ሞከረ። ማንም ሊሰብረው አልቻለም።"),
    "s07": ("Then he untied the bundle and gave each son a single stick. 'Now break yours.'",
            "ከዚያም እስሩን ፈትተው ለእያንዳንዱ ልጅ አንድ አንድ እንጨት ሰጡ። «አሁን የራሳችሁን ስበሩ።»"),
    "s08": ("Each stick snapped easily.",
            "እያንዳንዱ እንጨት በቀላሉ ተሰበረ።"),
    "s09": ("'My sons,' he said, 'alone, you are like one stick. Together, no one can break you.'",
            "«ልጆቼ» አሉ፤ «ብቻችሁን ስትሆኑ እንደ አንድ እንጨት ናችሁ። አንድ ስትሆኑ ግን ማንም ሊሰብራችሁ አይችልም።»"),
    "s10": ("From that day, the brothers worked as one. As the elders say: when spider webs unite, they can tie up a lion.",
            "ከዚያ ቀን ጀምሮ ወንድማማቾቹ እንደ አንድ ሰው ሠሩ። አበው እንዳሉት፦ ድር ቢያብር አንበሳ ያስር።"),
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
