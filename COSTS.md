# Costs and measurements

## Free-tier limits I actually found (check them on the day you run)

| Service | What I found | Date checked |
|---|---|---|
| Gemini API (AI Studio) | TODO(you): requests per minute and per day for the text and TTS models | |
| Cloudflare Workers AI | TODO(you): daily free neurons, and roughly how many images that allowed | |
| Kaggle | TODO(you): weekly GPU hours shown in Settings, and how many I used | |

## Measured per stage (generated from runs.jsonl)

Run `python run.py costs` to regenerate the table below. The latencies are wall-clock time per call. "GPU min" comes from the `gpu_s` the Kaggle scripts log. The list-price equivalent uses `pipeline/prices.json`, so **verify those unit prices** and correct them there.

<!-- AUTO:START -->
_Not generated yet: run `python run.py costs`._
<!-- AUTO:END -->

## Notes

- **The money I paid was $0.** Everything ran on free tiers.
- **The binding constraint was GPU time, not money.** TODO(you): minutes per Wan clip on a T4 compared with Ken Burns (about 1 s locally), and how many hero shots that bought.
- **The cost of the live one-line change** (from the walkthrough): TODO(you). Example: 1 translation call and 1 TTS call, X s in total.
- **Frontier comparison:** TODO(you). Fill this in if the cohort's frontier lane was available; otherwise write "not available to me".
