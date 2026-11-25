# Walkthrough script (at most 5 minutes)

**Before you hit record:**
- Run `python run.py film` once, so everything is cached.
- Open `storyboard.json`, ARCHITECTURE.md and a terminal.

1. **0:00–0:30, what this is.** Play 10 s of the vertical film. Say who it's for and what they should feel.
2. **0:30–1:45, architecture.** Show the stage table in ARCHITECTURE.md:
   - One contract: `storyboard.json`, validated by the schema before every run.
   - Each stage reads it and writes cached outputs named by a hash of its inputs.
   - Every call is logged to `runs.jsonl`.
   - The GPU stages run on Kaggle with the same contract.
3. **1:45–2:45, one hard decision.** Pick one:
   - Wan on only 3 hero shots with Ken Burns elsewhere, because a T4 needs minutes per clip (show the gpu_s numbers).
   - Cutting picture to the measured Amharic narration instead of fixed durations.
   - Whatever your hardest real problem was (FAILURES.md).
4. **2:45–4:30, live regeneration.**
   - Run `python run.py status`: everything is cached.
   - Edit **one** line, e.g. `s04.narration.en`, or one `image_prompt`. Save the file.
   - Run `python run.py film`. Point at the summary: `script s04`, `narration s04`, nothing else.
   - Show the new lines in runs.jsonl. On Windows: `Get-Content runs.jsonl -Tail 3`. On Mac or Linux: `tail -n 3 runs.jsonl`.
   - Play the changed shot in the new film.
5. **4:30–5:00, one thing you learned.**
