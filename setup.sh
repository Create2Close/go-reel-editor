#!/usr/bin/env bash
# setup.sh: gets the GO! Reel Editor ready, on macOS or Windows (Git Bash, the shell Claude Code uses).
# Claude runs it when a member says "set me up". Safe to re-run: it skips what is already there.
# A normal run needs no Terminal, no password, no Homebrew, no winget and no restart.
#
#   uv       runs the editor's Python (and fetches that Python). Installed with its own installer, into the
#            member's home folder, when the computer has none.
#   ffmpeg   the video tool. It ships inside the editor's environment (the imageio-ffmpeg package), so nothing
#            is installed for it. A computer that already has ffmpeg and ffprobe keeps using its own.
#            Only if that built-in tool does not work here does setup fall back to Homebrew (Mac) / winget (Windows).
#   yaps     the transcriber (WhisperX, ~4 GB) installs itself later, the first time a member edits a yap
#
#   bash setup.sh            set up (or repair) the editor
#   bash setup.sh --update   fetch the newest version into this folder first, then set up
#
# Exit codes (Claude reads them; the output says exactly what to do):
#   0 ready · 1 something needs the member (the output names it) · 2 restart Claude Code, then run it again
#
# The whole script lives in functions and runs from its last line, so an update may replace this file while it
# is running. Written for bash 3.2 (the one macOS ships): no arrays, no associative arrays, no ${var,,}.
set -uo pipefail
SKILL="$(cd "$(dirname "$0")" && pwd)"
say()  { printf '%s\n' "$*"; }
have() { command -v "$1" >/dev/null 2>&1; }
OS=unknown
UV=""
WINHOME=""
WINLOCAL=""
DOCTOR_OUT=""
DOCTOR_RC=1

detect_os() {
  case "$(uname -s 2>/dev/null || echo unknown)" in
    Darwin) OS=mac ;;
    MINGW*|MSYS*|CYGWIN*) OS=windows ;;
    Linux) OS=linux ;;
    *) say "Unrecognised system. On Windows, Claude Code runs this through Git Bash (install Git for Windows)."; exit 1 ;;
  esac
  if [ "$OS" = windows ]; then
    WINHOME="$(cygpath -u "${USERPROFILE:-}" 2>/dev/null | tr -d '\r')"
    WINLOCAL="$(cygpath -u "${LOCALAPPDATA:-}" 2>/dev/null | tr -d '\r')"
  fi
}

version() { tr -d '[:space:]' < "$SKILL/VERSION" 2>/dev/null; }

# ── --update: bring this folder to the newest version, in place ───────────────────────────────────────────────
update_failed() {
  say "COULD NOT UPDATE: no internet, or files in the editor's folder were changed by hand. The editor still works as it is ($(version))."
  exit 1
}

update_skill() {
  local old new tmp src d url
  old="$(version)"
  if [ -e "$SKILL/.git" ]; then
    have git || update_failed
    git -C "$SKILL" pull --ff-only -q >/dev/null 2>&1 || update_failed
  else
    url="${GRE_UPDATE_TARBALL:-https://github.com/Create2Close/go-reel-editor/archive/refs/heads/main.tar.gz}"
    tmp="$(mktemp -d 2>/dev/null)" || update_failed
    if [ -z "$tmp" ] || [ ! -d "$tmp" ]; then update_failed; fi
    if ! curl -fsSL --connect-timeout 10 --max-time 600 "$url" -o "$tmp/update.tar.gz" 2>/dev/null \
       || ! tar -xzf "$tmp/update.tar.gz" -C "$tmp" 2>/dev/null; then
      rm -rf "$tmp"; update_failed
    fi
    src=""
    for d in "$tmp"/*/; do
      if [ -f "${d}VERSION" ] && [ -f "${d}setup.sh" ] && [ -f "${d}pyproject.toml" ] && [ -d "${d}gre" ]; then src="${d%/}"; fi
    done
    if [ -z "$src" ]; then rm -rf "$tmp"; update_failed; fi
    if ! cp -R "$src/." "$SKILL/"; then rm -rf "$tmp"; update_failed; fi
    rm -rf "$tmp"
  fi
  new="$(version)"
  if [ "$new" = "$old" ]; then say "ALREADY UP TO DATE $new"; else say "UPDATED to $new"; fi
}

# ── uv: found by absolute path, wherever it was installed, whatever this session's PATH says ───────────────────
# Install test: with the file ~/.go-reel-editor/clean-test in place, Homebrew's tools are ignored (see gre.sh).
hidden() {
  [ -f "${GRE_HOME:-$HOME/.go-reel-editor}/clean-test" ] || return 1
  case "$1" in /opt/homebrew/*|/usr/local/*) return 0 ;; esac
  return 1
}

find_uv() {
  local d
  UV=""
  if have uv && ! hidden "$(command -v uv)"; then UV="$(command -v uv)"; return 0; fi
  for d in "${UV_INSTALL_DIR:-}" "${XDG_BIN_HOME:-}" "$HOME/.local/bin" "${WINHOME:+$WINHOME/.local/bin}" \
           /opt/homebrew/bin /usr/local/bin "$HOME/.cargo/bin" "${WINLOCAL:+$WINLOCAL/Microsoft/WinGet/Links}"; do
    [ -n "$d" ] || continue
    hidden "$d/" && continue
    if [ -f "$d/uv.exe" ]; then UV="$d/uv.exe"; return 0; fi
    if [ -f "$d/uv" ] && [ -x "$d/uv" ]; then UV="$d/uv"; return 0; fi
  done
  return 1
}

refresh_path() {            # Windows: pull winget's folders into this session's PATH
  local d
  for d in "$WINLOCAL/Microsoft/WinGet/Links" "$WINHOME/.local/bin" \
           "$WINLOCAL"/Microsoft/WinGet/Packages/Gyan.FFmpeg*/ffmpeg-*/bin; do
    [ -d "$d" ] && PATH="$d:$PATH"
  done
  export PATH
}

