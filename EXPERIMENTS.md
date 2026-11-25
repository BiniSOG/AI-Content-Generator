# Experiments

Each entry changes **one thing**, with the seed fixed, unless the seed is the thing being tested. Outputs are in `outputs/experiments/<id>/`, measurements are in `outputs/experiments/<id>/result.json`, and every call is in `runs.jsonl`. You run them with `python run.py experiments`.

> **Fill in the Result and Decision lines yourself** after you look or listen. Write numbers where `result.json` has them. If a hypothesis turned out wrong, say so; that's the most valuable kind of entry.

### E01: the style block keeps the look consistent
- **Hypothesis:** Appending the fixed style block makes a shot look like the rest of the film; without it the model drifts to a generic photo look.
- **Change:** the style block on (A) vs off (B). Fixed: shot s02, its seed, the model.
- **Result:** TODO(you)
- **Decision:** TODO(you)

### E02: reference image vs text-only character
- **Hypothesis:** Conditioning on the character reference keeps Etenesh recognisable better than describing her in text alone.
- **Change:** FLUX.2 `input_image` refs on (A) vs off (B). Fixed: shot s04, seed, prompt.
- **Result:** TODO(you)
- **Decision:** TODO(you)

### E03: FLUX.2 klein vs FLUX.1 schnell
- **Hypothesis:** klein follows long prompts (props, clothing details) better at similar speed.
- **Change:** the model. Fixed: prompt s06, seed. Latency is in result.json.
- **Result:** TODO(you). Include both latencies.
- **Decision:** TODO(you)

### E04: seed vs prompt
- **Hypothesis:** The seed changes composition far more than identity, so picking the best of 3 seeds is cheaper than rewriting the prompt.
- **Change:** 3 seeds. Fixed: prompt s07, refs, model.
- **Result:** TODO(you)
- **Decision:** TODO(you)

### E05: TTS style instruction
- **Hypothesis:** "Calm, warm, unhurried" slows the delivery and makes it sound less like an announcement.
- **Change:** the style instruction off vs on. Fixed: voice, line s07. Durations are in result.json.
- **Result:** TODO(you). Include the duration difference in seconds.
- **Decision:** TODO(you)

### E06: voice vs style instruction
- **Hypothesis:** The choice of voice matters less than the style instruction.
- **Change:** the voices Kore, Sulafat and Aoede. Fixed: the style instruction and the line.
- **Result:** TODO(you)
- **Decision:** TODO(you)

### E07: language support (ceiling work)
- **Hypothesis:** Gemini TTS handles Amharic acceptably but Afaan Oromo and Tigrinya worse, and back-translation shows where meaning is lost.
- **Change:** the language (am / om / ti / en). Fixed: the source line, voice, style. result.json holds each translation and its back-translation.
- **Native-speaker rating, 1–5, with mispronounced words:** TODO(you). Ask one person per language.
- **Result:** TODO(you)
- **Decision:** TODO(you)

### E08: ducking ratio
- **Hypothesis:** Ratio 6 keeps the voice clear without pumping; ratio 2 leaves the music too loud under speech, and ratio 12 pumps.
- **Change:** sidechain ratio 2 / 6 / 12. Fixed: threshold, attack, release, score. Music-only and mix LUFS are measured in result.json.
- **Result:** TODO(you). Include the measured LUFS.
- **Decision:** TODO(you)

### E09: Ken Burns move for a close-up
- **Hypothesis:** On a close-up of hands, a slow zoom-in reads as attention, while a pan reads as searching.
- **Change:** zoom_in / pan_right / static. Fixed: keyframe s05, 6 s, 9:16.
- **Result:** TODO(you)
- **Decision:** TODO(you)

### E10: three ACE-Step score candidates
- **Hypothesis:** A caption that says "no lead melody, sparse" gives at least one candidate that sits under the voice without competing.
- **Change:** seeds 101 / 202 / 303. Fixed: caption, bpm 72, key C minor, 90 s.
- **How judged:** listen to each at low volume under the radio-cut narration.
- **Result:** TODO(you). Describe each candidate in one line.
- **Decision:** the chosen candidate, also written to `music.chosen` and `music.chosen_reason` in storyboard.json.

### E11: Wan 2.2 clip vs Ken Burns, same shot
- **Hypothesis:** On a T4 at 640×640, Wan adds believable motion (smoke, steam) to simple shots, but costs minutes of GPU time per clip, versus about 1 s for Ken Burns.
- **Change:** `motion.mode` wan vs kenburns for s03. GPU seconds are in runs.jsonl.
- **Result:** TODO(you)
- **Decision:** TODO(you)
