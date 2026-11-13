# GO! Reel Editor

A Claude skill that edits short vertical reels on your own computer, at no extra cost beyond your Claude plan (Pro, Max, Team or Enterprise): **X-reels, listicles, b-roll
reels and yaps**. You talk to Claude; Claude does the editing. No editing app, no paid services, nothing
uploaded anywhere.

Made by Cyrus Zed for the GO! Coaching community. Pairs with the **EZ Reel Writer** (writes X-reels, listicles
and b-rolls) and the **yap** skill (writes yaps): the writers write, the editor builds.

## What you need

- A Claude **Pro, Max, Team or Enterprise** plan (on Team or Enterprise, your admin must have Claude Code turned on) and the **Claude desktop app** (its **Code** tab, set to **Local**).
- A Mac or a Windows PC. About 1 GB free for the editor; about 4 GB more the first time you edit a yap.

Nothing else to install: no Terminal, no Homebrew, no password. Setup fetches the open-source tools it needs by itself.

## Install (one sentence)

Open the Claude desktop app → **Code** → pick a folder for your reels (on Windows, NOT inside Documents,
Desktop or OneDrive; `C:\Users\<you>\Reels` is perfect) → paste:

> Install the GO! Reel Editor from https://github.com/Create2Close/go-reel-editor and set me up.

Claude installs it and sets everything up (about 10 minutes the first time). Then start a new session and say
**Get me started with the GO! Reel Editor.** Two quick questions, and your first reel is on screen.

Claude tells you when there is a new version. You can also say "update the reel editor" any time.

## Use it

Put your clips, photos and takes in your reels folder (in Finder or File Explorer), not in the chat box: phone
videos are often bigger than the chat's upload limit, and the editor reads them straight from the folder at any size.

- "Make this a listicle" + paste the EZ Reel Writer output + a clip in the folder.
- "Make this a b-roll reel" + the Writer's on-screen text + a clip in the folder.
- "Make this an X-reel" + the Writer's post + the news image in the folder.
- "Edit my yap" + your raw takes in a folder (+ your script as `script.txt` for exact captions).
  You'll get one finished first version to watch: cut, captioned and titled. Say what to change ("put back the
  part about…", "cut 0:12 to 0:14", "other titles") or "looks good".
- On a yap: "put this article on screen" + the link, "show the rate chart", "show 7.40 to 7.11". The headline,
  the weekly 30-year fixed chart (Freddie Mac) or the number appears as you say it, in your own colours and font.

---

## For Claude: installing

Install into the user's Claude skills folder, then run the setup:

```bash
mkdir -p ~/.claude/skills
git clone https://github.com/Create2Close/go-reel-editor ~/.claude/skills/go-reel-editor \
  || (curl -fsSL https://github.com/Create2Close/go-reel-editor/archive/refs/heads/main.tar.gz | tar xz -C ~/.claude/skills \
      && mv ~/.claude/skills/go-reel-editor-main ~/.claude/skills/go-reel-editor)
bash ~/.claude/skills/go-reel-editor/setup.sh
```

Before you start, tell the user in one line that it takes about 10 minutes and they don't need to do anything.
Setup installs `uv` with its own installer and fetches ffmpeg by itself: no Homebrew, no winget, no password. Only if
that fails does it fall back to the manual route and exit 1 (the user does one step) or 2 (restart Claude on
Windows); `guide/setup.md` explains both. When it prints SETUP DONE, tell the user, in two short lines, to start a
**new** session in their reels folder (the skills load in new sessions) and say: **Get me started with the GO! Reel
Editor.** Setup also installs the two companion writer skills, `ez-reel-writer` and `yap`, unless the user already
has their own copies.

**Updating:** `bash ~/.claude/skills/go-reel-editor/setup.sh --update` (pulls the new version, then checks
everything). `gre update --check` says whether there is one.

## For developers

- `SKILL.md` is a short router: how Claude runs the editor, how it talks to members, and which guide to read.
- `guide/` holds the steps (setup, the welcome and looks, EZ reels, yaps); `formats/` holds each format's rules.
- `gre/` is the engine (Python: Pillow, NumPy, OpenCV; ffmpeg does the video). `gre.sh` is the launcher Claude
  calls: it finds `uv` and runs the engine, whatever the session's PATH looks like.
- `uv run --group dev pytest -q` runs the tests on synthetic footage.
- Yap transcription is WhisperX (Whisper large-v3 + wav2vec2 alignment) in its own environment under
  `~/.go-reel-editor/`, installed on first use.

## Licence

MIT (see `LICENSE`): use it, change it, build on it. The bundled fonts are under the SIL Open Font License (see
`looks/fonts/`). The tools setup downloads (uv, ffmpeg, WhisperX and its models) keep their own licences.
