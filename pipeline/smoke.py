"""Smoke test: one tiny call per hosted provider, each logged to runs.jsonl with latency.
Tells you in a minute which keys, model IDs and quotas work."""
from __future__ import annotations

from .common import CallFailed, image_filter_risks, load_storyboard, out_dir, say
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
    for w in image_filter_risks(sb):
        say("smoke", f"!! image safety filter may flag this: {w}")
    checks = [
        ("gemini text", lambda: gemini_text("Reply with the single word: ready", model=sb["models"]["text"], stage="smoke")),
        ("gemini tts", lambda: gemini_tts("ሰላም፣ እንኳን ደህና መጡ።" if sb["language"]["narration"] == "am" else "Hello.",
                                          model=sb["models"]["tts"], voice=sb.get("voice", {}).get("name", "Kore"),
                                          style=None, out_wav=d / "tts.wav", stage="smoke")),
        ("cloudflare image", lambda: cf_image("a tortoise walking on a red dirt path, " + sb["style"]["block"],
                                              model=sb["models"]["image"], seed=1, out_png=d / "image.png",
                                              width=512, height=512, stage="smoke")),
        ("cloudflare image_alt", lambda: cf_image("a tortoise walking on a red dirt path",
                                                  model=sb["models"]["image_alt"], seed=1, out_png=d / "image_alt.png",
                                                  width=512, height=512, stage="smoke")),
    ]
    for name, fn in checks:
        try:
            fn()
            results[name] = "OK"
        except (CallFailed, SystemExit, Exception) as e:
            results[name] = f"FAILED: {str(e)[:300]}"
            if name == "cloudflare image" and "3030" in str(e):
                results[name] += "\n" + " " * 25 + _diagnose_flag(sb, d)
    print("\n=== smoke test ===")
    for k, v in results.items():
        print(f"  {k:22} {v}")
    print("Latency of each call is in runs.jsonl (stage = smoke). Outputs in outputs/smoke/.")


def _diagnose_flag(sb: dict, d) -> str:
    """FLUX.2 output was flagged on every seed. One extra call without the style block tells
    whether the style text is the trigger or the model/filter itself."""
    try:
        cf_image("a tortoise walking on a red dirt path", model=sb["models"]["image"], seed=1,
                 out_png=d / "image_bare.png", width=512, height=512, stage="smoke")
        return ("-> the SAME prompt WITHOUT style.block passed, so a phrase in style.block is the trigger. "
                "Reword style.block in storyboard.json (see FAILURES.md F05).")
    except Exception as e:
        if "3030" in str(e):
            return ("-> flagged even without style.block: the filter is over-blocking this model right now. "
                    "Keyframes will fall back to models.image_alt; or try again later.")
        return f"-> diagnostic call failed: {str(e)[:150]}"
