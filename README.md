# The Smoke Still Finds Me: an AI short film and the pipeline that makes it

This repo holds a 60–90 second short film and the code that makes it. The film is narrated in Amharic, with English subtitles, an original ducked score and an AI end card, exported in 16:9 and 9:16. **One file, `storyboard.json`, is the contract between every stage.** Each stage reads it, writes its outputs, and caches them by a hash of its inputs. Changing one shot regenerates only that shot.

```
storyboard.json ─► validate ─► script ─► narration ─► keyframes ─► shots ─► music ─► assemble ─► film_16x9.mp4
   (contract)     (schema)   (Gemini)  (Gemini TTS)  (FLUX/CF)  (Wan/FFmpeg) (ACE-Step) (FFmpeg)    film_9x16.mp4
```

## Quick start (from a clean clone)

You need **Python 3.10+**, **FFmpeg** on your PATH, and free accounts with Google AI Studio and Cloudflare. Kaggle is optional and only needed for the GPU stages.

```bash
git clone https://github.com/BiniSOG/AI-Content-Generator.git
```
```bash
cd AI-Content-Generator
```
```bash
pip install -r requirements.txt
```
```bash
cp .env.example .env
```
Then put your keys in `.env`.
```bash
python run.py smoke
```
This makes one call per provider and logs each to `runs.jsonl`.
```bash
python run.py film
```
This is the whole pipeline in **one command**. `make film` does the same thing.

The outputs land in `outputs/final/film_16x9.mp4`, `outputs/final/film_9x16.mp4` and `outputs/final/subtitles_en.srt`.

To install FFmpeg on Windows: `winget install Gyan.FFmpeg`. On macOS: `brew install ffmpeg`. On Ubuntu: `sudo apt install ffmpeg`.

## Commands

| Command | What it does |
|---|---|
| `python run.py validate` | Validates `storyboard.json` against `schema/storyboard.schema.json` plus the cross-field rules. This also runs automatically before every stage. |
| `python run.py smoke` | Makes one tiny call to each provider and checks that the model IDs exist for your key. |
| `python run.py radio-cut` | Narration over placeholder or chosen music on black, with subtitles. This is the first prototype. |
| `python run.py keyframes --ref-only` | Generates the character reference sheets only, so you can approve them before any keyframes. |
| `python run.py <stage> [--only s03,s04]` | Runs one stage: `script`, `narration`, `keyframes`, `shots`, `music` or `assemble`. |
| `python run.py status` | Shows per shot whether the narration is cached, whether the keyframe and Wan clip exist, and the reason for the shot. |
| `python run.py kaggle-pack` | Zips the inputs for the Kaggle GPU notebook. See [kaggle/README.md](kaggle/README.md). |
| `python run.py experiments [--only e07]` | Runs the controlled experiments recorded in EXPERIMENTS.md. |
| `python run.py costs` | Rebuilds the measured table in COSTS.md from `runs.jsonl`. |
| `python tests/test_offline.py` | An offline end-to-end test with faked model calls that also checks caching. |

## Changing one shot

Edit one `narration.en` line or one `image_prompt` in `storyboard.json`, then run:

```bash
python run.py film
```

The run summary lists what was regenerated, for example `narration s04`. `runs.jsonl` gains exactly one new model-call line per regenerated item. Everything else is a cache hit.

## What it costs

The film costs **$0** on free tiers: the Gemini API free tier, Cloudflare Workers AI's daily allowance and Kaggle's weekly GPU quota. Measured latency, GPU minutes and the list-price equivalent are in [COSTS.md](COSTS.md). A typical full run is about 40 API calls plus about 20–60 Kaggle GPU minutes.

## Repository map

| Path | Contents |
|---|---|
| `storyboard.json` | Shots, durations, prompts, seeds, the reason for each shot, narration, music cues, model IDs |
| `schema/` | JSON Schema for the storyboard |
| `pipeline/` | One module per stage, plus `common.py` (caching, retries, logging) and `providers.py` (API clients) |
| `kaggle/` | GPU stages for ACE-Step 1.5 and Wan 2.2, which use the same storyboard and log format |
| `runs.jsonl` | One line per model call: model, params, seed, latency, status, attempts, cost |
| `outputs/` | Generated references, keyframes, narration, shots, music, experiments and final films |
| [DESIGN.md](DESIGN.md) | Audience, intent, both user tests and what changed |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Stages, contracts, caching, failure handling |
| [EXPERIMENTS.md](EXPERIMENTS.md) | Entries in the form hypothesis → change → result |
| [FAILURES.md](FAILURES.md) | What broke, what was tried, what fixed it |
| [COSTS.md](COSTS.md) | Measured latency and GPU minutes per stage, plus the list-price equivalent |
| [ETHICS.md](ETHICS.md) | Consent, licences, labelling plan |

## Secrets

Keys live only in `.env`, which is gitignored. `.env.example` lists the names. Nothing in `runs.jsonl` contains a key.
