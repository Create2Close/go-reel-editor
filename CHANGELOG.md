# Changelog

Newest first. Date · area · what · why.

## 0.2.1 · 2026-11-14 · talking videos: the editor hears the take, and listens back to its cut

The first real talking-video test of 0.2.0 came back bad: a line played twice, the captions ran seconds ahead of
the words, and three seconds of silence sat in the middle. One cause: the editor cut from a transcript it never
checked against the sound. Whisper had folded three takes of a line into one and timed the rest against the wrong
audio. (The first three bullets are what Claude shows a member as "what's new".)

- **It hears every take**: the waveform is cut into stretches of speech and each one is transcribed on its own,
  asked for every word as said. A second take, a wrong number or a restart can no longer vanish from the
  transcript or be timed onto another take. A stretch with more sound than words is listened to a second way, and
  a noise is no longer written down as "Thank you." (`gre/hear.py`, `gre/_whisperx_worker.py`).
- **It listens back to its own cut**: `gre yap cut` plays the cut to the transcriber and compares it word for word
  with what the cut is meant to say. A line that plays twice, words that are missing and dead air are `FIX` lines,
  with the place in the take and what to change; a draft with one open says `NOT READY TO SHOW`, and a final fails
  its check. A clipped word or number next to a cut is a `FIX` too; a word that was only heard another way, where
  nothing was cut, is a note (`gre/listen.py`, `edit/heard.json`).
- **Rates get %, money gets $, and the comment word stands out**: captions write 7.11%, $79 a month and $400,000
  ("seven point one one", "940 dollars" and "400 thousand dollar loan" included), and the word a call to action
  asks for is in bold capitals ("Just comment **RATES**"). The caption check enforces both; `#ok` in
  `captions.txt` leaves a number or a word alone.
- **No dead air**: pauses of half a second or more are closed where the WAVEFORM is silent, not where the word
  times say, so a mistimed word cannot leave a gap. A piece of sound no kept word belongs to is left out.
- **No stray sounds where a retake was cut**: the aligner starts a word the moment the one before it ends, so
  after "Mortgage rates, (pause) mortgage rates just dropped" the kept "mortgage" began with the s of the cut
  "rates,". Word boundaries now sit where the sound puts them (a gap inside a one-word span is the gap between
  two words), a cut's start no longer reaches back into a cut word, and a short burst set apart by a gap next to a
  cut word is a `FIX` in the listen-back, with the stretch to drop. (Cyrus, 2026-11-14: four of them in one draft,
  all after back-to-back retakes.)
- **A breath is a pause**: the cut tells speech from sound that is only above the room. Half a second with nothing
  louder than a breath is tightened like silence, and a cut ends at the end of the speech (soft endings kept), not
  at the end of the breath after it.
