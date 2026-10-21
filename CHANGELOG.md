# Changelog

Newest first. Date · area · what · why.

## 0.1.1 · 2026-10-20 · onboarding + clean-server test

- **Onboarding intake** (SKILL.md § 0b): name, Instagram @handle, profile photo, role/market/audience, brand colours
  (or a logo: `gre colors`), fonts (`gre font` downloads free Google Fonts; paid fonts map to the closest free one), a
  reel to match, caption style. `gre look new` builds the member's own look and a sample sheet to approve.
- **Optional allow-list** offered after setup, so the editor's own commands stop asking "Allow?".
- **Photo backgrounds** for listicles and b-roll (a still with a slow push-in). X-reel tall photos crop from the top.
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
