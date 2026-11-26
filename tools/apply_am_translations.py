"""Fill narration.spoken with hand-written Amharic and lock it (the script stage then skips
the translation API for these lines). Written by hand for the tortoise-and-rabbit story
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
    "s01": ("Long ago, in the green hills, there lived a rabbit who was very fast, and a tortoise who was very slow.",
            "ድሮ ድሮ፣ በአረንጓዴዎቹ ኮረብቶች ላይ በጣም ፈጣን ጥንቸልና በጣም ቀርፋፋ ኤሊ ይኖሩ ነበር።"),
    "s02": ("The rabbit loved to laugh at the others. 'No one in these hills can beat me,' he said.",
            "ጥንቸሉ በሌሎች መሳቅ ይወድ ነበር። «በእነዚህ ኮረብቶች ውስጥ ማንም ሊያሸንፈኝ አይችልም» አለ።"),
    "s03": ("The tortoise looked up and said quietly, 'Then let us race, to the big warka tree.'",
            "ኤሊዋ ቀና ብላ በለሆሳስ «እንግዲያው እስከ ትልቁ የዋርካ ዛፍ ድረስ እንሽቀዳደም» አለች።"),
    "s04": ("All the animals came to watch. The rabbit laughed. And the race began.",
            "እንስሳት ሁሉ ሊመለከቱ መጡ። ጥንቸሉ ሳቀ። ውድድሩም ተጀመረ።"),
    "s05": ("In a moment, the rabbit was far ahead. He looked back, and the tortoise was only a small dot.",
            "ጥንቸሉ በቅጽበት በጣም ቀደመ። ወደ ኋላ ቢመለከት ኤሊዋ ትንሽ ነጥብ ብቻ ሆና ታየች።"),
    "s06": ("'I have plenty of time,' he thought. He lay down in the shade beside the road, and fell asleep.",
            "«ብዙ ጊዜ አለኝ» ብሎ አሰበ። ከመንገዱ ዳር ጥላ ስር ተኝቶ እንቅልፍ ወሰደው።"),
    "s07": ("The tortoise did not stop. One step, then another, all through the hot afternoon.",
            "ኤሊዋ አላቆመችም። አንድ እርምጃ፣ ከዚያም ሌላ፣ በሞቃቱ ከሰዓት በኋላ ሁሉ።"),
    "s08": ("Slowly, quietly, she walked past the sleeping rabbit.",
            "ቀስ ብላ፣ በጸጥታ፣ ከተኛው ጥንቸል አጠገብ አልፋ ሄደች።"),
    "s09": ("When the rabbit woke up, he ran as fast as he could. But the tortoise was already at the tree.",
            "ጥንቸሉ ሲነቃ የቻለውን ያህል ሮጠ። ኤሊዋ ግን ቀድማ ዛፉ ጋ ደርሳ ነበር።"),
    "s10": ("Slow and steady wins the race. As the elders say: little by little, even an egg learns to walk.",
            "ቀስ ብሎ የማያቋርጥ ያሸንፋል። አበው እንዳሉት፦ ቀስ በቀስ እንቁላል በእግሩ ይሄዳል።"),
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
