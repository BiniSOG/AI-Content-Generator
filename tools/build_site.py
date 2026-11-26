"""Build a static showcase website for the finished film into site/ (ready for Vercel).

    python tools/build_site.py

Reads storyboard.json and the pipeline outputs:
  outputs/final/film_16x9.mp4, outputs/final/film_9x16.mp4   (the films)
  outputs/keyframes/sNN.png                                    (one picture per shot)
and writes site/index.html plus site/media/ (films, compressed shot pictures).
No build step, no server: Vercel serves the folder as plain files.
"""
from __future__ import annotations

import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.common import OUT, load_storyboard  # noqa: E402

SITE = ROOT / "site"
MEDIA = SITE / "media"
GITHUB_FILE_LIMIT_MB = 95  # GitHub refuses files over 100 MB


def esc(s: str) -> str:
    return html.escape(str(s or ""), quote=True)


def copy_film(name: str) -> str | None:
    src = OUT / "final" / name
    if not src.exists():
        print(f"  missing {src.relative_to(ROOT)} (run: python run.py film) - the page will say so")
        return None
    mb = src.stat().st_size / 1e6
    if mb > GITHUB_FILE_LIMIT_MB:
        sys.exit(f"{name} is {mb:.0f} MB; GitHub only accepts files under 100 MB. Re-export with a higher crf.")
    shutil.copyfile(src, MEDIA / name)
    print(f"  film  {name} ({mb:.1f} MB)")
    return f"media/{name}"


def shot_picture(sid: str) -> str | None:
    from PIL import Image
    src = OUT / "keyframes" / f"{sid}.png"
    if not src.exists():
        return None
    im = Image.open(src).convert("RGB")
    im.thumbnail((720, 720))
    out = MEDIA / f"{sid}.jpg"
    im.save(out, "JPEG", quality=82, optimize=True, progressive=True)
    return f"media/{sid}.jpg"


