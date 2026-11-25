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
- One place and two characters, to limit consistency problems.
- A stylised, hand-painted look: it's kinder to identity drift than photorealism, and it isn't anyone's likeness.
- No real person is depicted or voiced (see ETHICS.md).
- GPU quota: Wan 2.2 only on 3 hero shots, Ken Burns elsewhere.

## 2. Story

**Logline:** A woman far from home remembers how her grandmother taught her the coffee ceremony, and learns that it was never about the coffee.

**Beats:**
1. Place (s01)
2. The ritual and the person (s02–s03)
3. Sharing (s04)
4. Repetition, years in the hands (s05)
5. The first cup (s06)
6. The handover and its meaning (s07–s08)
7. Absence and continuity (s09)

**Motif:** the coffee smoke. It is greeted in s04, and it "still finds me" in s09.

## 3. Why every shot exists

| Shot | Size | Reason |
|---|---|---|
| s01 | extreme wide | Establishing shot: the audience must know this is a highland village at dawn before we meet anyone. |
| s02 | medium | Introduces Etenesh doing the ritual, so the first face we see is tied to the coffee. |
| s03 | close-up | The beans give the sound and smell a picture; it is the detail people remember. |
| s04 | medium | Introduces Liya and the first contact between the two: the smoke is passed to her. |
| s05 | close-up | Old hands grinding: years of repetition shown, not told. |
| s06 | medium close-up | The high pour from the jebena is the iconic image of the ceremony and the visual peak of the first half. |
| s07 | close-up | Turning point: the jebena is passed on; the line of dialogue carries the theme. |
| s08 | wide | Answers her line: the neighbours who come. The film's meaning is the people. |
| s09 | medium | The empty stool says she is gone without saying it; the narrator keeps the ritual alive. |

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
