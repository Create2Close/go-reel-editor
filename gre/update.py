"""gre update --check: is there a newer GO! Reel Editor? Claude runs it at the start of a session and tells the member.
The update itself is `bash setup.sh --update`.

First line of output, always exactly one of:
  UP TO DATE 0.2.0
  UPDATE AVAILABLE 0.2.0 -> 0.2.1      then up to three lines "- what is new"
  CHECK SKIPPED (reason)               offline, checked in the last 24 hours, anything unexpected
Always exits 0: a failed check never gets in a member's way."""
import json, os, re, time
import urllib.request
from .common import SKILL, HOME

REMOTE = "https://raw.githubusercontent.com/Create2Close/go-reel-editor/main"
DAY = 24 * 3600
TIMEOUT = 3


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "go-reel-editor"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(400_000).decode("utf-8", "replace")


def _key(v):
    if not re.fullmatch(r"\d+(\.\d+){1,3}", v):
        raise ValueError(v)
    return tuple(int(x) for x in v.split("."))


def whats_new(changelog, n=3):
    """The first n top-level bullets of the newest `## ` entry: the bold lead-in when there is one."""
    out, inside = [], False
    for line in changelog.splitlines():
        if line.startswith("## "):
            if inside:
                break
            inside = True
            continue
        if not inside or not line.startswith(("- ", "* ")):
            continue
        text = line[2:].strip()
        m = re.match(r"\*\*(.+?)\*\*", text)
        if m:
            text = m.group(1)
        else:
            text = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0]
        text = text.strip().rstrip(":").strip()
        if text:
            out.append(text if len(text) <= 100 else text[:97].rstrip() + "...")
        if len(out) == n:
            break
    return out


def check(force=False, now=None):
    """The lines to print."""
    now = time.time() if now is None else now
    cache = HOME / "update-check.json"
    try:
        local = (SKILL / "VERSION").read_text(encoding="utf-8").strip()
        _key(local)
    except Exception:
        return ["CHECK SKIPPED (this copy has no readable VERSION file)"]
    if not force:
        try:
            last = float(json.loads(cache.read_text(encoding="utf-8")).get("checked", 0))
        except Exception:
            last = 0.0
        if 0 <= now - last < DAY:
            return ["CHECK SKIPPED (checked in the last 24 hours)"]
    try:                                    # written before the request: one try a day, also when offline
        HOME.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"checked": now, "local": local}), encoding="utf-8")
    except OSError:
        pass
    base = (os.environ.get("GRE_UPDATE_URL") or REMOTE).rstrip("/")
    try:
        remote = _fetch(base + "/VERSION").strip()
    except Exception:
        return ["CHECK SKIPPED (offline, or the update server did not answer)"]
    try:
        newer = _key(remote) > _key(local)
    except ValueError:
        return ["CHECK SKIPPED (the update server gave an unexpected answer)"]
    notes = []
    if newer:
        try:
            notes = whats_new(_fetch(base + "/CHANGELOG.md"))
        except Exception:
            notes = []
    try:
        cache.write_text(json.dumps({"checked": now, "local": local, "remote": remote, "notes": notes}),
                         encoding="utf-8")
    except OSError:
        pass
    if not newer:
        return [f"UP TO DATE {local}"]
    return [f"UPDATE AVAILABLE {local} -> {remote}"] + [f"- {t}" for t in notes]


def main(a):
    try:
        lines = check(force=a.force)
    except Exception as e:                  # never a traceback, never a non-zero exit
        lines = [f"CHECK SKIPPED ({e.__class__.__name__})"]
    print("\n".join(lines))
    return 0
