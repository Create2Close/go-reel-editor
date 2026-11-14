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

## The checklist layout

A second way to draw a listicle: one centred column, every line of text in its own rounded box. A coloured title, the
points in white boxes with a check mark before each, a closing line in a black box. The title and every point are on
screen from the first frame; the closing line cuts in three quarters through and stays.

```json
{"layout": "checklist", "clip": "street.mov",
 "title": "Buying your first home? Read this first",
 "items": ["Get pre-approved before you tour a single house.",
           "Your payment is more than principal and interest.",
           "Closing costs run 2% to 5% of the price.",
           "A lower rate is not always the cheaper loan.",
           "Keep your credit quiet until the keys are yours."],
 "punchline": "📌 Save this before you start your search"}
```

**Pick it** for one list of three to six full-sentence points: a "read this first", "save this", "before you..." post.
**Keep the usual list** for short rows (a place and a number, a ranking, a lookup table), more than six rows, a
`small` source line, or two sides compared in columns. Their words win: "the checklist one", "the one with the check
marks and boxes".

- **Points**: 3 to 6 (the engine refuses 7), each a full sentence of about 6 to 10 words. A point is two lines at
  most, and so are the title and the closing line. Long points wrap into two lines of similar width by themselves;
  a line break typed in the text (`\n`) is kept.
- **The mark**: a green check mark before every point. `"bullet": "👉"` changes it, `"bullet": ""` removes it. A
  point that already starts with its own emoji keeps that one and gets no second mark.
- **Closing line**: one sentence that tells the viewer what to do with the list ("Save this before..."). It shows
  the emoji the member's text starts with; the editor never adds one. Leave `punchline` out for none.
- **Length**: about six words a second for everything on screen, 7 s at least and 12 s at most (the example above
  is 57 words: 9.5 s). `"duration"` sets it; `"punchline_at": 5` sets the second the closing line appears (0 = from the start).
- **Too much text**: the type gets slightly smaller before the editor refuses (never under the look's floor). When
  it does refuse it says which point is too long or that the stack is too tall: shorten or cut, as it says.
- **Position**: the stack sits just above the middle of the frame, inside the feed-safe band. `"center_y": 0.45`
  moves it (0 top, 1 bottom).
- The look draws it: its font in bold, its red box for the title (a member's own colour in their look), white and
  black boxes below (`looks/README.md` § `listicle.checklist`).
- The other rules above (footage, silent, the feed-safe band) and the checks below apply as written.

**From EZ Reel Writer output**: TITLE → `title`; each line under LIST → one entry in `items`, without its leading
check mark, dash or number (the editor draws the mark); PUNCHLINE → `punchline`, word for word, its emoji included.
A LIST with headers ("YOU CONTROL:" / "YOU DON'T:") is two columns: the usual list, not this layout.

## Check before you hand it over

- Every number, span and place name matches the member's copy exactly ("West Palm Beach", and 2015-2025 is
  eleven years). Their copy is the truth: flag a sum that doesn't add up, don't fix it silently.
- Money tables show their assumptions on screen (rate, term, down payment) in the `small` line.
- Compliance: payments, rates, down payment and term are trigger terms. Remind the member to run a money table
  past compliance before posting.

Examples (GO coaches): "History of Mortgage Rates" (2.35M plays), "Your Bank hopes you NEVER learn this" with
"APPLY TO PRINCIPAL ONLY" (2.25M), "How much salary to afford a home" (a lookup table, "Save this for later").
