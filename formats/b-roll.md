# B-roll reel

On-screen text over real footage of the member's life; nobody talks to camera. **The on-screen text is the
tease. The caption is the payoff. They never do the same job twice.** The belief format: the one EZ reel where a
call to action earns its keep (soft close is still the default).

## What the editor builds

```json
{"clip": "reading.mov", "start": 2.0,
 "blocks": [{"text": "I almost told this buyer to wait…", "style": "white"},
            {"text": "then we ran the real numbers", "style": "black"},
            {"text": "Here's what changed my mind:", "style": "black"}]}
```

Each block appears in turn (2.4 s apart) and stays to the end. `"at": 1.5` pins a block's time; `"y": 0.4`
pins its height (0 top, 1 bottom). Styles come from the look: `white` (black on white box), `black` (white on
black box), `outline` (no box, white with a dark edge).

## Rules

- **2-3 lines** (4 only rarely; the engine refuses 5). The standard shape:
  1. setup (a situation, a credential, a surprising claim), often ending in "…"
  2. the twist (contrast, stakes, the sharpening detail)
  3. the tease, ending in ":" or 👇, naming what the caption delivers without delivering it.
- The last line sends viewers to the caption, directly or by tease.
- 4-8 words a line: each reads in under 2 s.
- **Footage is proof, not wallpaper**: a shot that shows the content being true (reading a book for a habits
  post, the family trip for a step-away post). One steady phone shot, 6-8 s.
- **7 s** unless the member asks otherwise. Silent: the sound goes on in the app.
- Text stays in the feed-safe band (the engine refuses anything outside it).

## Check before you hand it over

- The on-screen words are exactly the member's (or the Writer's) ON-SCREEN TEXT block.
- The last line is readable for at least 1.5 s before the end (the engine warns).
- The caption goes in `out/<name>.caption.txt` exactly as written. It opens with NEW information: if it repeats
  the tease, say so.

Examples (GO coaches): Amir Syed "21 habits to be incredible at sales:" over him reading (all 21 in the caption);
"One day, you'll disappear for a month… / and your business won't notice." over his family trip (no CTA, best
engagement); Steve Beskid "I only have one regret in business: / I was a terrible leader / Here's what I got wrong 👇".
