# Yap: raw takes to a finished reel, with one stop

`gre <command>` means `bash "<skill folder>/gre.sh" <command>`. Read `formats/yap.md` first: its cut, caption and
title rules are the job. Keep to the reply rules in SKILL.md.

**The default is one stop.** You do the cut, the captions and the title yourself and show ONE finished first
version. They say what to change, or "looks good". Only when a member asks to go "step by step" do you stop after
each stage (last section).

## 1. Start

- **Footage.** They named a folder: use it. Otherwise `gre find --kind video`, offer the newest takes as buttons, and
  copy the ones they pick into a folder named after the topic (`buydown-yap/`). A word-for-word script goes in the
  same folder as `script.txt` (word for word only, not an outline): the cut and the captions then follow it.
- **The first yap ever on this computer** installs the transcriber: about 4 GB, 10 to 20 minutes, once. Tell them
  before you start, in one line, and that every yap after that is quick.
- `gre yap start <folder>`: it transcribes on this computer and proposes a cut. With a script, the last complete
  take of every line is already kept. Without one, fillers, restarts and repeated sentences are already out.
  It listens to every stretch of speech on its own, so the second and third take of a line, a wrong number and a
  restart are all in the transcript, each where it was said.

## 2. Make the cut (your judgement)

Read `edit/words.md` (every word numbered) and `edit/keep.json`. Edit `keep.json`: `segments` are the word ranges
that play, in playing order; every judgement cut gets an entry in `cuts` with a short reason ("aside", "sign-off
after the call to action"). Then `gre yap cut <folder>`. Pauses are tightened and the edges measured automatically.

**The cut is then listened back.** `gre yap cut` plays its own cut to the transcriber and compares what it hears,
word for word, with what the cut is meant to say. It takes about as long as the cut. Read what it prints:

- `listened back: the cut plays the words it is meant to` : go on.
- `FIX ... plays words that are not in the cut` : a retake or a stumble is still in there. Cut those words in
  `keep.json`; when the transcript has no words for them, add the stretch the line names to `"drop"`
  (`"drop": [{"from": 58.6, "to": 61.4, "why": "an aborted take"}]`, seconds of the clip). Run `gre yap cut` again.
- `FIX ... is not heard there` : the words are clipped or sit somewhere else in the take. Look at that spot in
  `edit/words.md` and keep the right range.
- `FIX ... a stray sound` : where a restart was cut ("Mortgage rates, | mortgage rates just dropped"), the end of
  the cut word (its s, its t) is still playing before the kept one. Add the stretch the line names to `"drop"`.
  If the short sound IS the kept word (a "So," before a pause), list that word in `"heard_ok"` instead.
- `FIX ... is dead air` : say so and send the line; the cut should have closed it by itself.
- `FIX ... a number may be clipped or misheard` / `... is not heard there` on one word: there is a cut right next
  to it. Look at that word's times in `edit/words.md`; if the piece really ends after the whole word, list the word
  in `"heard_ok"` in `keep.json` (`"heard_ok": ["7.11%"]`) and run `gre yap cut` again (it does not listen twice).
- `note` lines need nothing (a word "not heard clearly" where nothing was cut was only said softly).

**Never show a draft while a FIX line is open.** A member should not be the one who finds a repeated line.

## 3. Captions

`gre yap captions <folder>` writes a first version to `edit/captions.txt` and checks it. Read it and fix it by hand:
natural phrases, one line each, **bold** on about one word every five seconds (the stressed word), mishears
corrected in the text. Run it again until no `FIX` lines remain. Look at `edit/captions-preview.png` yourself.

Two things the first version already does, and the check enforces: **a rate takes % and money takes $** (7.11%,
$79 a month, $400,000, never "percent" or "dollars"), and **the word a call to action asks for is in bold
capitals** ("Just comment **RATES**"). A number that is neither, or a word that is not a comment word, goes on a
`#ok` line in `captions.txt` (`#ok 7.11 questions`) and is left alone.

## 4. Title

Pick the best title yourself (the rules are in `formats/yap.md` § Title: three to eight words that ADD to the first
sentence). If their script has a visual hook, use that. `gre yap title <folder> "line one" ["line two"]`, then look
at `edit/title-preview.png`: it is the thumbnail. If it says NO CLEAR SPACE, use a one-line version. Keep two
runner-up titles in mind for later.

## 5. Show the first version: THE ONE STOP

They asked for a graphic up front (an article on screen, the rate chart, a number, their name)? Add it now, before
the draft: `guide/graphics.md`. It is part of the one first version.

`gre yap draft <folder>` renders a quick preview with the cut, the captions and the title (a clock sits in the
corner so notes can point at a time). If it prints `NOT READY TO SHOW`, fix the cut first (§ 2). In ONE reply:

- the draft, playing in the chat;
- two or three plain lines on what you did: "I took out two retakes, the aside about your dog, and the sign-off
  after your call to action. 2:18 of takes is now 1:05. Title: *The rate isn't the problem*.";
- buttons: *Looks good, finish it* · *I have notes* · *Other titles* · *Show what you cut*. When the video quotes
  a number or a news story and has no graphic yet, swap *Show what you cut* for *Add a graphic*.

Do NOT paste the numbered transcript unless they pick *Show what you cut* (or ask "what did you cut?"). Then paste
the block `gre yap draft` printed between `=== PASTE INTO THE CHAT ===` and `=== END ===`, as it is.

## 6. Notes

They answer in plain words: "put back the part about my dad", "cut 0:12 to 0:14", "start on the line about rates",
"fix the caption that says cloud", "bigger title", "less zoom". **A note changes only its spot.** Never re-decide
the rest of the cut.

| The note is about | Do |
|---|---|
| What plays (put back, cut, reorder) | Change only that spot in `keep.json` → `gre yap cut` (it listens back again: no FIX lines) → `gre yap captions` (fix only the lines it flags) → `gre yap draft` |
| "It says a line twice", "there's a gap", "the words don't match" | The cut is wrong, not the captions. `gre yap cut` and read its FIX lines (§ 2). If the take was transcribed before 0.2.1, `gre yap start <folder> --retranscribe --force` first, then redo the judgement cuts |
| Caption words or line breaks | Edit `edit/captions.txt` → `gre yap captions` → `gre yap draft` |
| The title | *Other titles*: offer your best three as buttons. Then `gre yap title ...` → `gre yap draft` |
| The zoom | Edit `edit/moves.json` (`"auto": false` turns the automatic moves off) → `gre yap draft` |
| A graphic (add one, move it, full screen, take it off) | `guide/graphics.md`: edit `edit/graphics.json` → `gre yap graphics` → `gre yap draft` |
| The look | `--look <name>` on `captions`, `title` and `draft` |

Show the new draft with one line on what changed and the same buttons. A simple video should not take more than
two or three rounds.

## 7. Finish

On "looks good" (or "locked", "approved", "finish it"): `gre yap final <folder>` renders the full-quality reel with
the sound levelled, and checks it. Hand it over (SKILL.md § Handing over): the video playing in the chat, where it
is saved, and "Next: say *caption* for the text to post with it."

## Step by step (only when they ask for it)

Same commands, with a stop after each stage: show the draft with the cut only (`gre yap draft --no-captions`) and
wait for "locked"; then the captions (show `edit/captions-preview.png` and a draft) and wait for "approved"; then
offer five or six titles in three flavours (contrast, curiosity, straight to the viewer), recommend one, and render
the final when they pick.

## Camera moves

Automatic: every cut alternates a wide and a tight framing (100-103 % / 113-116 %) so jump cuts read as intentional.
Change it only if they ask.
