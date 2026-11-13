#!/usr/bin/env bash
# gre.sh: runs the editor's command (`gre`) whatever the session's PATH looks like.
#
#   bash "<skill folder>/gre.sh" doctor
#   bash "<skill folder>/gre.sh" listicle spec.json
#
# A new session often cannot see tools that were installed a minute ago (uv lands in ~/.local/bin, which is not on
# every PATH). This finds uv itself, puts its folder on PATH (the yap transcriber looks for uv there), and hands
# over to `uv run`. Works in bash 3.2 (macOS), Linux and Git Bash on Windows.
# Exit 3: uv is not on this computer yet, so the editor is not set up.
SKILL="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# Install test: with the file ~/.go-reel-editor/clean-test in place, Homebrew's tools are ignored, so a Mac that has
# Homebrew behaves like a member's Mac that does not. (setup.sh and gre/tools.py honour the same file.)
CLEAN=""; [ -f "${GRE_HOME:-${HOME:-}/.go-reel-editor}/clean-test" ] && CLEAN=1
hidden() { [ -n "$CLEAN" ] || return 1; case "$1" in /opt/homebrew/*|/usr/local/*) return 0 ;; esac; return 1; }

UV=""
if command -v uv >/dev/null 2>&1 && ! hidden "$(command -v uv)"; then
  UV="$(command -v uv)"
else
  WINHOME=""; WINLOCAL=""
  if command -v cygpath >/dev/null 2>&1; then          # Git Bash on Windows
    [ -n "${USERPROFILE:-}" ] && WINHOME="$(cygpath -u "$USERPROFILE" 2>/dev/null | tr -d '\r')"
    [ -n "${LOCALAPPDATA:-}" ] && WINLOCAL="$(cygpath -u "$LOCALAPPDATA" 2>/dev/null | tr -d '\r')"
  fi
  for d in "${UV_INSTALL_DIR:-}" "${XDG_BIN_HOME:-}" "${HOME:-}/.local/bin" /opt/homebrew/bin /usr/local/bin \
           "${WINHOME:+$WINHOME/.local/bin}" "${WINLOCAL:+$WINLOCAL/Microsoft/WinGet/Links}" "${HOME:-}/.cargo/bin"; do
    [ -n "$d" ] || continue
    hidden "$d/" && continue
    if [ -f "$d/uv.exe" ]; then UV="$d/uv.exe"; break; fi
    if [ -f "$d/uv" ] && [ -x "$d/uv" ]; then UV="$d/uv"; break; fi
  done
fi

if [ -z "$UV" ]; then
  printf '%s\n' 'PROBLEM: the editor is not set up yet. Say "set me up".' >&2
  exit 3
fi

UVDIR="$(dirname "$UV")"
case ":$PATH:" in *":$UVDIR:"*) ;; *) PATH="$UVDIR:$PATH" ;; esac
export PATH
export PYTHONIOENCODING="${PYTHONIOENCODING:-utf-8}"     # file names with accents or emoji print cleanly on Windows
exec "$UV" run -q --project "$SKILL" gre "$@"
