"""Where ffmpeg comes from, so a member never has to install it.

  1. GRE_FFMPEG_DIR    a folder holding ffmpeg (and ffprobe): tests and special setups
  2. system            an ffmpeg AND ffprobe the computer already has (PATH, Homebrew, winget): nothing changes
  3. bundled           the ffmpeg that ships inside the `imageio-ffmpeg` package (installed with the editor, no
                       Homebrew, no winget, no password). It has no ffprobe: `probe_with_ffmpeg` reads the same
                       facts from `ffmpeg -i`.
  4. system, ffmpeg only   last resort when the bundled one will not start

`activate()` runs once per process and puts the chosen folder first on PATH, so every bare `ffmpeg` call in the
engine, and every child process (the WhisperX worker), finds it.

GRE_FFMPEG_SOURCE=bundled|system|none narrows the search (tests; `none` pretends no ffmpeg exists)."""
import os, re, shutil, subprocess
from pathlib import Path

EXE = ".exe" if os.name == "nt" else ""
_STATE = None


def _home():
    from .common import HOME
    return HOME


def clean_test():
    """Install test: with the file ~/.go-reel-editor/clean-test in place, the computer's own ffmpeg is ignored, so a
    Mac that has Homebrew behaves like a member's Mac that does not. gre.sh and setup.sh honour the same file."""
    try:
        return (_home() / "clean-test").is_file()
    except OSError:
        return False


def _which(tool, folder=None):
    return shutil.which(tool, path=str(folder)) if folder else shutil.which(tool)


def _system_dirs():
    """Places a system ffmpeg lives that a session's PATH often misses."""
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            return []
        wg = Path(local) / "Microsoft" / "WinGet"
        return [wg / "Links"] + sorted((wg / "Packages").glob("Gyan.FFmpeg*/ffmpeg-*/bin"), reverse=True)
    return [Path("/opt/homebrew/bin"), Path("/usr/local/bin")]


def _system(need_probe=True):
    """(folder or None when it is already on PATH, ffmpeg, ffprobe) or None."""
    f, p = _which("ffmpeg"), _which("ffprobe")
    if f and (p or not need_probe):
        return None, f, p
    for d in _system_dirs():
        try:
            f, p = _which("ffmpeg", d), _which("ffprobe", d)
        except OSError:
            continue
        if f and (p or not need_probe):
            return Path(d), f, p
    return None


def _bundled_binary():
    try:
        import imageio_ffmpeg
    except Exception:
        return None
    try:
        found = sorted(p for p in (Path(imageio_ffmpeg.__file__).parent / "binaries").glob("ffmpeg-*") if p.is_file())
    except OSError:
        return None
    return found[-1] if found else None


def _link(src, dst):
    """Make dst (named plain `ffmpeg`) point at src: a symlink on Mac/Linux, a hard link or a copy on Windows."""
    tmp = dst.with_name(f"{dst.name}.{os.getpid()}.tmp")
    tmp.unlink(missing_ok=True)
    made = False
    if os.name != "nt":
        try:
            os.symlink(src, tmp)
            made = True
        except OSError:
            pass
    if not made:
        try:
            os.link(src, tmp)
        except OSError:
            shutil.copy2(src, tmp)
    try:
        os.replace(tmp, dst)
    except OSError:                          # Windows: dst is running in another editor process; keep it
        tmp.unlink(missing_ok=True)
        if not dst.exists():
            raise


