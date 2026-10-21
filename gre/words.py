"""The transcript as one numbered word list across every clip (W0, W1, ...), plus the readable sheet Claude cuts from."""
import json, re
from pathlib import Path

FILLERS = {"um", "uh", "uhm", "umm", "erm", "er", "hmm", "mm", "mhm", "ah"}
SMALL = {"a", "an", "the", "of", "in", "into", "on", "to", "for", "with", "and", "but", "or", "so", "my", "our",
         "your", "that", "at", "as", "by", "from", "is", "be", "if", "it's", "its", "their", "his", "her", "this"}


def norm(s):
    s = s.lower().replace("’", "'").replace("‘", "'")
    s = s.replace("&", "and")
    return re.sub(r"[^a-z0-9%$']", "", s).strip("'")


def load(edit_dir):
    p = Path(edit_dir) / "words.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    flat = []
    for ci, c in enumerate(d["clips"]):
        for w in c["words"]:
            flat.append(dict(w, clip=c["clip"], ci=ci, i=len(flat)))
    return d, flat


def ends_sentence(w):
    return bool(re.search(r"[.?!][\"”’)]*$", w))


def sheet(d, flat, out_md):
    """Phrases broken at pauses >= 0.3 s; pauses >= 0.5 s marked (they get tightened); fillers and odd words flagged."""
    lines = ["# Numbered transcript (W# = word number). Cut by keeping ranges of word numbers.", "",
             "‖0.8s = a pause (pauses of 0.5 s or more get tightened automatically). "
             "[filler] [long: maybe a merged repeat] [?: low confidence]", ""]
    for ci, c in enumerate(d["clips"]):
        ws = [w for w in flat if w["ci"] == ci]
        lines += [f"## Clip {ci + 1}: {c['clip']} ({c['duration']:.1f} s)", ""]
        cur, t0 = [], None
        for k, w in enumerate(ws):
            if cur and w["start"] - ws[k - 1]["end"] >= 0.3:
                lines.append(f"- {t0:6.1f}s  " + " ".join(cur))
                gap = w["start"] - ws[k - 1]["end"]
                if gap >= 0.5:
                    lines.append(f"  ‖{gap:.1f}s")
                cur = []
            if not cur:
                t0 = w["start"]
            tag = ""
            if norm(w["w"]) in FILLERS:
                tag = "[filler]"
            elif w["end"] - w["start"] > 1.0:
                tag = "[long]"
            elif w.get("prob", 1) < 0.4:
                tag = "[?]"
            cur.append(f"W{w['i']}·{w['w']}{tag}")
        if cur:
            lines.append(f"- {t0:6.1f}s  " + " ".join(cur))
        lines.append("")
    Path(out_md).write_text("\n".join(lines), encoding="utf-8")
    return out_md
