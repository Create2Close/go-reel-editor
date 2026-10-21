#!/usr/bin/env bash
# setup.sh: installs what the GO! Reel Editor needs, on macOS or Windows (Git Bash, the shell Claude Code uses).
# Claude runs it when a member says "set me up". Safe to re-run: it skips what is already there.
#
#   needs:  ffmpeg (video), uv (runs the editor's Python; it fetches its own Python)
#   then:   builds the editor's environment and checks everything with `gre doctor`
#   yaps:   the transcriber (WhisperX, ~4 GB) installs itself later, the first time a member edits a yap
#
# Exit codes (Claude reads them; the output says exactly what to do):
#   0 ready · 1 something needs the member (the output names it) · 2 restart Claude Code, then run it again
set -uo pipefail
SKILL="$(cd "$(dirname "$0")" && pwd)"
ORIG_PATH="$PATH"
say()  { printf '%s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
PENDING=0

case "$(uname -s 2>/dev/null || echo unknown)" in
  Darwin) OS=mac ;;
  MINGW*|MSYS*|CYGWIN*) OS=windows ;;
  Linux) OS=linux ;;
  *) say "Unrecognised system. On Windows, Claude Code runs this through Git Bash (install Git for Windows)."; exit 1 ;;
esac
say "== GO! Reel Editor setup ($OS) =="

# ── macOS: Homebrew for ffmpeg; uv from Homebrew or its own installer ─────────────────────────────
if [ "$OS" = mac ]; then
  for b in /opt/homebrew/bin /usr/local/bin "$HOME/.local/bin"; do
    [ -d "$b" ] && case ":$PATH:" in *":$b:"*) ;; *) PATH="$b:$PATH" ;; esac
  done
  export PATH
  if ! have ffmpeg; then
    if ! have brew; then
      say ""
      say "ONE STEP FOR YOU: this Mac needs Homebrew (the standard Mac installer for free tools)."
      say "It asks for your Mac password, so Claude can't type it for you. Open the Terminal app, paste this, press"
      say "Return, type your Mac password when asked (nothing shows while you type: that's normal), and wait"
      say "until it says 'Installation successful' (5-10 minutes):"
      say ""
      say '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
      say ""
      say "Then come back and say: continue setup"
      exit 1
    fi
    say "  > installing ffmpeg (Homebrew, a few minutes)..."
    brew install ffmpeg || { say "  ! brew install ffmpeg failed: read the message above, then say 'continue setup'"; exit 1; }
  else
    say "  ok ffmpeg"
  fi
  if ! have uv; then
    if have brew; then say "  > installing uv (Homebrew)..."; brew install uv
    else say "  > installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh; PATH="$HOME/.local/bin:$PATH"; fi
  else
    say "  ok uv"
  fi
  # Make the tools visible to EVERY later session, not just this run. Right after Homebrew installs (or for a second
  # user on a Mac that already had Homebrew), /opt/homebrew/bin is not on the login PATH, so every editor command
  # after setup would fail with "uv: command not found". Write it into the login profile once.
  PROFILE="$HOME/.zprofile"; case "${SHELL:-}" in */bash) PROFILE="$HOME/.bash_profile" ;; esac
  for b in /opt/homebrew/bin /usr/local/bin; do
    if [ -x "$b/brew" ] && ! printf '%s' ":$ORIG_PATH:" | grep -q ":$b:"; then
      if ! grep -qsF "$b/brew shellenv" "$PROFILE"; then
        printf '\n# Homebrew on PATH (added by GO! Reel Editor setup)\neval "$(%s/brew shellenv)"\n' "$b" >> "$PROFILE"
        say "  ok added Homebrew to $PROFILE (new sessions see ffmpeg and uv)"
      fi
      break
    fi
  done
  if [ -x "$HOME/.local/bin/uv" ] && ! printf '%s' ":$ORIG_PATH:" | grep -q ":$HOME/.local/bin:" \
     && ! grep -qsF '.local/bin' "$PROFILE"; then
    printf '\n# uv on PATH (added by GO! Reel Editor setup)\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$PROFILE"
    say "  ok added uv to $PROFILE"
  fi
fi

