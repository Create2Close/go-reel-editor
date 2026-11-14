# X-reel, listicle, b-roll (a few minutes each)

`gre <command>` means `bash "<skill folder>/gre.sh" <command>`. Read the format's rules first (`formats/x-reel.md`,
`formats/listicle.md`, `formats/b-roll.md`). Keep to the reply rules in SKILL.md.

## Build one

1. **Footage.** They named a clip or photo: use it. They didn't: `gre find` and offer the newest ones as buttons.
   Copy the one they pick into the reel's folder (never move or rename the original).
2. **Write the spec** from their copy, exactly as written, named after the reel
   (`austin-400k-listicle/austin-400k-listicle.json` → the video is `out/austin-400k-listicle.mp4`). Footage paths
   are relative to the spec. Full shapes are at the top of `gre/listicle.py`, `gre/broll.py`, `gre/xreel.py`.
   - **listicle**: `{"clip", "title", "items": [...] or "columns": [...], "small": "Source: ...", "punchline"}`.
     Three to six full-sentence points ("read this first", "save this"): add `"layout": "checklist"`
     (`formats/listicle.md` § The checklist layout).
   - **b-roll**: `{"clip", "blocks": [{"text", "style"}]}`. Styles come from the look (`white`, `black`, `outline`,
     `accent`...). The usual pattern: the set-up line `white`, the twist and the tease `black`.
   - **x-reel**: `{"text": "BREAKING: ...\n\nHere's ... 👇", "image": "news.jpg"}`. The post text is the hook label,
     one or two hook lines and the tease line. The long caption is never on screen. The name, @handle and photo
     come from their profile.
3. **Check a still yourself.** `gre preview <spec>`, then look at the PNG: every word as written, nothing cut off,
   readable, text in the middle band, no text on a face. Fix what is off before they see anything. A `note:` line
   (the b-roll text moved off a face, the clip loops) is worth one line to the member.
4. **Render.** `gre listicle|broll|xreel <spec> [--look clean|bold|serif]`, then `gre qa out/<name>.mp4`.
5. **Hand it over** (SKILL.md § Handing over): the video playing in the chat, where it is saved, then
   "Next: say *caption* for the text to post with it, or tell me what to change."

Show the still instead of the video only when you need them to choose between two versions.

## Change it

One sentence from them, one render from you: "bigger title", "swap the clip", "start the clip 3 seconds later",
"try the bold look", "use this photo instead". Edit the spec, render again, show the new video. Do not re-explain
what changed beyond one line.

## Practice ("make the practice listicle / b-roll / x-reel", "let me practice")

Copy `examples/practice/<format>/` from the skill folder into their Reels folder as `practice-<format>/`, read its
`writer-output.txt`, and build it exactly as above. The X-reel uses THEIR name, @handle and photo from the profile.
Hand it over with buttons: *Try another format* · *Use my own content* · *Make it my style*.
