# Failures

The format is **what broke → what I tried → what fixed it or how I worked around it → evidence**. Add an entry whenever something breaks: quota, out-of-memory, wrong model ID, bad pronunciation, a face drifting between shots. Real blockers are what this file is graded on.

### F01: model documentation unreachable while building the pipeline
- **What broke:** The environment the pipeline code was written in couldn't reach ai.google.dev, developers.cloudflare.com or huggingface.co (DNS failure), so the current model IDs and request formats couldn't be confirmed there.
- **Tried:** fetching the documentation pages. Only the ACE-Step GitHub README was reachable, and the music script follows its documented API (`GenerationParams`, `generate_music`).
- **Fix / workaround:** Model IDs moved out of the code into `storyboard.json` → `models`. `python run.py smoke` lists the models the key can actually see and flags any configured ID that isn't in the list. A wrong ID is now a one-line storyboard edit rather than a code change.
- **Evidence:** `pipeline/smoke.py`; the smoke lines in runs.jsonl.

### F02: vertical subtitles wrapped to three lines
- **What broke:** In the first offline render, a 9:16 subtitle cue ("In my grandmother's village, the day began before the sun.") wrapped to 3 lines at FontSize 11. Guidance is at most 2 lines.
- **Fix:** Vertical FontSize went to 9, with the safe-area margin kept (`pipeline/assemble.py`). The SRT itself is split at 40 characters per line, 2 lines per cue (`pipeline/subtitles.py`).
- **Evidence:** the frame check of `film_9x16.mp4` in the offline test.

### F03: Gemini text model overloaded at the smoke test (HTTP 503)
- **What broke:** The first `python run.py smoke` got a ReadTimeout on `gemini-3.8-flash`, then three HTTP 503 errors: "This model is currently experiencing high demand… try again later." The retry with backoff (4/8/16/32 s) ran out, so the text check failed. TTS (`gemini-3.8-flash-tts`) and FLUX.2 klein worked in the same run.
- **Tried:** the built-in retries. Waiting doesn't help a pipeline that has to run now.
- **Fix:** a model fallback chain configured in the storyboard (`models.text_fallbacks`, `models.tts_fallbacks`). Each model gets 2 attempts and then the next one is tried. The log line records the model actually used and the `requested_model`, so a fallback is visible in runs.jsonl. The fallback models came from the list the smoke test printed, so they're confirmed to exist for this key.
- **Evidence:** the smoke lines in runs.jsonl with `status: error, attempts: 4`; `pipeline/providers.py::_gemini_post`.
- **Follow-up:** the 2-attempts-per-model chain still failed when `gemini-3.8-flash` and `gemini-3.7-flash` were both overloaded: it spent ~12 s of backoff on each busy model before moving on. Now each model in the chain is tried **once per round**, and the pipeline waits (5/15/30 s) only after a whole round fails, for up to 4 rounds. Models that return a non-retryable 4xx are dropped from the chain. The chain also gained `gemini-3.6-flash`, `gemini-flash-latest` and three flash-lite models, which are usually less loaded. `gemini-2.5-flash` was removed. It shows up in the model list but returns HTTP 404 "no longer available to new users", so being listed by `models.list` doesn't prove a model is callable. When every model fails, the error now names each model with its own error, so a 404 from the last model no longer hides the 503s before it. Errors are logged as `HTTP 503: <message>` and not as raw JSON. The extra `round` field in runs.jsonl shows which pass succeeded.

### F04: FLUX.1 schnell on Cloudflare rejects `seed`
- **What broke:** The fallback image model returned HTTP 400: "Additional or unevaluated properties '/seed' at '/' not allowed".
- **Fix:** The seed is no longer sent to schnell. The log stores `seed: null` with `requested_seed` and `seed_supported: false`.
- **Consequence:** A keyframe made by the fallback model is **not seed-reproducible**. That's one more reason FLUX.2 klein, which takes a seed and reference images, is the primary model.
- **Evidence:** the smoke log line for `@cf/black-forest-labs/flux-1-schnell`, status error, HTTP 400.

### F05: FLUX.2 klein output flagged by Cloudflare's safety filter (code 3030)
- **What broke:** At the smoke test, `@cf/black-forest-labs/flux-2-klein-4b` returned HTTP 400 for "a clay coffee pot on a wooden table" plus the style block: `AiError: Your output has been flagged. Please choose another prompt / input image combination` (code 3030). This happened in two runs in a row at the same seed. FLUX.1 schnell, given the prompt *without* the style block, drew the scene without a problem.
- **Diagnosis:** the flag is deterministic, so it's the wording, not bad luck. The style block (added to every keyframe) said **"intimate and nostalgic"**. "Intimate" is a well-known sexual-content trigger, and the storyboard has a ten-year-old character (Liya) in s04/s07/s08, the combination filters block hardest. s04 also had the child "leaning in with closed eyes to smell the smoke" from a "smoking" pan (minor + smoking). Had it gone unfixed, most keyframes would have quietly fallen back to schnell, which takes no seed and no reference images, so character consistency would have been lost.
- **Fix:**
  1. Reworded `style.block` ("warm homely family atmosphere, nostalgic"), named Liya as Etenesh's granddaughter, and rewrote s04, s07 and s09 without "smoking"/"closed eyes". All of these change cache keys, so the refs and keyframes regenerate once.
  2. `python run.py validate` and `smoke` now warn about filter-prone wording (`common.image_filter_risks`), with a stricter word list for shots that include a minor.
  3. `cf_image` retries a flagged FLUX.2 output at seed+1000, then seed+2000 (fixed sequence, so still reproducible; `seed_used` is in runs.jsonl).
  4. If the smoke image is still flagged, it makes one call without the style block and reports whether the style text or the filter itself is at fault.
  5. Removed `Avoid: <negative>` from FLUX prompts. FLUX has no negative prompt, so "deformed hands, extra fingers" was going into the *positive* prompt. `style.negative` is still passed to Wan.
