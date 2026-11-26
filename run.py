#!/usr/bin/env python3
"""One entry point for the whole pipeline.

  python run.py film                 # everything: validate -> script -> narration -> keyframes -> shots -> music -> assemble
  python run.py radio-cut            # validate -> script -> narration -> music(placeholder ok) -> radio cut
  python run.py <stage> [--only s03,s04]
  python run.py status               # what is cached / what would regenerate

Stages: validate, smoke, models, script, narration, keyframes [--ref-only], shots, music, assemble,
        experiments [--only e01], costs, kaggle-pack
Every stage reads storyboard.json; each output is cached by a hash of its inputs, so a re-run
only regenerates what changed. Every model call is logged to runs.jsonl."""
from __future__ import annotations

import argparse
import sys
import time

from pipeline import common


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command")
    ap.add_argument("--only", help="comma-separated shot ids (or experiment ids)")
    ap.add_argument("--ref-only", action="store_true", help="keyframes: only the character reference sheets")
    a = ap.parse_args()
    only = set(a.only.split(",")) if a.only else None
    c = a.command
    common.load_env()

    if c == "validate":
        sb = common.load_storyboard()
        print("storyboard.json is valid")
        for w in common.image_filter_risks(sb):
            print(f"  warning (image safety filter may flag this): {w}")
        return
    if c == "smoke":
        from pipeline import smoke
        return smoke.run()
    if c == "models":
        from pipeline.providers import gemini_list_models
        print("\n".join(gemini_list_models()))
        return
    if c == "costs":
        from pipeline import costs
        return costs.run()
    if c == "experiments":
        from pipeline import experiments
        return experiments.run(only)
    if c == "kaggle-pack":
        return kaggle_pack()
    if c == "status":
        return status()

    from pipeline import assemble, keyframes, music, narration, script, shots
    sb = common.load_storyboard()
    print(f"[run] {common.RUN_ID}  storyboard valid ({len(sb['shots'])} shots)")
    t0 = time.time()
    summary = {}
    if c == "script":
        summary["script"] = script.run(sb, only)
    elif c == "narration":
        summary["narration"] = narration.run(sb, only)
    elif c == "keyframes":
        summary["keyframes"] = keyframes.run(sb, only, ref_only=a.ref_only)
    elif c == "shots":
        summary["shots"] = shots.run(sb, only)
    elif c == "music":
        music.run(sb)
    elif c == "assemble":
        summary["assemble"] = assemble.run(sb)
    elif c == "radio-cut":
        summary["script"] = script.run(sb, only)
        summary["narration"] = narration.run(sb, only)
        music.run(sb)
        assemble.radio_cut(sb)
    elif c == "film":
        summary["script"] = script.run(sb, only)
        summary["narration"] = narration.run(sb, only)
        summary["keyframes"] = keyframes.run(sb, only)
        summary["shots"] = shots.run(sb, only)
        music.run(sb)
        summary["assemble"] = assemble.run(sb)
    else:
        sys.exit(f"unknown command {c}. See: python run.py -h")
    print(f"\n[run] done in {time.time()-t0:.1f}s. Regenerated:")
    for k, v in summary.items():
        print(f"   {k:10} {', '.join(v) if v else '-'}")


def status() -> None:
    import json
    from pipeline.common import OUT, cache_key, load_storyboard
    from pipeline.keyframes import shot_prompt
    sb = load_storyboard()
    kf = json.loads((OUT / "keyframes" / "manifest.json").read_text()) if (OUT / "keyframes" / "manifest.json").exists() else {}
    na = json.loads((OUT / "narration" / "manifest.json").read_text()) if (OUT / "narration" / "manifest.json").exists() else {}
    model, voice, style = sb["models"]["tts"], sb.get("voice", {}).get("name", "Kore"), sb.get("voice", {}).get("style")
    print(f"{'shot':5} {'narration':12} {'keyframe':10} {'wan clip':9} reason")
    for s in sb["shots"]:
        text = s["narration"].get("spoken") or s["narration"]["en"]
        n_ok = na.get(s["id"], {}).get("key") == cache_key(text, voice, style, model)
        k_ok = s["id"] in kf and not kf[s["id"]].get("stale")
        clip = (OUT / "kaggle" / "clips" / f"{s['id']}.mp4").exists()
        print(f"{s['id']:5} {'cached' if n_ok else 'WILL REGEN':12} {'yes' if k_ok else 'missing':10} "
              f"{'yes' if clip else ('-' if s['motion']['mode']!='wan' else 'not yet'):9} {s['reason'][:60]}")


def kaggle_pack() -> None:
    """Zip what the Kaggle notebook needs: storyboard + keyframes of the wan shots + the kaggle scripts."""
    import zipfile
    from pipeline.common import OUT, ROOT, load_storyboard
    sb = load_storyboard()
    z = OUT / "kaggle_input.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.write(ROOT / "storyboard.json", "storyboard.json")
        for p in (ROOT / "kaggle").glob("*.py"):
            f.write(p, f"kaggle/{p.name}")
        for s in sb["shots"]:
            kf = OUT / "keyframes" / f"{s['id']}.png"
            if s["motion"]["mode"] == "wan" and kf.exists():
                f.write(kf, f"keyframes/{s['id']}.png")
    print(f"wrote {z}. Upload it to Kaggle as a Dataset named 'film-input' (see kaggle/README.md).")


if __name__ == "__main__":
    main()
