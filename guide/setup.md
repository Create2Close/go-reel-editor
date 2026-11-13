# Setup, updates and fixes

`gre <command>` means `bash "<skill folder>/gre.sh" <command>`. Keep to the reply rules in SKILL.md: short, plain
words, one `Next:` line.

## Set up ("set me up", "install", "continue setup", or `setup-ok` is missing)

Say one line first: "Setting up. About 10 minutes the first time, and you don't need to do anything." Then run:

```bash
bash "<skill folder>/setup.sh"
```

It installs what the editor needs on its own: no Terminal, no password, no restart in the normal case. Follow its
exit code:

- **0** ready. It ends with `SETUP DONE.` and the starter line below.
- **1** the member has to do one thing (rare: the automatic route failed and it fell back to the manual one). Relay
  the instructions it printed, exactly, in plain words. Then wait for "continue setup".
- **2** Windows needs a restart (rare, same fallback): "Close Claude completely, open it again in the same folder,
  and say *continue setup*."

**After a first install,** tell the member in two lines:
"You're set up. Start a new session in this folder and say: **Get me started with the GO! Reel Editor.**"
(The editor and its two writer skills load in a new session.) If this session already has the skill loaded and the
member was only repairing or updating, skip that and carry on.

## Update ("update the reel editor", or they accepted an update offer)

```bash
bash "<skill folder>/setup.sh" --update
```

It prints `UPDATED to <version>` or `ALREADY UP TO DATE`, then checks everything. Tell them in one line what is new
(the lines `gre update --check --force` printed), and that a new session picks up the new version.

## Fewer pop-ups (only if they were asked "Allow?")

Claude Code's default Auto mode runs the editor's commands without asking, so most members never see a prompt: don't
bring it up. If they did get "Allow?" prompts, or say they are annoying, ask once (buttons: *Yes, stop asking* ·
*Keep asking*): "Want me to stop asking permission for the editor's own commands? Only this editor's, nothing else."
On a yes, add these two entries to `permissions.allow` in `~/.claude/settings.json` (create the file or the list if
missing; keep everything already there), with the real skill path:
`"Bash(bash <skill folder>/gre.sh:*)"` and `"Bash(bash <skill folder>/setup.sh:*)"`. They apply from the next session.

## "What's wrong?" (or "it's not working")

Run `gre doctor`, read the last error in this session, and say in two plain lines what is wrong and the one thing
you will do (or they must do). Then do it.

| What you see | What to do |
|---|---|
| `PROBLEM: the editor is not set up yet` or a tool is MISSING | Run setup (above). |
| `PROBLEM: ... outside the feed-safe band` | Too much text for the frame. Offer to cut a line or shorten it. |
| "File too large", "upload limit", or a video stuck uploading in the chat | They dragged it into the chat box. No upload is needed: `gre find`, then copy it in (SKILL.md § Footage). |
| A clip won't read | `gre doctor`, then setup again. |
| A yap sounds clipped at a cut | Widen that piece by one word in `edit/keep.json`, re-run the cut and show the new draft. |
| Windows: "No such file or directory" for a folder that exists | Controlled Folder Access. Their Reels folder must be outside Documents, Desktop, Pictures, Videos and OneDrive (`C:\Users\<name>\Reels`). |
| The yap transcriber download stopped | Check the internet and run the same step again: it continues. |
| "Not available on your plan" | Claude Code needs Pro, Max, Team or Enterprise. On Team or Enterprise the admin turns Claude Code on. |
| Anything else | One line on what happened, one on what you'll try. Try it. Still stuck: a screenshot in the GO! community, tag Cyrus. |
