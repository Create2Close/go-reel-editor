# Changelog

Newest first. Date · area · what · why.

## 0.1.3 · 2026-10-21 · writers bundled, welcome starter

- **Companion skills**: setup now installs the EZ Reel Writer and the yap writer next to the editor (`companions/`),
  so one session writes the copy and builds the reel. A member's own copy of either is never overwritten (the
  editor only updates copies it installed, marked `.from-go-reel-editor`). `gre doctor` reports both.
- **Welcome starter**: setup ends by telling the member to open a new session and paste "Get me started with the GO!
  Reel Editor." SKILL.md § 0a answers it: a two-line welcome, a quiet health check, the fewer-pop-ups offer, the
  seven questions, then three ways to start (Writer output, an idea for the Writer, or the practice pack).
- From Cyrus's first full test (all four formats passed).

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
- **Clean-server test** (RunPod, bare Ubuntu 24.04, no ffmpeg/uv/Python): setup to READY with no manual steps, 24 tests
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
