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
- One place (the race path) and two characters, to limit consistency problems.
- A nature-documentary look with realistic animals: image models draw animals far more consistently than people, and no one's likeness is involved.
- No real person is depicted or voiced (see ETHICS.md).
- GPU quota: Wan 2.2 only on 3 hero shots, Ken Burns elsewhere.

## 2. Story

**Logline:** In the Ethiopian highlands, a boastful rabbit challenges a slow tortoise to a race, naps halfway because he is sure he will win, and wakes to find the tortoise has already reached the finish.

A retelling of Aesop's fable *The Tortoise and the Hare*, set in the Ethiopian highlands with animals native to them (an Ethiopian highland hare, a leopard tortoise, gelada monkeys), narrated in Amharic, and closed with the Amharic proverb ቀስ በቀስ እንቁላል በእግሩ ይሄዳል ("little by little, even an egg learns to walk").

**Beats:**
1. Place and the race course: the path and the far warka tree (s01)
2. The boast and the challenge (s02–s03)
3. The start: one flies, one barely moves (s04)
4. Overconfidence: far ahead, then the nap (s05–s06)
5. Steady steps, and the pass (s07–s08)
6. The finish and the lesson (s09–s10)

**Motif:** the warka tree. It is the far dot in s01, the finish in s09, and the shelter where the rabbit is humbled in s10.

## 3. Why every shot exists

| Shot | Size | Reason |
|---|---|---|
| s01 | extreme wide | Establishing shot: the place and, through the path and the far tree, the race course and its finish before we meet anyone. |
| s02 | medium | Introduces the rabbit and his flaw, pride, in one image: high on the rock, looking down. |
| s03 | close up | Low angle on the tortoise answers the high angle on the rabbit: the small one accepts the challenge calmly. |
| s04 | wide | The whole contrast of the film in one frame: one is already flying, the other has barely moved. Local animals as the crowd. |
| s05 | medium | Shows the distance between them, which is what makes the rabbit careless. |
| s06 | medium | The mistake: the rabbit stops because he underestimates the tortoise. The calm image makes the danger funny. |
| s07 | close up | The film's lesson shown, not told: steady steps. Close and low so the slow walk feels determined, not weak. |
| s08 | medium | The turning point: both characters in one frame as the lead changes hands. |
| s09 | wide | The payoff: the winner and the loser in one frame, so the audience sees the result before it is said. |
| s10 | medium close up | Resolution: the proud one is humbled, and the Amharic proverb gives the moral a local voice. |

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