def _bundled(log=None):
    """(folder, ffmpeg) for the packaged ffmpeg, or (None, why)."""
    src = _bundled_binary()
    if not src:
        return None, "the built-in video tool is not installed"
    folder = _home() / "tools" / (src.name[:-4] if src.name.lower().endswith(".exe") else src.name)
    exe, mark = folder / f"ffmpeg{EXE}", folder / "ok.txt"
    try:
        st = src.stat()
        stamp = f"{src}|{st.st_size}|{st.st_mtime_ns}"
        if exe.exists() and mark.exists() and mark.read_text(encoding="utf-8") == stamp:
            return folder, str(exe)
        if log:
            log("  > setting up the video tool (once)...")
        folder.mkdir(parents=True, exist_ok=True)
        if os.name != "nt" and not os.access(src, os.X_OK):
            src.chmod(st.st_mode | 0o111)
        _link(src, exe)
        r = subprocess.run([str(exe), "-hide_banner", "-version"], capture_output=True, timeout=60)
        if r.returncode:
            return None, "the built-in video tool does not start on this computer"
        mark.write_text(stamp, encoding="utf-8")
        return folder, str(exe)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"the built-in video tool could not be set up ({e.__class__.__name__})"


def _resolve(log=None):
    st = {"source": None, "dir": None, "ffmpeg": None, "ffprobe": None, "why": ""}
    override = os.environ.get("GRE_FFMPEG_DIR")
    if override:
        d = Path(override).expanduser()
        f = _which("ffmpeg", d) if d.is_dir() else None
        if f:
            st.update(source="GRE_FFMPEG_DIR", dir=d, ffmpeg=f, ffprobe=_which("ffprobe", d))
        else:
            st["why"] = f"GRE_FFMPEG_DIR has no ffmpeg in it: {d}"
        return st
    only = (os.environ.get("GRE_FFMPEG_SOURCE") or "").strip().lower()
    if not only and clean_test():
        only = "bundled"
    if only == "none":
        st["why"] = "GRE_FFMPEG_SOURCE=none"
        return st
    if only != "bundled":
        s = _system()
        if s:
            st.update(source="system", dir=s[0], ffmpeg=s[1], ffprobe=s[2])
            return st
    if only != "system":
        d, f = _bundled(log)
        if d:
            st.update(source="bundled", dir=d, ffmpeg=f)
            return st
        st["why"] = f
    if only != "bundled":
        s = _system(need_probe=False)
        if s:
            st.update(source="system", dir=s[0], ffmpeg=s[1], ffprobe=s[2])
    return st


def activate(log=None, refresh=False):
    """Find ffmpeg once and put its folder first on PATH. Returns
    {"source": "system" | "bundled" | "GRE_FFMPEG_DIR" | None, "dir", "ffmpeg", "ffprobe", "why"}."""
    global _STATE
    if _STATE is None or refresh:
        _STATE = _resolve(log)
        d = _STATE["dir"]
        if d:
            parts = [x for x in os.environ.get("PATH", "").split(os.pathsep) if x and Path(x) != Path(d)]
            os.environ["PATH"] = os.pathsep.join([str(d)] + parts)
    return _STATE


def have_ffprobe():
    """True when a real ffprobe comes with the ffmpeg in use (the bundled one has none)."""
    return bool(activate()["ffprobe"])


# ---------- reading a file's facts without ffprobe ----------

_STREAM = re.compile(r"^\s*Stream #0:(\d+)(?:\[[^\]]*\])?(?:\([^)]*\))?: (Video|Audio|Subtitle|Data|Attachment): (.*)$")
_DURATION = re.compile(r"^\s*Duration: (\d+):(\d\d):(\d\d(?:\.\d+)?)")
_ROTATION = re.compile(r"rotation of (-?[\d.]+) degrees", re.I)   # "displaymatrix:" (ffmpeg 7), "Display Matrix:" (9)
_TAG = re.compile(r"^\s+([A-Za-z_][\w.\- ]*?)\s*: (.*)$")
_RANGES = {"tv", "pc"}
_FIELD = re.compile(r"^(progressive|top first|bottom first|top coded first.*|bottom coded first.*|left|center|"
                    r"topleft|top|bottomleft|bottom|unspecified)$")


