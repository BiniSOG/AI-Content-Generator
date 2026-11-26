# Ethics: consent, labelling, licences

## Consent

**No real person's face, likeness or voice appears in this film.**

- **Etenesh and Liya are fictional.** The storyboard sets `characters[].real_person = false`. Their appearance is written as a fictional composite of typical Ethiopian Habesha features and dress (so the film represents its community accurately rather than generically), and no photo of a real person was used as a reference.
- **The narrator's voice is a stock Gemini TTS voice** ("Kore"). It is not cloned from anyone; the storyboard enforces `voice.cloned: false`.
- **The story** is a composite inspired by the common Ethiopian coffee ceremony, not one family's private history. TODO(you): if it is inspired by your own grandmother, say so here, and say that no private details were sent to any API.
- **The pipeline enforces consent in code.** If a character is ever marked `real_person: true`, `python run.py validate` refuses to run until this file contains a line `CONSENT:<character_id>` with the record below.

<!-- Template, only needed for a real person:
CONSENT:<character_id>
- Person: <name or initials>, relationship: <...>
- What they agreed to: likeness / voice / the exact narration lines (attach the text)
- How recorded: <voice note / signed message / video>, date: <YYYY-MM-DD>, stored at: <private location, not in this repo>
-->

## Labelling

- The film ends with a 3-second **"Made with AI"** end card. It names the tools used. It comes from `storyboard.json` → `end_card`, and the schema requires the text to contain "AI".
- When posting, **the platform's AI-content disclosure is switched on**. On YouTube that's "Altered or synthetic content" = Yes; on TikTok it's "AI-generated content".
- No watermark or provenance metadata is stripped. FFmpeg re-encoding may not carry C2PA manifests across; TODO(you): check and note this.
- Each post will say in its caption that the images, voice and music are AI-generated.

## Private data

- No personal or family information is sent to any API. The prompts and narration are all in `storyboard.json` and contain only the fictional story.
- Note the data terms of the free tiers: free-tier Gemini API content may be used to improve Google products. That's acceptable here because nothing private is sent.

## Licences

| Component | Used for | Licence / terms | Output use |
|---|---|---|---|
| Gemini Flash (Gemini API, free tier) | translation, experiment back-translation | Gemini API Terms of Service | output may be used; free-tier data may be used by Google |
| Gemini TTS (Gemini API) | narration | Gemini API Terms of Service | synthetic voice; label it as AI |
| FLUX.2 klein 4B (Cloudflare Workers AI) | keyframes | Apache 2.0 (4B weights) and Cloudflare terms | usable |
| FLUX.1 schnell (fallback) | keyframes (fallback) | Apache 2.0 | usable |
| Wan 2.2 TI2V-5B | moving shots | Apache 2.0 | usable |
| ACE-Step 1.5 | score | MIT; trained on licensed, royalty-free and synthetic data | usable commercially |
| FFmpeg | assembly | LGPL/GPL (tool, not distributed here) | n/a |
| This repository's code | pipeline | TODO(you): choose one, e.g. MIT | |

TODO(you): open each model page once and confirm the licence is still as listed above.

## Style

The prompts describe qualities ("hand-painted gouache, warm earthy palette, paper grain") and name no living artist.
