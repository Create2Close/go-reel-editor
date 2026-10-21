# Listicle

The whole payload on screen, static, over one real-life clip: title, list, punchline. A viewer who never opens
the caption gets 100 % of the value from the screen. The highest-reach EZ reel and the cheapest build.
Too dense to read in one pass is the point: people rewatch (examples loop 2.7-5x).

Two kinds, two jobs:
- **Debate bait** (rankings, opinions, provocative data): comments and reach. Punchline = the member's opinion.
- **Utility save** (checklists, lookup tables, steps): saves and follows. Punchline = an action line in quotes
  ("APPLY TO PRINCIPAL ONLY") or none. Near-zero comments is normal.

## What the editor builds

```json
{"clip": "walk.mov", "title": "What $400K buys you in 2026",
 "items": ["Austin TX: 3 bed, 2 bath", "..."],
 "small": "Source: Zillow, Oct 2026",
 "punchline": "Same money. Very different house."}
```

Two columns ("RENTING vs OWNING", "can control vs can't"): `"columns": [{"header": "RENTING:", "color": "red",
"items": [...]}, {"header": "OWNING:", "color": "green", "items": [...]}]`.

## Rules

- **Title**: 8 words or fewer, readable in one second. No clickbait the list can't cash.
- **List**: 5-14 rows (the engine refuses more than 14). About 8 words a row (numbers don't count). One row
  pattern, parallel wording. The best lists read as a story: problem → escalating facts → kicker on the
  shortest line.
- **Punchline**: bottom, its own colour, 1-2 sentences, never a number that isn't on screen.
- **Footage**: one clip of real life (a walk, the backyard, driving). Phone quality is right; stock reads as an
  ad. It doesn't need to match the topic. All text appears at once and holds; no animation.
- **Length**: 7 s unless the member asks otherwise (a 13-14 row table can earn 10-12 s). Short clips loop.
- **Text stays in the feed-safe band** (y300-1600 of 1920): Facebook shows reels as a 4:5 crop and the
  Instagram buttons cover the bottom. The engine refuses anything outside it: shorten, don't shrink.
- **Silent**: the trending sound goes on in the Instagram app.

## Check before you hand it over

- Every number, span and place name matches the member's copy exactly ("West Palm Beach", and 2015-2025 is
  eleven years). Their copy is the truth: flag a sum that doesn't add up, don't fix it silently.
- Money tables show their assumptions on screen (rate, term, down payment) in the `small` line.
- Compliance: payments, rates, down payment and term are trigger terms. Remind the member to run a money table
  past compliance before posting.

Examples (GO coaches): Rebecca Foote "History of Mortgage Rates" (2.35M plays), Heath Barnes "Your Bank hopes you
NEVER learn this" with "APPLY TO PRINCIPAL ONLY" (2.25M), Daniel Solis "How much salary to afford a home" (a
lookup table, "Save this for later").