def _split(text):
    """Split on top-level commas: 'h264 (High), yuv420p(tv, bt709), 1920x1080' -> 3 parts."""
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def _video(rest):
    parts = _split(rest)
    s = {"codec_type": "video", "codec_name": parts[0].split()[0] if parts and parts[0] else ""}
    for i, part in enumerate(parts[1:], 1):
        m = re.match(r"^(\d+)x(\d+)\b", part)
        if m and "width" not in s:
            s["width"], s["height"] = int(m.group(1)), int(m.group(2))
            continue
        m = re.match(r"^([\d.]+)(k?) (fps|tbr)$", part)
        if m:
            if m.group(3) == "fps" or "avg_frame_rate" not in s:
                s["avg_frame_rate"] = f"{round(float(m.group(1)) * (1000 if m.group(2) else 1) * 1000)}/1000"
            continue
        if i == 1:                                   # yuv420p10le(tv, bt2020nc/bt2020/arib-std-b67, progressive)
            m = re.match(r"^([A-Za-z0-9_]+)\s*(?:\((.*)\))?$", part)
            if not m:
                continue
            s["pix_fmt"] = m.group(1)
            for tok in (t.strip() for t in (m.group(2) or "").split(",")):
                if tok in _RANGES:
                    s["color_range"] = tok
                elif tok.count("/") == 2:
                    s["color_space"], s["color_primaries"], s["color_transfer"] = tok.split("/")
                elif tok and "color_space" not in s and not _FIELD.match(tok):
                    s["color_space"] = s["color_primaries"] = s["color_transfer"] = tok
    for k in ("color_space", "color_primaries", "color_transfer"):
        if s.get(k) == "unknown":
            del s[k]
    s.setdefault("avg_frame_rate", "0/1")
    return s


def _audio(rest):
    parts = _split(rest)
    s = {"codec_type": "audio", "codec_name": parts[0].split()[0] if parts and parts[0] else ""}
    for part in parts[1:]:
        m = re.match(r"^(\d+) Hz$", part)
        if m:
            s["sample_rate"] = m.group(1)
    s.setdefault("sample_rate", "0")
    return s


def parse_ffmpeg_info(text):
    """Turn the text `ffmpeg -i file` prints into the part of ffprobe's JSON the editor uses."""
    out = {"streams": [], "format": {}}
    cur, in_tags, seen_input = None, False, False
    for line in text.splitlines():
        if line.startswith("Input #"):
            if seen_input:
                break
            seen_input = True
            continue
        if not seen_input:
            continue
        m = _DURATION.match(line)
        if m and cur is None:
            out["format"]["duration"] = f"{int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)):.6f}"
            continue
        m = _STREAM.match(line)
        if m:
            kind, rest = m.group(2), m.group(3)
            cur = _video(rest) if kind == "Video" else _audio(rest) if kind == "Audio" else {"codec_type": kind.lower()}
            cur["index"] = int(m.group(1))
            out["streams"].append(cur)
            in_tags = False
            continue
        if cur is None:
            continue
        if not line.startswith(" "):                 # the banner after the input block ("At least one output...")
            break
        stripped = line.strip()
        if stripped == "Metadata:":
            in_tags = True
            continue
        if stripped == "Side data:":
            in_tags = False
            continue
        m = _ROTATION.search(line)
        if m:
            cur.setdefault("side_data_list", []).append({"side_data_type": "Display Matrix",
                                                         "rotation": int(round(float(m.group(1))))})
            continue
        if in_tags:
            m = _TAG.match(line)
            if m:
                cur.setdefault("tags", {})[m.group(1).strip()] = m.group(2).strip()
    return out


def probe_with_ffmpeg(path):
    """ffprobe's answer, read from `ffmpeg -i` (the bundled ffmpeg ships without ffprobe)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path)], capture_output=True, text=True,
                       errors="replace")
    d = parse_ffmpeg_info(r.stderr)
    if not d["streams"]:
        from .common import die
        last = [ln.strip() for ln in r.stderr.strip().splitlines() if ln.strip()][-1:]
        die(f"{Path(str(path)).name} is not a video, photo or sound file this editor can read"
            + (f" ({last[0][-200:]})" if last else ""))
    d["format"].setdefault("duration", "0")
    d["format"]["filename"] = str(path)
    return d