# ── Windows: winget, then pull the new tools into this session's PATH ────────────────────────────
if [ "$OS" = windows ]; then
  refresh_path() {
    local d L
    L="$(cygpath -u "${LOCALAPPDATA:-}" 2>/dev/null)"
    for d in "$L/Microsoft/WinGet/Links" "$(cygpath -u "${USERPROFILE:-}" 2>/dev/null)/.local/bin" \
             "$L"/Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin; do
      [ -d "$d" ] && PATH="$d:$PATH"
    done
    export PATH
  }
  refresh_path
  if ! have winget && ! have winget.exe; then
    say "winget is missing: install 'App Installer' from the Microsoft Store, then say 'continue setup'."
    exit 1
  fi
  wg() { winget install --exact --id "$1" --accept-source-agreements --accept-package-agreements \
           --disable-interactivity >/dev/null 2>&1; return 0; }
  if have ffmpeg; then say "  ok ffmpeg"; else say "  > installing ffmpeg (winget, a few minutes)..."; wg Gyan.FFmpeg; fi
  if have uv; then say "  ok uv"; else say "  > installing uv (winget)..."; wg astral-sh.uv; fi
  refresh_path
  for t in ffmpeg ffprobe uv; do
    have "$t" || { say "  ! $t is installed but this session can't see it yet"; PENDING=1; }
  done
  # Controlled Folder Access (Windows Security > Ransomware protection) silently blocks Python from writing in
  # Documents, Desktop, Pictures, Videos and OneDrive; the error reads "No such file or directory".
  CFA="$(powershell.exe -NoProfile -NonInteractive -Command '(Get-MpPreference).EnableControlledFolderAccess' 2>/dev/null | tr -d '[:space:]')"
  if [ "$CFA" = "1" ]; then
    say "  ! Controlled Folder Access is ON. Keep your reels folder OUTSIDE Documents, Desktop, Pictures, Videos"
    say "    and OneDrive (for example C:\\Users\\<you>\\Reels), or the editor can't save files there."
  fi
fi

if [ "$OS" = linux ]; then
  if ! have ffmpeg; then
    SUDO=""; [ "$(id -u)" != 0 ] && SUDO="sudo -n"
    if have apt-get && $SUDO true 2>/dev/null; then
      say "  > installing ffmpeg (apt)..."
      $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null 2>&1
      $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg >/dev/null 2>&1
    fi
    have ffmpeg || { say "ONE STEP FOR YOU: install ffmpeg (it needs your password): sudo apt install -y ffmpeg"; say "Then say: continue setup"; exit 1; }
  else
    say "  ok ffmpeg"
  fi
  if ! have uv; then say "  > installing uv..."; curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; PATH="$HOME/.local/bin:$PATH"; export PATH; fi
  have uv && say "  ok uv"
fi

if [ "$PENDING" = 1 ]; then
  say ""
  say "== Almost done =="
  say "Windows only shows newly installed tools to newly opened apps. Quit Claude completely (close the window),"
  say "open it again in the same folder, and say: continue setup"
  exit 2
fi

# ── companion skills: the EZ Reel Writer and the yap writer, next to this skill ─────────────────────────────────
# Installed when missing, updated when this editor put them there, never touching a member's own copy.
SKILLS_DIR="$(dirname "$SKILL")"
case "$SKILLS_DIR" in */.claude/skills) ;; *) SKILLS_DIR="$HOME/.claude/skills" ;; esac
mkdir -p "$SKILLS_DIR"
for c in ez-reel-writer yap; do
  src="$SKILL/companions/$c"; dst="$SKILLS_DIR/$c"
  [ -d "$src" ] || continue
  if [ ! -e "$dst" ] || [ -f "$dst/.from-go-reel-editor" ]; then
    rm -rf "$dst" && cp -R "$src" "$dst" && printf 'installed by the GO! Reel Editor\n' > "$dst/.from-go-reel-editor"
    say "  ok $c skill (writes the copy)"
  else
    say "  ok $c skill (your own copy, kept as it is)"
  fi
done

# ── the editor's own environment (uv fetches Python 3.11/3.12 itself if the computer has none) ────
say "  > building the editor's environment (first time: about a minute)..."
if ! uv sync --project "$SKILL" -q; then
  say "  ! could not build the environment (see above). Check the internet connection and say 'continue setup'."
  exit 1
fi
say ""
uv run -q --project "$SKILL" gre doctor || exit 1
mkdir -p "$HOME/.go-reel-editor" && date > "$HOME/.go-reel-editor/setup-ok"
say ""
say "SETUP DONE."
say "Tell the member: open a NEW session in this same folder (the skills load in new sessions) and paste:"
say "  Get me started with the GO! Reel Editor."
exit 0
