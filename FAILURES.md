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
- **What broke:** At the smoke test, `@cf/black-forest-labs/flux-2-klein-4b` returned HTTP 400 for "a clay coffee pot on a wooden table" in the gouache style: `AiError: Your output has been flagged. Please choose another prompt / input image combination` (code 3030). FLUX.1 schnell drew the same scene without a problem.
- **Tried:** retrying. The same prompt and seed give the same image, so it gets flagged again. The filter checks the *output*, so this is a false positive on that one image, not a problem with the prompt.
- **Fix:** `cf_image` catches code 3030 on FLUX.2 and tries again at seed+1000, then seed+2000. The sequence is fixed, so the keyframe stays reproducible. runs.jsonl records `requested_seed` and `seed_used`. If all three seeds are flagged, the keyframes stage falls back to `image_alt` as before.
- **Evidence:** the smoke line in runs.jsonl with `status: error` and code 3030; `pipeline/providers.py::cf_image`.

### F06: TODO(you), the next real failure from your run
- **What broke:**
- **Tried:**
- **Fix / workaround:**
- **Evidence (runs.jsonl line, error text, file):**

<!-- Likely candidates: a wrong model ID at the smoke test; Cloudflare daily allowance used up; Gemini 429 rate limit (see the attempts>1 lines in runs.jsonl); Amharic names mispronounced; character face changing between s02 and s07; Wan OOM on T4 or no bf16; ACE-Step LM planner failing on T4 (the script falls back to DiT-only); Kaggle session timeout. -->