wg() { winget install --exact --id "$1" --accept-source-agreements --accept-package-agreements \
         --disable-interactivity >/dev/null 2>&1; return 0; }

restart_needed() {
  say ""
  say "== Almost done =="
  say "Windows only shows newly installed tools to newly opened apps. Quit Claude completely (close the window),"
  say "open it again in the same folder, and say: continue setup"
  exit 2
}

ensure_uv() {
  local log tried_winget brew
  tried_winget=0
  if find_uv; then say "  ok uv"; return 0; fi
  log="$(mktemp 2>/dev/null || printf '%s' "${TMPDIR:-/tmp}/gre-setup-uv.$$")"
  say "  > installing uv (it runs the editor; about 20 MB, once, no password)..."
  if [ "$OS" = windows ]; then
    MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' powershell.exe -NoProfile -ExecutionPolicy Bypass \
      -Command "irm https://astral.sh/uv/install.ps1 | iex" >"$log" 2>&1
  elif have curl; then
    curl -LsSf https://astral.sh/uv/install.sh 2>>"$log" | sh >>"$log" 2>&1
  elif have wget; then
    wget -qO- https://astral.sh/uv/install.sh 2>>"$log" | sh >>"$log" 2>&1
  else
    printf 'neither curl nor wget is on this computer\n' >"$log"
  fi
  if ! find_uv; then                       # the old way, only when the installer above did not work
    if [ "$OS" = mac ]; then
      brew=""
      if have brew; then brew=brew
      elif [ -x /opt/homebrew/bin/brew ]; then brew=/opt/homebrew/bin/brew
      elif [ -x /usr/local/bin/brew ]; then brew=/usr/local/bin/brew; fi
      if [ -n "$brew" ]; then
        say "  > that did not work; installing uv with Homebrew instead..."
        "$brew" install uv >>"$log" 2>&1
      fi
    elif [ "$OS" = windows ] && { have winget || have winget.exe; }; then
      say "  > that did not work; installing uv with winget instead..."
      wg astral-sh.uv; tried_winget=1; refresh_path
    fi
  fi
  if ! find_uv; then
    if [ "$tried_winget" = 1 ]; then rm -f "$log"; restart_needed; fi
    say "  ! could not install uv. What the installer said:"
    tail -n 6 "$log" 2>/dev/null | tr -d '\r' | sed 's/^/      /'
    rm -f "$log"
    say "  Check the internet connection, then say: continue setup"
    exit 1
  fi
  rm -f "$log"
  say "  ok uv"
}

# ── the doctor: the editor's own check. DOCTOR_OUT gets its report, DOCTOR_RC its exit code ────────────────────
run_doctor() {
  DOCTOR_OUT="$("$UV" run -q --project "$SKILL" gre doctor 2>&1 | tr -d '\r')"
  DOCTOR_RC=$?
  printf '%s\n' "$DOCTOR_OUT" | grep -q '^READY' || DOCTOR_RC=1
}
ffmpeg_missing() { printf '%s\n' "$DOCTOR_OUT" | grep -Eq 'MISSING +ff(mpeg|probe)'; }