def build() -> None:
    sb = load_storyboard()
    if SITE.exists():
        shutil.rmtree(SITE)
    MEDIA.mkdir(parents=True)
    print("building site/ ...")
    wide = copy_film("film_16x9.mp4")
    tall = copy_film("film_9x16.mp4")
    pics = {s["id"]: shot_picture(s["id"]) for s in sb["shots"]}
    poster = next((p for p in pics.values() if p), None)
    print(f"  shot pictures: {sum(1 for p in pics.values() if p)}/{len(pics)}")

    lang = sb["language"].get("narration_name", sb["language"]["narration"])
    m = sb["models"]
    shots_html = []
    for i, s in enumerate(sb["shots"], 1):
        n = s["narration"]
        pic = pics[s["id"]]
        img = (f'<img src="{pic}" alt="{esc(s.get("beat", s["id"]))}" loading="lazy" width="720" height="720">'
               if pic else '<div class="noimg">picture not generated yet</div>')
        shots_html.append(f"""
      <article class="shot">
        {img}
        <div class="shot-text">
          <p class="shot-meta">{i:02d} · {esc(s.get("beat", ""))} · {esc(s["shot_size"].replace("_", " "))}</p>
          <p class="am" lang="am">{esc(n.get("spoken", ""))}</p>
          <p class="en">{esc(n["en"])}</p>
        </div>
      </article>""")

    def player(src, cls, label):
        if not src:
            return f'<div class="player {cls} missing">{label} version not exported yet</div>'
        return (f'<video class="player {cls}" controls playsinline preload="metadata" '
                f'{"poster=" + chr(34) + poster + chr(34) if poster else ""}><source src="{src}" type="video/mp4"></video>')

    credits = "".join(f"<li>{esc(c)}</li>" for c in sb["end_card"].get("credits", []))
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(sb["title"])}</title>
<meta name="description" content="{esc(sb["logline"])}">
<meta property="og:title" content="{esc(sb["title"])}">
<meta property="og:description" content="{esc(sb["logline"])}">
{f'<meta property="og:image" content="{poster}">' if poster else ""}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Ethiopic:wght@400;600&family=Noto+Serif:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #f6f1e9; --surface: #fffaf3; --ink: #2a1d14; --muted: #6b5a4c; --line: #e4d8c8; --accent: #9a4a22;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #17110c; --surface: #211811; --ink: #f1e6d8; --muted: #b9a693; --line: #3a2c21; --accent: #e08a55; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink);
         font: 17px/1.6 "Noto Serif", Georgia, serif; }}
  .wrap {{ max-width: 1080px; margin: 0 auto; padding: 0 16px; }}
  header {{ padding: 56px 0 24px; text-align: center; }}
  .proverb {{ font-family: "Noto Sans Ethiopic", sans-serif; color: var(--accent); font-size: 1.15rem; margin: 0 0 8px; }}
  h1 {{ font-size: clamp(2rem, 6vw, 3.4rem); line-height: 1.1; margin: 0 0 12px; letter-spacing: -0.01em; }}
  .logline {{ color: var(--muted); max-width: 680px; margin: 0 auto; }}
  .tabs {{ display: flex; gap: 8px; justify-content: center; margin: 28px 0 16px; }}
  .tabs button {{ font: inherit; font-size: .95rem; padding: 8px 16px; border-radius: 999px; cursor: pointer;
                 border: 1px solid var(--line); background: var(--surface); color: var(--ink); }}
  .tabs button[aria-pressed="true"] {{ background: var(--ink); color: var(--bg); border-color: var(--ink); }}
  .stage {{ display: flex; justify-content: center; }}
  .player {{ display: block; width: 100%; background: #000; border-radius: 12px; }}
  .player.wide {{ max-width: 1000px; aspect-ratio: 16 / 9; }}
  .player.tall {{ max-width: 380px; aspect-ratio: 9 / 16; }}
  .player.missing {{ display: grid; place-items: center; color: #ddd; font-size: .95rem; }}
  .hidden {{ display: none !important; }}
  .note {{ text-align: center; color: var(--muted); font-size: .9rem; margin: 10px 0 0; }}
  h2 {{ font-size: 1.6rem; margin: 64px 0 20px; }}
  .shots {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px; }}
  .shot {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px; overflow: hidden; }}
  .shot img, .noimg {{ display: block; width: 100%; height: auto; aspect-ratio: 1; object-fit: cover; }}
  .noimg {{ display: grid; place-items: center; color: var(--muted); font-size: .9rem; background: var(--line); }}
  .shot-text {{ padding: 14px 16px 16px; }}
  .shot-meta {{ margin: 0 0 8px; color: var(--muted); font-size: .8rem; text-transform: uppercase; letter-spacing: .06em; }}
  .am {{ font-family: "Noto Sans Ethiopic", sans-serif; margin: 0 0 6px; font-size: 1.05rem; }}
  .en {{ margin: 0; color: var(--muted); font-size: .95rem; }}
  .made {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; }}
  .card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 18px 20px; }}
  .card h3 {{ margin: 0 0 8px; font-size: 1.05rem; }}
  .card p, .card ul {{ margin: 0; color: var(--muted); font-size: .95rem; }}
  .card ul {{ padding-left: 18px; }}
  footer {{ margin: 64px 0 40px; padding-top: 20px; border-top: 1px solid var(--line); color: var(--muted);
           font-size: .9rem; text-align: center; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="proverb" lang="am">ድር ቢያብር አንበሳ ያስር</p>
    <h1>{esc(sb["title"])}</h1>
    <p class="logline">{esc(sb["logline"])}</p>
  </header>

  <div class="tabs" role="group" aria-label="Film format">
    <button type="button" data-show="wide" aria-pressed="true">Horizontal 16:9</button>
    <button type="button" data-show="tall" aria-pressed="false">Vertical 9:16</button>
  </div>
  <div class="stage">
    {player(wide, "wide", "Horizontal")}
    {player(tall, "tall hidden", "Vertical")}
  </div>
  <p class="note">Narrated in {esc(lang)}, with English subtitles. Sound on.</p>

  <h2>The story, shot by shot</h2>
  <section class="shots">{"".join(shots_html)}
  </section>

  <h2>How it was made</h2>
  <section class="made">
    <div class="card"><h3>One storyboard</h3><p>Every shot, line, seed and model is written in a single storyboard
      file. Each stage reads it and caches its output, so changing one line regenerates only that shot.</p></div>
    <div class="card"><h3>Pictures</h3><p>{esc(m.get("image"))} on Cloudflare Workers AI, with reference images
      to keep the father and his sons consistent, and an automatic check that counts the people in each picture.</p></div>
    <div class="card"><h3>Voice</h3><p>Gemini text-to-speech ({esc(m.get("tts"))}) reading hand-written {esc(lang)}
      lines, each one checked by listening for anything that is not {esc(lang)}.</p></div>
    <div class="card"><h3>Motion and sound</h3><p>Wan 2.2 for a few hero shots, slow camera moves elsewhere, an
      original score, and FFmpeg for the mix, the subtitles and both exports.</p></div>
    <div class="card"><h3>Credits</h3><ul>{credits}</ul></div>
  </section>

  <footer>Made with AI. All characters are fictional. A retelling of the traditional fable of the bundle of sticks.</footer>
</div>
<script>
  document.querySelectorAll(".tabs button").forEach(function (b) {{
    b.addEventListener("click", function () {{
      document.querySelectorAll(".tabs button").forEach(function (x) {{ x.setAttribute("aria-pressed", x === b); }});
      document.querySelectorAll(".player").forEach(function (p) {{
        var show = p.classList.contains(b.dataset.show);
        p.classList.toggle("hidden", !show);
        if (!show && p.pause) p.pause();
      }});
    }});
  }});
</script>
</body>
</html>
"""
    (SITE / "index.html").write_text(page, encoding="utf-8")
    (SITE / "vercel.json").write_text(json.dumps({
        "cleanUrls": True,
        "headers": [{"source": "/media/(.*)", "headers": [
            {"key": "Cache-Control", "value": "public, max-age=31536000, immutable"}]}]}, indent=2) + "\n")
    total = sum(f.stat().st_size for f in SITE.rglob("*") if f.is_file()) / 1e6
    print(f"done: site/ ({total:.1f} MB). Open site/index.html in a browser to check it.")


if __name__ == "__main__":
    build()