- **Numbers keep their whole length**: figures are timed the way they are said ("7.4%" as "seven point four
  percent", "$400,000" as "four hundred thousand dollars"), and every edge of a cut runs to the end of the sound the
  word sits in. Before, a rate could lose everything after its first digit.
- **`"drop"` in `keep.json`**: a stretch of the take, in seconds, that never plays whatever the words say: the way
  to cut something the transcript has no words for.
- **The first cut knows more repeats**: a restart that finishes its last word ("and that, and that's") and a short
  line said twice ("That's October. That's October.").
- **A script matches however its numbers are written**: "seven point one one" in `script.txt` finds the take
  the transcript wrote as "7.11%", and the caption shows 7.11%. A second go inside a scripted line ("...walked away
  from. Let me do that again. The number you walked away from is already gone.") keeps the second go. The last
  word of a line heard another way is no longer dropped.
- **Bold reads as bold**: bold caption words are drawn a touch fatter in every look (`captions.bold_fat` in a look,
  0.02 of the size by default). One weight step was invisible at phone size, and the serif look had no bold at all.
- Fixed: digit-by-digit numbers were added up ("eight seven five" became 20), and "400 thousand" became
  "400 1000".
- A transcript made before this version is reused as it is, with a note. `gre yap start <folder> --retranscribe
  --force` hears the take again.

## 0.2.0 · 2026-11-13 · easier (install, first reel, replies, yaps) and news graphics

Members said the editor felt complicated. This release is about that. (The first three bullets are what Claude
shows a member as "what's new".)

- **Easier install: no Terminal, no password, no restart**: setup installs `uv` with its own installer and fetches
  ffmpeg by itself, so a Mac no longer needs Homebrew and Windows no longer needs winget or a restart. The old route
  stays as an automatic fallback. A new launcher, `gre.sh`, finds the tools whatever the session's PATH is.
- **Shorter replies, one next step, buttons to click**: SKILL.md now opens with nine reply rules (five short lines,
  one question at a time, one `Next:` line, choices as buttons, plain words, no narration).
- **Talking videos in one stop**: Claude does the cut, the captions and the title and shows one finished first
  version; the member says what to change or "looks good". "Step by step" is still there on request, and the
  numbered transcript only appears when they ask what was cut.
- **A checklist listicle**: `"layout": "checklist"` in a listicle spec draws one centred column, every line in its
  own rounded box: a coloured title, three to six full-sentence points with a check mark, and a closing line that
  cuts in three quarters through. Long points wrap into two even lines; the length follows the reading (about six
  words a second, 7 to 12 s). Drawn by the look (optional `listicle.checklist` block; older looks get numbers from
  their own type size). The usual list and its columns are unchanged. `formats/listicle.md` § The checklist layout.
- **X-reel photos shown whole**: the name, handle and post text stay inside the reel safe zone, and the photo
  alone may run below it, down to the feed-safe line. A landscape photo is no longer cropped; a tall one keeps
  most of its height. Before, the photo was cut to whatever strip was left above the caption area.
- **B-roll text keeps off faces**: the editor looks for faces in the clip or photo and, when the lines would cross
  one, moves the whole block to the nearest clear spot in the feed-safe band (slightly smaller type only when that
  is what it takes), and says so in a `note:` line. `gre preview` shows the same placement. `"center_y"` or
  `"avoid_faces": false` in the spec switches it off; footage with no face comes out exactly as before.
- **Graphics on talking videos**: a headline card (the article's headline, outlet and date, with a highlighter
  swipe across the key phrase), the rate chart (Freddie Mac's weekly 30-year average, last 52 weeks, the line draws
  itself and the number counts up, with its source and date), a stat card (one number, or from → to) and a lower
  third (name, title, one line: never a default, only for a member who says yes, and never a reason to hold a reel).
  Each lands on the words the member says and is drawn in
  their own look: their font, their card, their colours. One file per yap, `edit/graphics.json`; `gre yap graphics`
  checks it (timing, room above the head, nothing on the face, the title or the captions) and draws a preview sheet;
  `gre yap draft` and `gre yap final` put the graphics in, and the final check fails while one covers the face.
  `guide/graphics.md` has the steps and the rule that matters: never invent a headline, a date or a number.
- **`gre headline <link>`** reads an article's headline, outlet and date from the page itself (or says it could
  not); **`gre rates`** fetches the weekly 30-year fixed average (FRED, then Freddie Mac's own file), saves it for
  offline use, and prints the latest, a week, four weeks and a year ago, the 52-week high and low, and with
  `--payment 400000` the monthly payment at each.
- **Looks draw graphics too**: an optional `graphics` block in a look (`looks/README.md`); without it the card
  comes from the rest of the look, so every existing look works unchanged. The sample sheet shows them.
- **Two questions before the first reel, not seven**: name and @handle, and a profile photo; then the practice
  X-reel with their own name on it. Colours, fonts and the look come after the first reel; role and market are asked
  the first time they want something written.
- **Claude finds the footage**: `gre find` lists the newest videos and photos in Reels, Downloads, Desktop and
  Movies, so members pick from buttons and never move files or upload anything.
- **Update offers**: `gre update --check` (at most once a day) tells Claude when a new version is out; it offers it
  with one line on what is new. `setup.sh --update` does the update.
- **A short SKILL.md**: 3,300 words became a 1,400-word router plus four guides in `guide/` (setup, the welcome and
  looks, EZ reels, yaps), read only when needed.
- **MIT licence** (Create2Close).

## 0.1.7 · 2026-11-10 · footage goes in the folder, not the chat box

- **No uploads, any size** (SKILL.md § 2, § 7): a member hit an upload limit (about 400 MB) dragging a phone video
  into the chat box. The editor never needs that upload: it reads files straight from the folder. Claude now says
  where to put footage every time it asks for some ("your Reels folder in Finder / File Explorer, not this chat
  box"), and when a member attaches a video anyway or hits "file too large", it finds the file on disk (Reels,
  Downloads, Desktop, Movies), confirms it, and copies it into the reel's folder.
- README, the welcome's yap line and the session kit say the same.

## 0.1.6 · 2026-10-22 · house photos for the practice pack

- **Practice images are real-estate scenes, not Zoom backgrounds**: the listicle now builds over a neighbourhood
  street from above (`neighborhood.jpg`) and the X-reel's news image is a house front (`house.jpg`), both generated
  stock-style photos with no people, signs or text. The GO! Zoom backgrounds (`office.jpg`, `news-photo.jpg`) are gone.

## 0.1.5 · 2026-10-22 · privacy pass

- **No real people in the repo**: the practice b-roll photo (an astronaut with a real face) is replaced by NASA's
  public-domain "View of Moonset" (iss061e003881). The listicle and X-reel practice images are GO! graphics with no
  people. Credits in `examples/practice/README.md`.
- **No names**: the format docs and the bundled writers' examples describe the reels (plays, copy, mechanics) without
  naming the coaches or creators behind them; the yap research notes list creator counts, not handles.
- Scanned the full history for keys and tokens: none.

## 0.1.4 · 2026-10-22 · everything in the chat, quick previews, captions to copy, Team/Enterprise

- **The chat is the review** (SKILL.md § 5b): stills, drafts, the yap's numbered transcript, caption lines, title
  options and the finished reel all appear in the conversation. Videos and stills go out with the desktop app's
  file tool so they open and play there (a clickable link otherwise). Members never open a .md or .txt.
- **Yap drafts are quick previews**: `gre yap draft` renders 540x960 with a fast encode (veryfast, CRF 26), so a
  review copy arrives fast and plays smoothly in the chat; only `gre yap final` renders full quality. It prints the
  numbered transcript for the chat (clip names, no internal word numbers); the full sheet stays in `edit/drafts/`
  for Claude.
- **Post caption on request** (§ 5c): offered at every hand-over and shown in a code block with a copy button. EZ
  reels use the Writer's caption word for word; a yap uses its script's caption or a drafted one. The
  `out/<name>.caption.txt` file is gone.
- **Reel naming**: the spec is named after the reel, so the video is `out/<reel>.mp4`, not `out/spec.mp4` (flagged by
  both the Sonnet and the Haiku practice runs, which otherwise passed QA word for word).
- **Plans**: Pro, Max, Team or Enterprise (Team/Enterprise: the admin turns Claude Code on). From Cyrus's install test.

## 0.1.3 · 2026-10-21 · writers bundled, welcome starter

- **Companion skills**: setup now installs the EZ Reel Writer and the yap writer next to the editor (`companions/`),
  so one session writes the copy and builds the reel. A member's own copy of either is never overwritten (the
  editor only updates copies it installed, marked `.from-go-reel-editor`). `gre doctor` reports both.
- **Welcome starter**: setup ends by telling the member to open a new session and paste "Get me started with the GO!
  Reel Editor." SKILL.md § 0a answers it: a two-line welcome, a quiet health check, the fewer-pop-ups offer, the
  seven questions, then three ways to start (Writer output, an idea for the Writer, or the practice pack).
- From Cyrus's first full test (all four formats passed). Auto mode is the default permission mode, so the
  "stop asking Allow?" offer now only comes up if the member was actually prompted.

## 0.1.2 · 2026-10-21 · static X-reels, PATH fix, practice pack

- **Practice pack** (`examples/practice/`): a listicle, a b-roll and an X-reel with Writer output and GO! images, so a
  member can say "make the practice listicle" before they have content. All three render and pass QA.

(see the first two bullets below)

## 0.1.1 · 2026-10-20 · onboarding + clean-server test

- **Onboarding intake** (SKILL.md § 0b): name, Instagram @handle, profile photo, role/market/audience, brand colours
  (or a logo: `gre colors`), fonts (`gre font` downloads free Google Fonts; paid fonts map to the closest free one), a
  reel to match, caption style. `gre look new` builds the member's own look and a sample sheet to approve.
- **Optional allow-list** offered after setup, so the editor's own commands stop asking "Allow?".
- **Photo backgrounds** for listicles and b-roll (a still with a slow push-in). X-reel tall photos crop from the top.
- **Setup keeps tools on PATH**: on a Mac it writes Homebrew (and a ~/.local/bin uv) into the login profile, so every
  later session finds ffmpeg and uv. Before, a fresh Homebrew install or a second Mac user saw "uv: command not found".
- **X-reels are static** (Cyrus, 2026-10-21): no zoom, 6-7 s, the whole card centred inside the reel safe zone
  (top 14 %, bottom 35 %, sides 6 % clear: x65-1015, y300-1248), checked on every render and in the tests.
- **Clean-server test** (a bare Ubuntu 24.04 cloud server, no ffmpeg/uv/Python): setup to READY with no manual steps, 24 tests
  pass, the full yap line (transcribe on GPU, cut, draft, captions, final) QA PASS at -17.8 LUFS. Two fixes from it:
  Linux setup now installs ffmpeg itself (root / passwordless sudo); the transcriber ignores a machine-wide
  `HF_HUB_ENABLE_HF_TRANSFER=1` that crashed the model download.

## 0.1.0 · 2026-10-20 · first pilot (GO! session, Thursday 2026-10-22)

- **EZ reels**: listicle, b-roll and X-reel renderers, standalone: bundled open-licence fonts, Noto Color Emoji when Apple's emoji font is absent (Windows), looks from the
  skill or `~/.go-reel-editor/looks`, the member's name/handle/avatar from a profile. Guards: the feed-safe band
  (y300-1600), 14 rows max, 4 b-roll blocks max, warnings for long lines and a missing 👇.
- **Looks**: `clean` (default), `bold`, `serif`, each with b-roll, listicle, X-reel, caption and title styles.
- **Yap line**: local WhisperX transcription (installed on first use); a proposed cut (scripted: the last complete
  take of every script line, 100 % word agreement with an editor's human lock on a real scripted yap when given
  the locked words; unscripted: fillers, restarts and repeated sentences out, no false hits on a clean read);
  waveform-measured edges and tightened pauses; one-pass render (any number of clips, automatic wide/tight
  framing at every cut, captions, title, 15 ms crossfades, 80 Hz high-pass, measured gain to -17 LUFS into a
  -6 dBFS limiter), audio within half a frame of picture in every segment; numbered-transcript drafts (L#/R#)
  for lock-and-patch notes; captions chunked by a per-sentence optimiser and checked against the house rules
  (sentence ends, small words, numerals, Realtor, periods, width) by sequence alignment; the title fitted above
  the head (face detection), over hair/hat, or under the captions, never on the face.
- **Install**: `setup.sh` for macOS (Homebrew) and Windows (winget, Git Bash), `gre doctor`.
- **Tests**: 23, on synthetic footage.
