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

### F03: TODO(you), the first real failure from your run
- **What broke:**
- **Tried:**
- **Fix / workaround:**
- **Evidence (runs.jsonl line, error text, file):**

<!-- Likely candidates: a wrong model ID at the smoke test; Cloudflare daily allowance used up; Gemini 429 rate limit (see the attempts>1 lines in runs.jsonl); Amharic names mispronounced; character face changing between s02 and s07; Wan OOM on T4 or no bf16; ACE-Step LM planner failing on T4 (the script falls back to DiT-only); Kaggle session timeout. -->
