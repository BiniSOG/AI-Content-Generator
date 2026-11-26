# Design

> **How to fill this in:** replace every `TODO(you)` with your own words. Write sections 1–2 **before** generating any images, and commit them so the git history shows the order. Quote people's exact words in the test sections. Don't invent feedback; the interview checks it.

## 1. Audience and intent (written before generation)

- **Who:** TODO(you). Example: young Ethiopians aged 18–30 who live away from the town their family comes from, or abroad.
- **Where they watch:** TODO(you). Example: on a phone, vertical, in a TikTok, Instagram or YouTube Shorts feed, often with sound on.
- **What they should feel or understand at the end:** TODO(you). Example: a pull toward a grandparent, and the idea that a ritual is a way of keeping a person.
- **Problem statement:** "How might we help TODO(you) feel TODO(you)?"
- **Why this story:** TODO(you), in 2–3 sentences in your own voice.

### Constraints that shaped the design
- 60–90 s, which is about 130–170 words of narration once Amharic runs longer than English.
- One place (the family tukul and its fields) and two references (father, sons), to limit consistency problems.
- A realistic film-still look, so the faces read as Ethiopian rather than as generic illustration; all characters are fictional.
- No real person is depicted or voiced (see ETHICS.md).
- GPU quota: Wan 2.2 only on 3 hero shots, Ken Burns elsewhere.

## 2. Story

**Logline:** An old Ethiopian farmer on his sickbed calls his five quarrelling sons and, with a bundle of sticks, shows them that alone they break easily but together no one can break them.

A retelling of the old fable of the bundle of sticks (found in Aesop and in many other traditions), set in an Ethiopian highland farming family, narrated in Amharic, and closed with the Amharic proverb ድር ቢያብር አንበሳ ያስር ("when spider webs unite, they can tie up a lion").

**Beats:**
1. Place and the sickbed (s01–s02)
2. The problem: the sons quarrel (s03)
3. The call (s04)
4. The test: the tied bundle cannot be broken (s05–s06)
5. The turn: single sticks snap (s07–s08)
6. The lesson and its result: together in the same fields they fought over (s09–s10)

**Motif:** the bundle of sticks. It is tied in s05, untied in s07, rests under the father's hand in s09, and hangs by the door in s10.

**Characters:** one reference for the father and one group reference for the five sons (FLUX.2 takes only a few reference images per shot), each son dressed distinctly so they can be told apart.

## 3. Why every shot exists

| Shot | Size | Reason |
|---|---|---|
| s01 | extreme wide | Establishing shot: the place and the one lit doorway lead us to the sickbed before we meet anyone. |
| s02 | medium | Introduces the father and his worry in one image, so the audience asks what troubles him. |
| s03 | wide | Answers the question: the worry is the sons' division. Two groups and the oxen between them show what they fight over. |
| s04 | medium | Brings the divided brothers into one frame for the first time, around their father. |
| s05 | close up | Introduces the object the whole lesson depends on; close so the tight cord is clearly seen. |
| s06 | medium | Shows strength failing against the bundle, which sets up the surprise. |
| s07 | close up | The turn: the same sticks, separated. The father's hands do the teaching. |
| s08 | medium | The surprise, shown with all five at once so the audience sees it before it is explained. |
| s09 | medium close up | The father's words name the lesson; the brothers touching each other already show them taking it in. |
| s10 | wide | Resolution: the quarrel of s03 becomes shared work in the same fields, and the proverb gives the moral a local voice. |

(These reasons are also stored in `storyboard.json` as `shots[].reason`, so they can't drift from the plan.)

## 4. Test 1: the radio cut (narration, placeholder music, black screen)

- **Date and format:** TODO(you). Example: 2026-11-25, sent `radio_cut.mp4` on Slack and Telegram.
- **Questions asked:** (1) In one sentence, what was it about? (2) What did you feel at the end? (3) Where did you get lost or bored? (4) Did any word sound wrong?

| # | Who (audience match, no full names needed) | What they said (quote) | Where in the cut |
|---|---|---|---|
| 1 | TODO(you) | | |
| 2 | TODO(you) | | |
| 3 | TODO(you) | | |

**Insights:** TODO(you). What did several people say?

**What I changed in `storyboard.json` because of it** (link the commit):

| Change | Because | Commit |
|---|---|---|
| TODO(you) | | |

## 5. Test 2: the near-final cut (9:16)

- **Date and format:** TODO(you)

| # | Who | What they said (quote) | Did the change from Test 1 work? |
|---|---|---|---|
| 1 | TODO(you) | | |
| 2 | TODO(you) | | |
| 3 | TODO(you) | | |

**What I changed for the final:** TODO(you)

**What I chose not to change, and why:** TODO(you)