- **Evidence:** smoke lines in runs.jsonl with code 3030; `pipeline/providers.py::cf_image`, `pipeline/common.py::image_filter_risks`, `pipeline/smoke.py::_diagnose_flag`.

### F06: characters didn't look Ethiopian; script stage slowed by busy models
- **What broke:** (1) The reference sheets drew generic faces, not Ethiopian ones. The descriptions said only "Ethiopian" (and the F05 rewording had dropped it from Liya's), and the pale ochre/cream palette washed out skin tones. (2) `film` re-tried all five overloaded Gemini models for *every* narration line, including 90-second ReadTimeouts: about 6 minutes for one line.
- **Fix:** (1) The character descriptions now name Habesha features (rich brown skin, oval face, high cheekbones, slim nose, almond-shaped eyes, curled grey hair, shuruba braids) and clothing (habesha kemis, tibeb border). The style block says "rich natural brown skin tones". The ref prompt leads with "authentic Ethiopian Habesha appearance" and puts the face portrait first. `python run.py ref-candidates` renders 4 seeds per character, so a human can pick the best face and set `ref_seed`. (2) `_gemini_post` remembers models that were busy in the last 3 minutes and tries the others first, so after the first line finds a working fallback, the next lines go straight to it. Early rounds also use half the timeout.
- **Evidence:** outputs/refs/candidates/*.png; the `round` and `requested_model` fields in runs.jsonl.

### F07: still not Ethiopian, cups held wrong, final film without audio
- **What broke:** (1) The faces and the grandmother's hair still didn't read as Ethiopian. (2) In the keyframes, people held cups in the wrong place. (3) The final video had no audible audio.
- **Diagnosis:** (1) The painted gouache style pulls faces toward a generic illustration, and the descriptions named features but not the visual markers that really identify an elderly Orthodox Amhara woman: hair in fine shuruba braids under a netela draped over the head, a forehead cross tattoo, the habesha kemis with tibeb. The two-panel "reference sheet" also gave FLUX.2 a split image to copy from. (2) The prompts never said which hand holds what, where, or which way up, and a 4B model fills those gaps at random. (3) The export command is correct; the offline test produces audible audio. Nothing in the pipeline checked that the TTS audio was really speech, so a TTS model returning near-silent audio (a known failure for languages a model doesn't fully support, like Amharic) or a non-PCM format would produce a silent film without any error.
- **Fix:**
  1. Style changed to a cinematic, realistic film still. Full descriptions are used for the reference portrait (now one waist-up portrait, not a two-panel sheet); a compact `short` description goes into shot prompts, which have a 2048-character limit (now checked).
  2. Every shot prompt was rewritten to follow the real buna ceremony (roast in the menkeshkesh over the brazier, waft the aroma, grind in the mukecha, pour abol from a height, the child serves the eldest first) with exact hand and object positions: who holds what, with which hand, at what height, cups upright on the tray under the spout.
  3. Audio is now checked at every step: TTS output that is silent or too short for its text counts as a failure and the next TTS model is tried; cached silent narration files regenerate; non-PCM TTS formats are decoded with ffmpeg; `assemble` refuses to write a silent voice track or film; `python run.py check-audio` shows where the audio is lost.
- **Evidence:** `python run.py check-audio` output; `pipeline/providers.py::gemini_tts`.

### F08: Amharic on screen needs an Ethiopic font
- **What broke:** switching the subtitles to Amharic + English would have drawn every Ge'ez letter as an empty box: the subtitle font, DejaVu Sans, has no Ethiopic glyphs. The first version of the bilingual subtitles also cut long Amharic sentences after two lines.
- **Fix:** `subtitles.subtitle_font` picks a font with Ethiopic letters (Nyala on Windows, Kefa on macOS, Noto Sans Ethiopic or Abyssinica SIL on Linux via `fc-list :lang=am`) and stops with an install hint if there is none. Long Amharic sentences are split at ፣ ፤ ፦ into several cues, and the English is paired with them sentence by sentence (split by length when the counts differ); no text is ever dropped.
- **Evidence:** frames from the offline test with Abyssinica SIL, 16:9 and 9:16.

### F09: TODO(you), the next real failure from your run
- **What broke:**
- **Tried:**
- **Fix / workaround:**
- **Evidence (runs.jsonl line, error text, file):**

<!-- Likely candidates: a wrong model ID at the smoke test; Cloudflare daily allowance used up; Gemini 429 rate limit (see the attempts>1 lines in runs.jsonl); Amharic names mispronounced; character face changing between s02 and s07; Wan OOM on T4 or no bf16; ACE-Step LM planner failing on T4 (the script falls back to DiT-only); Kaggle session timeout. -->
