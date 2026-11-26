# Architecture

## Principle

`storyboard.json` is the **only** contract. No stage hands data directly to another. Each stage reads the storyboard and the stable files earlier stages left in `outputs/`, and writes its own. That gives three properties:

- **Any stage can be rerun alone**, for example `python run.py shots --only s03`.
- **A change is local.** Each output is named by a hash of exactly the inputs that stage uses, so editing one line regenerates only what depends on it.
- **Runs are reproducible and explainable.** Prompts, seeds and model IDs live in the storyboard, not in the code.

## Stages

| # | Stage | Reads (storyboard fields + files) | Writes | Model | Runs on |
|---|---|---|---|---|---|
| 0 | validate | whole storyboard, `schema/`, ETHICS.md (consent markers) | nothing; it exits non-zero on error | none | local |
| 1 | script | `shots[].narration.en`, `language`, `models.text` | `shots[].narration.spoken` + `spoken_source_hash` (back into the storyboard) | Gemini Flash | API |
| 2 | narration | `narration.spoken`, `voice`, `models.tts` | `outputs/narration/sNN-<key>.wav`, `sNN.wav`, `manifest.json` (measured durations) | Gemini TTS | API |
| 3 | keyframes | `characters[]`, `style`, `shots[].image_prompt/seed/characters` | `outputs/refs/<char>.png`, `outputs/keyframes/sNN-<key>.png`, `manifest.json` | FLUX.2 klein, falling back to FLUX.1 schnell | API |
| 4a | wan (GPU) | `shots[].motion` (`mode == wan`), keyframes | `outputs/kaggle/clips/sNN.mp4`, `runs_kaggle.jsonl` | Wan 2.2 TI2V-5B | Kaggle |
| 4b | shots | keyframes, Wan clips, `motion.kenburns`, narration durations | `outputs/shots/{16x9,9x16}/sNN-<key>.mp4` | FFmpeg | local |
| 5a | score (GPU) | `music.caption/bpm/key/duration_s/seeds` | `outputs/kaggle/music/cand_N.wav`, `runs_kaggle.jsonl` | ACE-Step 1.5 | Kaggle |
| 5b | music | `music.chosen`, candidates | `outputs/music/score.wav` (pre-levelled to −20 LUFS) | FFmpeg | local |
| 6 | assemble | everything above, `end_card`, `output` | `outputs/final/film_16x9.mp4`, `film_9x16.mp4`, `subtitles_en.srt`, `timeline.json` | FFmpeg | local |

**Picture is cut to the voice.** Each shot's length is `max(duration_s, narration length + lead-in + 0.7 s)`. Narration therefore has to be generated before shots, and timing comes from the real TTS output, not from estimates.

**Both aspect ratios come from one square keyframe.** Every keyframe is 1024×1024 with the subject centred, as the style block requests. The shots stage centre-crops it to 16:9 or 9:16 before the Ken Burns move. That is why one set of images serves both exports.

## The contract (schema)

`schema/storyboard.schema.json` (JSON Schema 2020-12) enforces the following:

- 8–12 shots
- shot ids of the form `sNN`
- a `reason` on every shot
- an allowed shot size
- a duration between 3 and 14 s
- a motion mode of `kenburns` or `wan`
- an end card text that contains "AI"
- `voice.cloned` must be `false`
- `additionalProperties: false` everywhere, so typos are errors rather than silently ignored

`common.validate_storyboard` adds rules the schema can't express:

- shot ids are unique
- the characters referenced by a shot exist
- music cues point at real shots
- **a character with `real_person: true` blocks the run unless ETHICS.md contains `CONSENT:<id>`**

That last rule is the consent gate in code.

## Caching

```
key = sha256(json([...exact inputs of this stage...]))[:12]
output = outputs/<stage>/<shot>-<key>.<ext>      # immutable, never overwritten
         outputs/<stage>/<shot>.<ext>            # stable copy of the current one, read by later stages
```

| Stage | Key inputs |
|---|---|
| script | English line, language, text model |
| narration | spoken line, voice, style instruction, TTS model |
| keyframes | full prompt (shot + character descriptions + style block; the negative goes only to Wan, since FLUX has no negative prompt), seed, model, size, **hashes of the reference images** |
| shots | hash of the keyframe or Wan clip, motion, length, output size |
| music | hash of the chosen candidate, loudness target |
| assemble | hashes of every shot, narration and score file, plus the music and end-card settings |

Changing a character's description changes their reference sheet, which changes the keyframe key of **only the shots that character appears in**. Old outputs stay on disk, so reverting a change is free: the old key is a cache hit again. `python run.py status` shows what will regenerate. `tests/test_offline.py` proves three things: a fresh run makes N calls, a second run makes 0, and a one-line edit makes exactly 2 (translation and TTS for that shot).

## Failure handling

| Failure | Handling |
|---|---|
| HTTP 429 / 5xx / timeout | `common.http_call` retries up to 4 times with exponential backoff (4, 8, 16, 32 s, honouring `Retry-After`). It logs **one** runs.jsonl line per logical call, including the attempt count and the final error. |
| HTTP 4xx (bad key, bad model ID, bad field) | No retry, because a retry can't fix it. The error body is logged and shown. |
| Primary image model fails | `cf_image_with_fallback` switches to `models.image_alt` (FLUX.1 schnell, text-only) and logs which model was used in the keyframe manifest. |
| One keyframe fails | The other shots continue. The failed shot keeps its previous keyframe, marked `stale`, and the shots stage warns. A rerun retries only that shot. |
| No Wan clip (quota, OOM, timeout) | The shot falls back to Ken Burns over its keyframe. This is the planned fallback. |
| Kaggle session dies mid-batch | `wan_shots.py` saves each clip as soon as it finishes and skips existing clips on restart. |
| No score yet | The music stage makes a clearly labelled placeholder pad, so the radio cut can be tested before any GPU work. |
| Translation corrected by a human | Setting `"locked": true` on the narration means it is never re-translated. |
| Crash halfway through the script stage | The storyboard is saved after every translated line. |

## Logging

`runs.jsonl` has one JSON line per model call, plus lines tagged `provider: "local"` for the FFmpeg steps so that stage timing is complete. Each line holds:

- `ts`, `run_id`, `stage`, `shot`, `provider`, `model`
- `params`, `seed`, `latency_s`, `gpu_s`
- `status`, `attempts`, `error`
- `cost_usd_free_tier`, `cost_usd_list_price` (from `pipeline/prices.json`)
- `cache_key`, `output`

The Kaggle scripts write the same format to `runs_kaggle.jsonl`, and the music stage merges those lines once each, using `call_id`. `python run.py costs` aggregates the log into COSTS.md.

## Mixing chain (assemble)

1. Each shot's narration is delayed to `shot start + lead_in`, mixed, then loudness-normalised to −16 LUFS (voice stem).
2. The score is looped or trimmed to length at −6 dB, with a 2 s fade-in and a 4 s fade-out.
3. `sidechaincompress` (threshold 0.02, ratio 6, attack 300 ms, release 1500 ms, all from `music.duck`) uses the voice as the key, so the music ducks under speech.
4. Voice and ducked music are mixed, then given a **two-pass** `loudnorm` to −14 LUFS integrated and −1 dBTP. The measurements are saved in `mix.loudness.json`.
5. The shot clips and the end card (rendered with Pillow, so it needs no font files) are joined, the English SRT is burned in, and the result is exported as H.264/AAC MP4 at a constant 24 fps. The vertical cut puts subtitles higher, inside the platform safe area.
