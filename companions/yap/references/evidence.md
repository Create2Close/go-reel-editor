# Evidence behind the YAP skill

Every rule in `SKILL.md` traces to a study of **100 true-yap outlier videos** (transcribed and
frame-analyzed) drawn from **1,324 scraped videos** across **14 creators** on Instagram and
TikTok, conducted August 2026. Outlier score = a video's plays ÷ that creator's own median plays.

**Corpus definition (revised 2026-08-26 at the project owner's direction):** a true yap is one
creator talking directly TO THE VIEWER for the whole video — scripted or not, edited or not.
The original 98-outlier set also contained **27 acted dialogue skits** (roleplay two-handers,
mostly from two mortgage creators), **5 lifestyle vlogs**, and **2 other non-yaps**;
those were classified out (see `format_classification.json` in the research database). They are
real, working formats — but different formats, with different mechanics, and this skill does not
teach them. Stats below are on the clean 64 unless marked otherwise.

Creators studied: 8 mortgage/real estate creators, plus 6 business/creator/marketing creators (the
topic-agnostic replication set, added 2026-08-26 at ≥2.0x bar). Patterns below held across both groups unless noted.

---

## THE GOVERNING CAVEAT

**Outlier score is noise-dominated. Never present any of this as causal.**

- The *same true yap* posted twice, a day apart, did **95,628 plays and then 5** (18.97x → 0.00x).
- A lifestyle video reposted two hours later scored **97.95x and 11.29x**.
- One creator posted the same topic 18 times in 10 weeks: scores ran **0.16x to 24.54x**.
- Two near-identical captions, same creator, a month apart: **0.17x and 18.53x**.

Base rates across the original 799: **19.9% clear 2.5x · 11.5% clear 5x · 6.6% clear 10x.**
Roughly one in five posts beats the creator's own median. Plan against that number.

Also: the corpus is **survivorship-selected** (chosen at ≥2.5x), and **creator is confounded
with style** — each creator runs essentially one format. Same-creator contrasts are the
reliable evidence; cross-creator medians are partly creator comparisons.

---

## ONE CLAIM

- Single-claim videos reached **24–87x**; videos with genuinely independent points plateaued at
  **5–14x**. Every one of the top 12 structurally-real performers makes exactly **one** claim —
  including the list videos, which collapse their items into one thesis.
- **The concept trap:** the same creator scored **87.46x** on a story about his father tapping
  an empty glass and **0.29x** on "The best investment you'll ever make can't be bought." Same
  domain, same length, same voice. Another creator: **34.26x** counting corporate landlord
  listings (4,166 → 9,447 after a dated bill) vs **0.05x** on "the hedonic treadmill" and
  **0.11x** on "the Confidence Tax."
- **Trap beats option:** "ask for a seller credit, do NOT lower the price" **26.78x** vs "you
  can borrow from your 401k" **2.44x**.
- **Cost/confession beats reassurance:** revealing that loan officers repay commission on early
  payoffs **31.04x** vs "medical debt doesn't always hurt your chances" **0.00x**.
- **Sort + threat:** "why you should avoid FHA if you're buying in 2026 **and have good credit**"
  **18.53x** vs "4 reasons **I wouldn't** use FHA" **9.46x** vs neutral explainers ~**0.20x**.

## THE AUDIO HOOK

Measured on the final 100 (top third vs bottom third by outlier):

| Feature | Top third | Bottom third |
|---|---|---|
| **Opens with a question** | **0%** | 18% |
| "you / your" in first sentence | 51% | 48% (no separation on the diverse corpus; overall you-density still 1-in-20 words) |
| Median first-sentence length | 18 words | 17 words (no separation) |

(Directional detail from the wider pre-split set: negation 34% vs 23%; a forward-pointing
open loop 37% vs 10% — the largest single gap measured.)

- Median first sentence: **20 words ≈ 5–6 seconds.** Winners are dense, not short.
- 83% make the topic clear inside the first sentence.
- **Credentials appear at median word 39 (~12.5s), never at word 0.** The two videos that led
  with credentials scored **3.36x** and **1.91x** — near the bottom of their creators' catalogs.
- Time to first payoff: median 13.4s, and it does **not** predict performance. What predicts
  performance is whether the first 5 seconds contained a claim worth waiting for.

## THE VISUAL HOOK

First-frame analysis paired with the words spoken in the first 3 seconds. On the final 100:

| | n | median outlier |
|---|---|---|
| Designed on-screen text present | **74 (74%)** | **8.67x** |
| No designed text | 26 | 5.09x |

| Pairing (text ↔ first-3s speech) | n |
|---|---|
| SECOND_LAYER — a claim the speech withholds | 28 |
| COMPRESS — punchier version of the claim | 27 |
| REPEAT — the spoken line, verbatim | 16 |
| CONTEXT_GATE — names the situation | 5 |
| NONE | 24 |

- **The verbatim REPEAT is a legitimate system, not a failure** — 16 of 100, including 190x,
  144x, 49x, 47x, and 40x outliers, and one creator who runs a locked
  white-on-black pill of his opening line on every video. It works when the first line IS the
  compressed claim; transcribing a weak opener is what fails.
- The top of the diverse corpus also shows a **no-designed-text mode**: one creator's 190x
  runs only word-at-a-time karaoke captions over striking footage — the scene is the hook.
- Auto-captions show **no** performance correlation — furniture, not a hook.
- (CHARACTER_LABEL / "Part 2" series cards existed only on the excluded skits — high floor,
  hard ceiling ~8.8x. Retention device, not an acquisition device.)
- Text is **not mandatory** — two big outliers (26.78x, 18.27x) have none. What high outliers
  share is a concrete promise in *whichever* channel carries it.
- Every creator runs one **locked template**; off-template videos are disproportionately their
  weakest.
- Top outliers stack a third layer — a CNBC page, a real Loan Estimate, a 1997 grocery receipt.

## THE MIDDLE (PROOFS)

- **Instantiate or die:** 70% of the corpus contains digits; zero high performers teach
  abstractly. The "Illustrate" slot is filled by a *worked number* more often than a story.
- **One scenario carried to its consequence beats a table:** 24.3x vs 5.5x for exactly that
  contrast within the corpus.
- **Objection pre-empt ("8 Mile") is a beat, not a structure** — appears in ~16% of videos,
  consistently at **55–70% through**, never at the top.
- **Judgment lists beat inventory lists:** "5 things I notice about people" **47.75x** vs "5
  things to look for on your loan estimate" **0.83x**. Listicles as a format are neutral
  (median 1.01x) — what matters is whether each item is a verdict.

## LANDING

(Measured pre-split; the excluded skits' signature ending — the abrupt mid-scene stop — is
removed. For true yaps the menu is the three below plus the hard CTA.)

| Ending | n | Range | Note |
|---|---|---|---|
| Landed aphorism + follow CTA | 24 | 2.92–**87.46x** | The CTA rides on the payoff |
| Landed point, no ask | ~15 | 2.59–24.31x | |
| Question to comments | ~7 | 2.80–**47.75x** | Top users ask for nothing else |
| Hard link-in-bio CTA | 12 | 2.44–26.78x | Converts; caps reach |

Worst endings: the applause close ("we'll see you next time") **1.90x**, and a bare instruction
with no hook behind it **1.86x**.

## LANGUAGE (measured on the wider pre-split corpus, 30,516 words; the monologue rules below
were derived from the direct-to-camera videos and are unaffected by the skit exclusion)

