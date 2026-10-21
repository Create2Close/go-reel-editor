# X-reel

A news story as an X-post card: the member's avatar, name, verified badge and handle, 2-3 lines, one news image,
on black (or white). STATIC: no zoom, no motion, one card held 6-7 s. The full story lives in the caption, so
the reel loops while people read (2.5x plays per viewer). Top-of-funnel reach and speed to news:
"wide but local" (a Texas story with no mortgage content is proper top of funnel).

## What the editor builds

```json
{"text": "BREAKING: Samsung is moving its U.S. headquarters to Plano, Texas.\n\n1,000 employees relocating to DFW by end of 2026.\n\nHere's what just happened 👇",
 "image": "news.jpg", "mode": "dark"}
```

Name, handle and avatar come from the member's profile (`gre profile`). `"crop_y": 0-1` moves the crop of a tall photo (0 top, 0.2 default); `"image_header"` adds a small strip
above the image; `"mode": "light"` gives the white version.

## Rules

- **The post text is 2-3 lines, never a block**: the hook label (BREAKING / JUST IN / REPORT, rotated, never
  the same on consecutive posts), the most dramatic verified fact, an optional stakes line, and the tease
  ending in 👇 (varied every post: "Here's who's behind it 👇"). A paragraph on screen gets swiped (the engine
  warns over 4 lines).
- **The image sells the headline.** A real news photo of the place, the building, the person. Landscape crops
  to the card width; a tall photo is centre-cropped.
- **The caption** (from the Writer: sectioned, ending "What this means for [market] Realtors" and "Bottom
  line", under 1,800 characters) goes in `out/<name>.caption.txt`, never on screen.
- **Static, 6-7 s, silent.** No slow zoom, ever (Cyrus, 2026-10-21).
- **The whole card (avatar, name, text, image) sits inside the reel safe zone**: the top 14 %, bottom 35 % and
  sides 6 % stay clear (x65-1015, y300-1248 on 1080x1920), which also clears the Facebook 4:5 and Instagram 3:4
  feed crops. The engine centres the card there, crops a tall photo to fit, and refuses anything outside it.
- **Organic only: never use X-post styling inside a paid ad.**
- Only facts from the article. If the member's text states something the article doesn't, flag it.
