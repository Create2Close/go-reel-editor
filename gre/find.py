"""gre find: the newest videos and photos on this computer, so Claude can offer them instead of asking a member to
move files around.

  gre find [--kind video|image|any] [--days 30] [--limit 8] [folders...]

Looks in the folder the session is in (three levels deep), Downloads, Desktop and Movies (Videos on Windows).
One numbered line per file, newest first:
  1. IMG_4821.MOV · Downloads · today 9:41 am · 1:12 · 412 MB · /Users/me/Downloads/IMG_4821.MOV"""
import os, sys, time
from datetime import datetime, timedelta
from pathlib import Path
from .common import IMAGE_EXT

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi"}                 # what `gre yap` accepts
SKIP_NAMES = {"out", "edit", ".venv", "node_modules", "__pycache__"}
BUNDLES = (".app", ".photoslibrary", ".tvlibrary", ".fcpbundle", ".imovielibrary", ".musiclibrary", ".lrdata")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def default_places(cwd=None):
    """[(folder, how deep)]: the session folder, then the usual places a phone video lands."""
    home = Path.home()
    cwd = Path(cwd or os.getcwd())
    places = [(cwd, 0 if cwd == home else 3)]              # never crawl a whole home folder
    names = ["Downloads", "Desktop", "Movies" if sys.platform == "darwin" else "Videos"]
    for n in names:
        places.append((home / n, 1))
    if os.name == "nt":                                      # OneDrive often owns the Desktop on Windows
        od = os.environ.get("OneDrive")
        if od:
            places += [(Path(od) / "Desktop", 1), (Path(od) / "Videos", 1)]
    return places


def _skip(name):
    low = name.lower()
    return name.startswith(".") or low in SKIP_NAMES or low.startswith("practice-") or low.endswith(BUNDLES)


def _walk(root, depth, exts, since, blocked):
    """Yield (mtime, size, path) under root, at most `depth` folders down. Unreadable folders go in `blocked`."""
    stack = [(root, 0)]
    while stack:
        folder, level = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except FileNotFoundError:
            continue
        except OSError:                                      # macOS privacy: Downloads/Desktop can refuse a listing
            blocked.append(Path(folder))
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    if level < depth and not _skip(e.name):
                        stack.append((e.path, level + 1))
                elif e.is_file() and not e.name.startswith(".") and Path(e.name).suffix.lower() in exts:
                    st = e.stat()
                    if st.st_mtime >= since and st.st_size > 0:
                        yield st.st_mtime, st.st_size, Path(e.path)
            except OSError:
                continue


def when(ts, now=None):
    """today 9:41 am · yesterday 4:05 pm · Nov 3 · Nov 3 2025"""
    now = now or datetime.now()
    d = datetime.fromtimestamp(ts)
    clock = f"{d.hour % 12 or 12}:{d.minute:02d} {'am' if d.hour < 12 else 'pm'}"
    if d.date() == now.date():
        return f"today {clock}"
    if d.date() == (now - timedelta(days=1)).date():
        return f"yesterday {clock}"
    day = f"{MONTHS[d.month - 1]} {d.day}"
    return day if d.year == now.year else f"{day} {d.year}"


def size(n):
    for unit, step in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= step:
            v = n / step
            return f"{v:.1f} {unit}" if unit == "GB" and v < 10 else f"{v:.0f} {unit}"
    return f"{n} bytes"


def length(seconds):
    s = int(round(seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def _duration(path):
    """A video's length, or None (no video tool yet, a broken file): the line just goes without it."""
    try:
        from .common import probe
        d = float(probe(path)["format"].get("duration") or 0)
        return d if d > 0 else None
    except Exception:
        return None


def search(folders=None, kind="any", days=30, limit=8, cwd=None, now=None):
    """([(mtime, size, path)] newest first, [folders that refused a listing])."""
    exts = VIDEO_EXT if kind == "video" else IMAGE_EXT if kind == "image" else VIDEO_EXT | IMAGE_EXT
    places = [(Path(f).expanduser(), 3) for f in folders] if folders else default_places(cwd)
    since = (now or time.time()) - days * 86400
    found, blocked, seen = [], [], set()
    for root, depth in places:
        for mtime, nbytes, p in _walk(root, depth, exts, since, blocked):
            try:
                key = os.path.normcase(str(p.resolve()))
            except OSError:
                key = os.path.normcase(str(p))
            if key not in seen:
                seen.add(key)
                found.append((mtime, nbytes, p))
    found.sort(key=lambda x: (-x[0], str(x[2])))
    return found[:max(0, limit)], blocked


def main(a):
    found, blocked = search(a.folders, a.kind, a.days, a.limit)
    if not found:
        print("NONE FOUND")
    for n, (mtime, nbytes, p) in enumerate(found, 1):
        parts = [p.name, p.parent.name or str(p.parent), when(mtime)]
        if p.suffix.lower() in VIDEO_EXT:
            d = _duration(p)
            if d:
                parts.append(length(d))
        parts += [size(nbytes), str(p)]
        print(f"{n}. " + " · ".join(parts))
    if blocked:
        names = []
        for b in blocked:
            if (b.name or str(b)) not in names:
                names.append(b.name or str(b))
        print(f"could not look in: {', '.join(names)} (no permission)")
    return 0
