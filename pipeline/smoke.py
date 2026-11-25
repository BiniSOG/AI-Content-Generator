"""Smoke test: one tiny call per hosted provider, each logged to runs.jsonl with latency.
Tells you in a minute which keys, model IDs and quotas work."""
from __future__ import annotations

from .common import CallFailed, load_storyboard, out_dir, say
from .providers import cf_image, gemini_list_models, gemini_text, gemini_tts


def run() -> None:
    sb = load_storyboard()
    d = out_dir("smoke")
    results = {}
    try:
        names = gemini_list_models()
        flash = [n for n in names if "flash" in n]
        say("smoke", f"Gemini key OK. Flash-family models visible to your key: {', '.join(flash[:25])}")
        for role in ("text", "tts"):
            if sb["models"][role] not in names:
                say("smoke", f"!! models.{role} = '{sb['models'][role]}' is NOT in that list. Edit storyboard.json.")
    except Exception as e:
        say("smoke", f"!! could not list Gemini models: {e}")
    checks = [
        ("gemini text", lambda: gemini_text("Reply with the single word: ready", model=sb["models"]["text"], stage="smoke")),
        ("gemini tts", lambda: gemini_tts("ሰላም፣ እንኳን ደህና መጡ።" if sb["language"]["narration"] == "am" else "Hello.",
                                          model=sb["models"]["tts"], voice=sb.get("voice", {}).get("name", "Kore"),
                                          style=None, out_wav=d / "tts.wav", stage="smoke")),
        ("cloudflare image", lambda: cf_image("a clay coffee pot on a wooden table, " + sb["style"]["block"],
                                              model=sb["models"]["image"], seed=1, out_png=d / "image.png",
                                              width=512, height=512, stage="smoke")),
        ("cloudflare image_alt", lambda: cf_image("a clay coffee pot on a wooden table",
                                                  model=sb["models"]["image_alt"], seed=1, out_png=d / "image_alt.png",
                                                  width=512, height=512, stage="smoke")),
    ]
    for name, fn in checks:
        try:
            fn()
            results[name] = "OK"
        except (CallFailed, SystemExit, Exception) as e:
            results[name] = f"FAILED: {str(e)[:300]}"
    print("\n=== smoke test ===")
    for k, v in results.items():
        print(f"  {k:22} {v}")
    print("Latency of each call is in runs.jsonl (stage = smoke). Outputs in outputs/smoke/.")