# ── ffmpeg the old way: ONLY when the built-in video tool does not work on this computer ───────────────────────
ffmpeg_fallback() {
  local b dirs oldifs SUDO
  say "  ! the built-in video tool did not work on this computer: installing ffmpeg the standard way instead"
  if [ "$OS" = mac ]; then
    dirs="${GRE_BREW_DIRS-/opt/homebrew/bin:/usr/local/bin}"      # tests point this at a folder without brew
    oldifs="$IFS"; IFS=:
    for b in $dirs; do
      if [ -n "$b" ] && [ -d "$b" ]; then case ":$PATH:" in *":$b:"*) ;; *) PATH="$b:$PATH" ;; esac; fi
    done
    IFS="$oldifs"; export PATH
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
  elif [ "$OS" = windows ]; then
    refresh_path
    if ! have winget && ! have winget.exe; then
      say "winget is missing: install 'App Installer' from the Microsoft Store, then say 'continue setup'."
      exit 1
    fi
    say "  > installing ffmpeg (winget, a few minutes)..."
    wg Gyan.FFmpeg
    refresh_path
  else
    SUDO=""; [ "$(id -u)" != 0 ] && SUDO="sudo -n"
    if have apt-get && $SUDO true 2>/dev/null; then
      say "  > installing ffmpeg (apt)..."
      $SUDO env DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null 2>&1
      $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg >/dev/null 2>&1
    fi
    have ffmpeg || { say "ONE STEP FOR YOU: install ffmpeg (it needs your password): sudo apt install -y ffmpeg"; say "Then say: continue setup"; exit 1; }
  fi
}

# ── companion skills: the EZ Reel Writer and the yap writer, next to this skill ─────────────────────────────────
# Installed when missing, updated when this editor put them there, never touching a member's own copy.
companions() {
  local SKILLS_DIR c src dst
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
}

main() {
  local CFA uvdir
  detect_os
  if [ "${1:-}" = "--update" ]; then
    update_skill
    exec bash "$SKILL/setup.sh"
  fi
  say "== GO! Reel Editor setup ($OS) =="

  ensure_uv
  uvdir="$(dirname "$UV")"
  case ":$PATH:" in *":$uvdir:"*) ;; *) PATH="$uvdir:$PATH" ;; esac
  export PATH

  if [ "$OS" = windows ]; then
    # Controlled Folder Access (Windows Security > Ransomware protection) silently blocks Python from writing in
    # Documents, Desktop, Pictures, Videos and OneDrive; the error reads "No such file or directory".
    CFA="$(powershell.exe -NoProfile -NonInteractive -Command '(Get-MpPreference).EnableControlledFolderAccess' 2>/dev/null | tr -d '[:space:]')"
    if [ "$CFA" = "1" ]; then
      say "  ! Controlled Folder Access is ON. Keep your reels folder OUTSIDE Documents, Desktop, Pictures, Videos"
      say "    and OneDrive (for example C:\\Users\\<you>\\Reels), or the editor can't save files there."
    fi
  fi

  companions

  # the editor's own environment: uv fetches Python 3.11/3.12 itself, and the video tool comes with the packages
  say "  > building the editor's environment (first time: a minute or two; it brings its own Python and video tool)..."
  if ! "$UV" sync --project "$SKILL" -q; then
    say "  ! could not build the environment (see above). Check the internet connection and say 'continue setup'."
    exit 1
  fi
  say ""
  run_doctor
  if [ "$DOCTOR_RC" != 0 ] && ffmpeg_missing; then
    ffmpeg_fallback
    say ""
    run_doctor
    if [ "$DOCTOR_RC" != 0 ] && [ "$OS" = windows ] && ffmpeg_missing; then
      say "  ! ffmpeg is installed but this session can't see it yet"
      restart_needed
    fi
  fi
  printf '%s\n' "$DOCTOR_OUT"
  [ "$DOCTOR_RC" = 0 ] || exit 1
  mkdir -p "$HOME/.go-reel-editor" && date > "$HOME/.go-reel-editor/setup-ok"
  say ""
  say "SETUP DONE."
  say "Tell the member: open a NEW session in this same folder (the skills load in new sessions) and paste:"
  say "  Get me started with the GO! Reel Editor."
  exit 0
}

main "$@"; exit $?
