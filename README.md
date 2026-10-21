# GO! Reel Editor

A Claude skill that edits short vertical reels on your own computer, at no extra cost beyond your Claude Pro or Max plan: **X-reels, listicles, b-roll
reels and yaps**. You talk to Claude; Claude does the editing. No editing app, no paid services, nothing
uploaded anywhere.

Made by Cyrus Zed for the GO! Coaching community. Pairs with the **EZ Reel Writer** (writes X-reels, listicles
and b-rolls) and the **yap** skill (writes yaps): the writers write, the editor builds.

## What you need

- A Claude **Pro or Max** plan and the **Claude desktop app** (its **Code** tab, set to **Local**).
- A Mac or a Windows PC. About 1 GB free for the editor; about 4 GB more the first time you edit a yap.
- Mac only: Homebrew (the setup tells you the one line to paste if you don't have it).

## Install (one sentence)

Open the Claude desktop app → **Code** → pick a folder for your reels (on Windows, NOT inside Documents,
Desktop or OneDrive; `C:\Users\<you>\Reels` is perfect) → paste:

> Install the GO! Reel Editor from https://github.com/Create2Close/go-reel-editor and set me up.

Claude installs it, then sets up the open-source tools it needs (10-15 minutes the first time). Update later with
"update the reel editor".

## Use it

- "Make this a listicle" + paste the EZ Reel Writer output + drop a clip in the folder.
- "Make this a b-roll reel" + the Writer's on-screen text + a clip.
- "Make this an X-reel" + the Writer's post + the news image.
- "Edit my yap" + your raw takes in a folder (+ your script as `script.txt` for exact captions).
  You'll get a draft to watch ("put back the part about…", "cut 0:12 to 0:14"), then captions to approve,
  then a title to pick.

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

Follow `setup.sh`'s exit code as `SKILL.md` § 0 describes (1 = the user does one step, 2 = restart Claude).
When it prints SETUP DONE, tell the user to start a **new** session in their reels folder (the skills load in new
sessions) and paste: **Get me started with the GO! Reel Editor.** Setup also installs the two companion writer
skills, `ez-reel-writer` and `yap`, unless the user already has their own copies.

**Updating:** `git -C ~/.claude/skills/go-reel-editor pull && bash ~/.claude/skills/go-reel-editor/setup.sh`
(a tarball install: download it again over the old folder).

## For developers

`gre/` is the engine (Python: Pillow, NumPy, OpenCV; ffmpeg does the video). `uv run --group dev pytest -q`
runs the tests on synthetic footage. Yap transcription is WhisperX (Whisper large-v3 + wav2vec2 alignment) in
its own environment under `~/.go-reel-editor/`, installed on first use. Fonts are SIL OFL (see `looks/fonts/`).