- **"you/your" = 48.2 per 1,000 words, in 98% of videos** — 1 in every 21 words.
- High performers use **13% less "I"** (35.7 vs 41.2 per 1k). Within-creator correlation of
  I-density with performance: **−0.12** (−0.61 and −0.67 for the two most disciplined creators).
  The lowest-performing creator had the highest I-density (60.4/1k).
- **Sentence length does NOT separate winners from losers** — both groups write the same way.
  Median 10 words, mean 13.45, SD 15.24. 38% under 8 words, 20% over 20. 46% of videos contain
  a run of 3+ consecutive sub-8-word sentences.
- **What does separate them: volume.** High performers say **46% more words over 27% more time**
  (298 words / 87s vs 226 / 64s). Duration correlates **+0.26** and stays positive within 7 of 8
  creators.
- **Contraction rate 83.7%** — uniform across tiers, table stakes.
- **Filler:** weak performers use **2.1x more "like"**, **4x more "you know"**. "I mean" and
  "literally" appear **zero times** in top performers. Within-creator filler correlation **−0.17**.
- **"Here's the thing" appears 6 times in 30,516 words** — a writing-about-talking cliché, not a
  talking cliché.
- **Pace: median 203 wpm** (conversational English is ~130–150). But WPM correlates at only
  **+0.12** corpus-wide and **−0.02 within creators** — a creator trait, not a lever. Only the
  bottom quartile is measurably slower (194 median). Don't speed up; don't drift below 160.

## LENGTH

On the final 100:

| Band | n | Median outlier |
|---|---|---|
| ≤45s | 21 | 8.63x |
| 46–90s | 43 | 6.85x |
| 91–120s | 17 | 6.87x |
| >120s | 18 | 8.36x |

Corpus median duration: **81 seconds.** Median words: **258** at **204 wpm**.
**Length does not predict performance** — the bands are flat. The earlier mortgage-only corpus
showed longer-wins; the diverse corpus erased it. What survives: ignore the 60-second rule in
both directions, and match length to the proof. Median outlier score *rises* with duration. The
60-second ceiling is not real for this format — but duration explains only **5.7%** of
within-creator variance, so length is permission, not a lever.

## THE SUB-10s MEME CLIP (a separate business)

Across all 799: sub-10s clips are **18.4% of output but produce 42% of all ≥10x outliers**,
while carrying the highest median (1.29x) and the most extreme tail. One creator's 8-second
clip did 5.9M plays — **44% of his entire catalog's reach**. These are borrowed-audio memes
where the **caption is the joke** and the clip is the delivery vehicle. They are an
**audience-acquisition lottery, not a content strategy** — and they teach nothing about talking,
which is why they were excluded from the training corpus. A creator who only yaps has a low
ceiling; a creator who only memes has no business.

## TOPIC FRAMING

Caption-word lift, top-quintile vs bottom-half across all 799:
**over-represented** — income 2.19, price 2.00, housing market 1.75, cost of living 1.59,
inflation 1.17. **Under-represented** — credit 0.47, home 0.66, payment 0.71, tips 0.74,
rate 0.79, first-time-buyer 0.80.

Broad cultural/economic framing outperforms narrow craft-technical framing roughly **2:1**.
Translated out of any niche: **the topic that travels is the one your niche is a lens onto, not
the one your niche is about.**

---

## Full research

The complete analysis — five reports with per-video citations, all 98 transcripts with metadata
and visual-hook annotations, first-frame stills, and the re-runnable scrape pipeline — lives in
`GO!/Sessions/Yap Aug 27/yap-database/`.
