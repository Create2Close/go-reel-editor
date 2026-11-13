"""Graphics on a yap: a headline card, the rate chart, a stat card and a lower third, timed to the words the member
says and drawn in the member's look. One file per yap, <folder>/edit/graphics.json:

  {"graphics": [
    {"type": "headline", "at": "here's the headline", "for": 4.0, "layout": "above",
     "headline": "...", "outlet": "...", "date": "Nov 12, 2026", "highlight": "words from the headline", "url": "..."},
    {"type": "chart", "at": "the chart", "for": 5.0, "layout": "full", "weeks": 52},
    {"type": "stat", "at": "7.40", "for": 3.0, "from": "7.40%", "to": "7.11%", "label": "30-year fixed"},
    {"type": "stat", "at": 21.5, "value": "$79", "label": "less a month"}
  ]}

  and, ONLY for a member who has said yes to it (gre profile --lower-third yes):
    {"type": "lower_third", "at": 4.0, "for": 4.0}

  at       words the member says (the graphic lands as they start; matched without case or punctuation against the
           words still in the cut, so a re-cut keeps it in place), or a number of seconds on the finished video
  nth      which time they say it, when they say it more than once (default 1)
  delay    seconds to shift it, + later / - earlier (default 0)
  for      seconds on screen (defaults: headline 4, chart 5, stat 3, lower third 4)
  layout   headline, chart: "above" (the space above the head) or "full" (the whole frame for a beat)
           stat: "auto" (beside the head on the side with more room, else above), "left", "right", "above", "full"
  lower_third   never a default and never required: it is drawn only when its entry is in the file AND the profile
                says the member wants it. Otherwise it is left out with a note, and so is one with no name saved or
                no room: a lower third never holds a reel up. name / title / line come from the profile (gre
                profile --name --title --line) unless given here. It sits top left, above the head: in a close-up
                there is no room low down, where the captions run.

The text is drawn exactly as written: nothing is shortened, reworded or made up. Motion: every graphic comes in over
10-12 frames with a strong ease-out and a small slide or scale, and leaves in 7."""
import json, math, re
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw
from .common import W, H, FPS, SAFE_TOP, SAFE_BOTTOM, UserError, font, profile
from .cards import (NoFit, Card, Cv, style, contrast, _lum, _words, highlight_words,          # noqa: F401
                    headline_card, chart_card, stat_card, lower_third_card)

LEFT, RIGHT = 60, W - 60                 # cards keep to the width the title uses
TYPES = ("headline", "chart", "stat", "lower_third")
NAMES = {"headline": "headline", "chart": "chart", "stat": "stat", "lower_third": "lower third"}
SECONDS = {"headline": 4.0, "chart": 5.0, "stat": 3.0, "lower_third": 4.0}
LAYOUTS = {"headline": ("above", "full"), "chart": ("above", "full"),
           "stat": ("auto", "left", "right", "above", "full"), "lower_third": ("top",)}
MIN_SECONDS = {"headline": 2.0, "chart": 3.0, "stat": 1.5, "lower_third": 2.0}
ENTER, EXIT = {"headline": 10, "chart": 12, "stat": 9, "lower_third": 10}, 7      # frames
LEAD = 0.1                               # a graphic timed to words starts this early, so it is landing as they are said


# ---------- timing: words the member says, or seconds ----------

def _key(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower().replace("&", "and"))


def find_phrase(phrase, words):
    """Every place the phrase is said in `words` (each {"w", "start", ...}): a list of (start seconds, word position).
    Case, punctuation and hyphens are ignored, and a word may be written joined or apart ("buy downs", "buydowns")."""
    target = "".join(_key(t) for t in str(phrase).split())
    hits = {}
    if not target:
        return []
    for field in ("w", "heard"):
        keys = [_key(w.get(field, w["w"])) for w in words]
        text, starts, pos = "".join(keys), {}, 0
        for i, k in enumerate(keys):
            if k:
                starts.setdefault(pos, i)
            pos += len(k)
        ends = {p for p in list(starts) + [len(text)]}
        at = text.find(target)
        while at >= 0:
            if at in starts and at + len(target) in ends:
                hits.setdefault(starts[at], words[starts[at]]["start"])
            at = text.find(target, at + 1)
    return [(t, i) for i, t in sorted(hits.items())]


def clock(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def when(g, played, flat, total):
    """(start, end) on the finished video, or (None, why) in plain words."""
    kind = g.get("type")
    at = g.get("at")
    try:
        delay, dur = float(g.get("delay", 0) or 0), float(g.get("for", SECONDS.get(kind, 4.0)))
    except (TypeError, ValueError):
        return None, '"for" and "delay" are numbers of seconds'
    if isinstance(at, (int, float)) and not isinstance(at, bool):
        start = float(at) + delay
    elif isinstance(at, str) and at.strip():
        said = find_phrase(at, played)
        try:
            nth = int(g.get("nth", 1) or 1)
        except (TypeError, ValueError):
            nth = 1
        if not said:
            if find_phrase(at, flat):
                return None, (f'the words "{at.strip()}" were cut from the video. Pick words that are still in it, '
                              f'give a time in seconds, or put that part back')
            return None, (f'the words "{at.strip()}" are not said in the video. Use words from the transcript, or a '
                          f'time in seconds')
        if not 1 <= nth <= len(said):
            times = ", ".join(clock(t) for t, _ in said)
            return None, (f'"{at.strip()}" is said {len(said)} time{"s" * (len(said) != 1)} ({times}), so there is '
                          f'no number {nth}')
        start = said[nth - 1][0] - LEAD + delay
    else:
        return None, 'it needs "at": words the member says, or a number of seconds'
    start = max(0.0, start)
    if dur < MIN_SECONDS.get(kind, 1.5):
        return None, f"{dur:g} seconds is too short to read: give it at least {MIN_SECONDS.get(kind, 1.5):g}"
    if start >= total - MIN_SECONDS.get(kind, 1.5):
        return None, (f"it would start at {clock(start)}, too close to the end of the video ({clock(total)}): "
                      f"start it earlier")
    return round(start, 3), round(min(start + dur, total), 3)


# ---------- motion ----------

def out_expo(t):
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def out_cubic(t):
    return 1 - (1 - min(1.0, t)) ** 3


def in_out(t):
    t = max(0.0, min(1.0, t))
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def out_back(t, s=1.6):
    t = min(1.0, t) - 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


def _blend(img, rgba, x, y, alpha=1.0, scale=1.0):
    """Lay an RGBA image on the frame at (x, y), optionally scaled about its own centre."""
    if alpha <= 0:
        return
    if abs(scale - 1) > 1e-3:
        h, w = rgba.shape[:2]
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        pm = rgba.astype(np.float32)
        pm[..., :3] *= pm[..., 3:4] / 255.0
        pm = cv2.resize(pm, (nw, nh), interpolation=cv2.INTER_LINEAR)
        a = np.maximum(pm[..., 3:4], 1e-3)
        pm[..., :3] = pm[..., :3] * 255.0 / a
        rgba = np.clip(pm, 0, 255).astype(np.uint8)
        x, y = x + (w - nw) // 2, y + (h - nh) // 2
    from .render import blend
    blend(img, rgba, int(round(x)), int(round(y)), alpha)


class Layer:
    """One graphic on the timeline: `draw(frame, f)` lays it on frame f (counted from its first frame)."""

    def __init__(self, kind, layout, card, x, y, start, end, G):
        self.kind, self.layout, self.card, self.x, self.y, self.G = kind, layout, card, int(x), int(y), G
        self.start, self.end = start, end
        self.f0 = round(start * FPS)
        self.n = max(1, round(end * FPS) - self.f0)
        self.full = layout == "full"
        self.ein, self.eout = ENTER[kind], EXIT
        self.rect = (0, 0, W, H) if self.full else (self.x, self.y, self.x + card.w, self.y + card.h)
        self.move = "pop" if kind == "stat" and not self.full else "slide"
        self.dx, self.dy = (-44, 0) if kind == "lower_third" else (0, 44) if self.full else (0, -34)
        # in-card motion: when it starts (frames after the first) and how long it takes
        self.act = ((self.ein + 4, 11) if hasattr(card, "hi") else (self.ein - 4, 38) if hasattr(card, "frame")
                    else (self.ein + 3, 7) if hasattr(card, "pre") else (0, 0))

    def landed(self):
        """The first frame on which everything has arrived."""
        return min(self.n - self.eout - 1, self.act[0] + self.act[1] + 1 if self.act[1] else self.ein + 1)

    def content(self, f):
        c, (a0, an) = self.card, self.act
        p = 1.0 if not an else (f - a0 + 1) / an
        if p >= 1 or not an:
            return getattr(c, "hi", c.img)
        if hasattr(c, "frame"):
            return c.frame(in_out(p))
        if p <= 0:
            return getattr(c, "pre", c.img)
        if hasattr(c, "hi"):                     # the highlighter runs across the lines one after another
            out, done = c.img.copy(), in_out(p) * sum(r[2] - r[0] for r in c.rects)
            for x0, y0, x1, y1 in c.rects:
                xe = x0 + int(round(min(x1 - x0, max(0.0, done))))
                out[y0:y1, x0:xe] = c.hi[y0:y1, x0:xe]
                done -= x1 - x0
            return out
        x0, y0, x1, y1 = c.to_box                # the "to" value rises into place
        out, e = c.pre.copy(), out_cubic(p)
        rise = int(round((1 - e) * 12))
        src = c.img[y0:y1 - rise, x0:x1].astype(np.float32)
        dst = out[y0 + rise:y1, x0:x1].astype(np.float32)
        out[y0 + rise:y1, x0:x1] = (dst + (src - dst) * min(1.0, p * 1.5)).astype(np.uint8)
        return out

    def backdrop(self, f):
        """The rows (y0, y1) a full-screen graphic's backdrop covers on frame f: it wipes up from the bottom on the
        way in and off the top on the way out. None when this is not a full-screen graphic or it is not on."""
        if not self.full or not 0 <= f < self.n:
            return None
        t = min(1.0, (f + 1) / self.ein)
        q = max(0.0, (f - (self.n - self.eout)) / self.eout)
        y0 = 0 if t >= 1 else int(round(H * (1 - out_expo(t))))
        y1 = H if q <= 0 else int(round(H * (1 - q ** 3)))
        return (y0, y1) if y1 > y0 else None

    def draw(self, img, f):
        if not 0 <= f < self.n:
            return
        m = self.card.m
        t = min(1.0, (f + 1) / self.ein)
        q = max(0.0, (f - (self.n - self.eout)) / self.eout)       # 0 until the exit starts, then towards 1
        if self.full:
            rows = self.backdrop(f)
            if rows:
                img[rows[0]:rows[1]] = np.array(self.G["full_bg"][:3], np.uint8)
            a = max(0.0, min(1.0, (f - 1) / 7)) if q <= 0 else max(0.0, 1 - q * 2)
            if a > 0:
                dy = (1 - out_cubic((f - 1) / 9)) * self.dy if q <= 0 else -q * 24
                _blend(img, self.content(f), self.x - m, self.y - m + dy, a)
            return
        if self.move == "pop":
            a, sc = (min(1.0, t * 2.2), 0.84 + 0.16 * out_back(t)) if q <= 0 else (1 - q, 1 - 0.06 * q)
            _blend(img, self.content(f), self.x - m, self.y - m, a, sc)
            return
        if q <= 0:
            a, e = min(1.0, t * 1.7), 1 - out_expo(t)
        else:
            a, e = 1 - q, q ** 3 * 0.5
        _blend(img, self.content(f), self.x - m + self.dx * e, self.y - m + self.dy * e, a)


# ---------- reading the file ----------

def path(E):
    return Path(E) / "graphics.json"


def load(E):
    """The list of graphics in edit/graphics.json, or None when there is no file."""
    p = path(E)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise UserError(f"graphics.json is not valid JSON ({e}): fix the file and run this again")
    gs = d.get("graphics") if isinstance(d, dict) else d
    if not isinstance(gs, list) or not all(isinstance(g, dict) for g in gs):
        raise UserError('graphics.json must hold a list: {"graphics": [{"type": "headline", ...}, ...]}')
    return gs


def rates_for(E):
    """The rate numbers a chart is drawn from: the copy saved with this yap (edit/rates.json) the first time the
    chart was built, so a later render never shows different numbers; else the editor's saved copy, which is then
    copied into the yap. None when `gre rates` has never run."""
    from . import news
    p = Path(E) / "rates.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return [(str(a), float(b)) for a, b in d["series"]]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    c = news.read_cache()
    if not c:
        return None
    p.write_text(json.dumps({"fetched": c.get("fetched"), "via": c.get("via"), "series": c["series"][-600:]}),
                 encoding="utf-8")
    return c["series"]


def check_fields(g):
    """What is wrong with one entry before any drawing: a list of plain-words problems."""
    kind = g.get("type")
    if kind not in TYPES:
        return [f'"{kind}" is not a graphic: use headline, chart, stat or lower_third']
    out = []
    lay = g.get("layout")
    if kind != "lower_third" and lay is not None and lay not in LAYOUTS[kind]:
        if lay == "split":
            out.append('the "split" layout is not available: use "above" or "full"')
        else:
            out.append(f'"{lay}" is not a layout for a {NAMES[kind]}: use ' + " or ".join(f'"{x}"' for x in LAYOUTS[kind]))
    if kind == "headline":
        if not _words(g.get("headline")):
            out.append('it needs "headline": the article\'s headline, word for word')
        elif highlight_words(_words(g["headline"]).split(), g.get("highlight")) is None:
            out.append(f'the highlight "{_words(g.get("highlight"))}" is not in the headline: it must be words from it, '
                       f'next to each other')
    if kind == "stat":
        if g.get("from") and not g.get("to"):
            out.append('a "from" needs a "to"')
        elif not (g.get("to") or g.get("value")):
            out.append('it needs "value" (one number) or "from" and "to"')
    if kind == "chart":
        try:
            if not 8 <= int(g.get("weeks", 52)) <= 520:
                raise ValueError
        except (TypeError, ValueError):
            out.append('"weeks" is a number from 8 to 520 (52 is a year)')
    return out


def lower_third_off(g):
    """Why a lower third entry is left out, or None when it may be drawn. The lower third is never a default: the
    member must have said yes (the profile's "lower_third": true), and there must be a name to show. Either way
    the reel goes ahead without it: these are notes, never problems."""
    if profile().get("lower_third") is not True:
        return ("left out: the member has not said yes to a name card. If they asked for it, save that first "
                "(`gre profile --lower-third yes`); otherwise take this entry out. Never add one on your own")
    if not lower_third_text(g)["name"]:
        return ('left out: no name is saved for it. Ask the member for just that, once, and save it (`gre profile '
                '--name "..." --title "..." --line "..."`). The reel does not wait for it')
    return None


def lower_third_text(g):
    """The lower third's words: the entry's own, else the profile's."""
    pr = profile()
    return {"name": g.get("name") or pr.get("name") or "", "title": g.get("title") or pr.get("title") or "",
            "line": g.get("line") or pr.get("line") or ""}


# ---------- placing ----------

def cap_band(lk):
    C = lk["captions"]
    return int(C["center_y"] - C["size"] * 0.75), int(C["center_y"] + C["size"] * 0.75)


def face_rects(boxes):
    """The face proper in each sampled frame (brow to chin, cheek to cheek): what a graphic must never cover."""
    return [(int(x + 0.10 * w), int(y + 0.05 * h), int(x + 0.90 * w), int(y + 1.0 * h)) for x, y, w, h in boxes]


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def place(g, G, lk, boxes, series=None):
    """Draw one graphic and find its place. Returns (card, x, y, layout, where, problems). The card is always drawn
    (at its smallest when nothing fits) so the preview shows the problem."""
    from .title import head_span
    kind = g["type"]
    lay = g.get("layout") if g.get("layout") in LAYOUTS[kind] else LAYOUTS[kind][0]
    full = lay == "full"
    head, brow, chin = head_span(boxes)
    cap_top, cap_bottom = cap_band(lk)
    problems = []
    if kind == "lower_third":
        g = dict(g, **lower_third_text(g))

    def make(w, h, mode=None, force=False):
        if kind == "headline":
            return headline_card(g, G, w, h, full, force)
        if kind == "chart":
            return chart_card(g, G, w, h, (series or [])[-int(g.get("weeks", 52)):], full, force)
        if kind == "stat":
            return stat_card(g, G, w, h, mode or ("full" if full else "row"), force)
        return lower_third_card(g, G, min(w, 720), h, force)

    def smallest(w, mode=None):
        """The card at its smallest whatever the room, or a blank stand-in when even that cannot hold the text."""
        try:
            return make(w, 0, mode, True)
        except NoFit:
            return Card(Cv(400, 120, G, card=not full, fill=G["full_bg"] if full else None))

    def too_long(e):
        problems.append(f"the text does not fit: {e}. " + (
            'Use the full-screen layout ("layout": "full")' if kind == "headline" and not full else
            "Ask the member for a shorter version: never shorten or reword it yourself"))

    if full:
        top, bottom = SAFE_TOP + 40, cap_top - 60
        try:
            card = make(W - 148, bottom - top)
        except NoFit as e:
            too_long(e) if e.kind == "long" else problems.append("it does not fit the frame, even full screen")
            card = smallest(W - 148)
        y = top + int(max(0, bottom - top - card.h) * (0.5 if kind == "stat" else 0.38))
        return card, (W - card.w) // 2, y, "full", "full screen", problems

    def above(if_not='use the full-screen layout ("layout": "full")'):
        """Above the head; else over the hair but above the brow; else drawn there anyway, with a problem."""
        tries = [(head - 16, "above the head")] if head else [(int(0.42 * H), "at the top (no face was found)")]
        if brow:
            tries.append((brow - 20, "over the hair, clear of the face"))
        for limit, where in tries:
            try:
                card = make(RIGHT - LEFT, limit - SAFE_TOP)
                return card, (W - card.w) // 2, SAFE_TOP, "above", where, problems
            except NoFit as e:
                if e.kind == "long":
                    too_long(e)
                    break
        else:
            problems.append(f"there is no clear space above the head for it: {if_not}")
        card = smallest(RIGHT - LEFT)
        return card, (W - card.w) // 2, SAFE_TOP, "above", "above the head", problems

    if kind in ("headline", "chart"):
        return above()

    if kind == "stat":
        if lay in ("auto", "left", "right") and boxes:
            hl = min(x - 0.12 * w for x, y, w, h in boxes)
            hr = max(x + 1.12 * w for x, y, w, h in boxes)
            eye = sum(y + 0.42 * h for x, y, w, h in boxes) / len(boxes)
            room = {"left": hl - 20 - LEFT, "right": RIGHT - (hr + 20)}
            side = lay if lay != "auto" else max(room, key=room.get)
            at_side = lambda c: (c, LEFT if side == "left" else RIGHT - c.w,
                                 int(min(max(SAFE_TOP, eye - c.h / 2), cap_top - 30 - c.h)), side,
                                 f"{side} of the head", problems)
            try:
                return at_side(make(room[side], cap_top - 30 - SAFE_TOP, "side"))
            except NoFit:
                if lay != "auto":
                    problems.append(f'there is no room {side} of the head for it: use "auto", "above" or "full"')
                    return at_side(smallest(max(room[side], 240), "side"))
        elif lay in ("left", "right"):
            problems.append('no face was found, so the side of the head is unknown: use "above" or "full"')
        return above()

    # the lower third: one spot in every look, top left of the safe area. A close-up has no room low down (the chin
    # meets the caption band), so the name sits where the title sat, once the title has gone.
    card, x, y, lay, where, problems = above("leave it off (the NMLS number can go in the post's caption)")
    return card, LEFT, y, "top", "top left, " + where, problems


# ---------- the whole file: timing, faces, placing, checks ----------

def sample_times(cuts, t0, t1, most=6):
    """Moments to look for the face while a graphic is up: its start, its end and the middle of every piece of the
    cut it runs across (each piece has its own framing)."""
    from .render import frame_plan
    out, cum = [t0 + 0.05, max(t0, t1 - 0.1)], 0.0
    for n in frame_plan(cuts["segments"]):
        a, b = cum, cum + n / FPS
        if a < t1 and b > t0:
            out.append((max(a, t0) + min(b, t1)) / 2)
        cum = b
    out = sorted(set(round(t, 2) for t in out))
    if len(out) > most:
        out = [out[round(k * (len(out) - 1) / (most - 1))] for k in range(most)]
    return out


class Item:
    def __init__(self, i, g):
        self.i, self.g, self.kind = i, g, g.get("type")
        self.name = NAMES.get(self.kind, str(self.kind))
        self.start = self.end = None
        self.layer, self.where, self.problems, self.notes, self.on_face = None, "", [], [], False

    def lines(self):
        """What `gre yap graphics` prints for this graphic."""
        head = f"{self.i} {self.name}"
        out = [f"  FIX   {head}: {p}" for p in self.problems] + [f"  note  {head}: {n}" for n in self.notes]
        if self.layer and not self.problems:
            out.append(f"  ok    {head:15s} {clock(self.start)}-{clock(self.end)}  {self.where}")
        return out


def build(E, lk, cuts, moves, flat, keep, grab=None, title_spec=None, caps=None):
    """Everything in graphics.json, resolved: a list of Items (each with its Layer, or its problems), or None when
    the yap has no graphics file. `grab(t)` returns the program frame at t (RGB) for the face search."""
    from . import title as T
    from .captions import played_words
    from .render import frame_plan
    specs = load(E)
    if specs is None:
        return None
    G = style(lk)
    played = played_words(flat, cuts, keep)
    total = sum(frame_plan(cuts["segments"])) / FPS
    grab = grab or (lambda t: T.grab(cuts, moves, t))
    frames = {}

    def boxes_at(times):
        for t in times:
            if t not in frames:
                frames[t] = grab(t)
        return T.face_boxes([frames[t] for t in times if frames[t] is not None])

    title_rect, title_end = None, 0.0
    if title_spec:
        img, _, bb = T.card(title_spec["lines"], lk, title_spec["size"])
        if bb:
            title_rect = (bb[0], int(title_spec["top"]) + bb[1], bb[2], int(title_spec["top"]) + bb[3])
            title_end = lk["title"].get("hold", 3.5) + lk["title"].get("fade_out", 0.3)
    cap_top, cap_bottom = cap_band(lk)
    items = []
    for i, g in enumerate(specs, 1):
        it = Item(i, g)
        items.append(it)
        it.problems += check_fields(g)
        if it.kind not in TYPES:
            continue
        if it.kind == "lower_third" and lower_third_off(g):
            it.notes.append(lower_third_off(g))
            continue
        res = when(g, played, flat, total)
        if res[0] is None:
            it.problems.append(res[1])
            continue
        it.start, it.end = res
        if any(k in p for p in it.problems for k in ("needs", "not a layout", "not available", '"weeks"')):
            continue                             # not enough to draw it yet
        series = None
        if it.kind == "chart":
            series = rates_for(E)
            if not series or len(series) < 8:
                it.problems.append("there are no rate numbers on this computer yet: run `gre rates` first, then this again")
                continue
        boxes = boxes_at(sample_times(cuts, it.start, it.end))
        it.boxes = boxes
        card, x, y, lay, where, probs = place(g, G, lk, boxes, series)
        if it.kind == "lower_third" and any("no clear space" in p for p in probs):
            it.notes.append("left out: there is no clear space above the head for it (the NMLS number can go in "
                            "the post's caption)")
            continue                             # never on the face, and never a reason to hold the reel
        it.problems += probs
        it.where = where
        it.layer = L = Layer(it.kind, lay, card, x, y, it.start, it.end, G)
        if L.full:
            if title_rect and it.start < title_end:
                it.problems.append(f"it covers the title, which is on screen until {clock(title_end)}: start it after that")
            continue
        r = L.rect
        if r[0] < 40 or r[2] > W - 40 or r[1] < SAFE_TOP - 4 or r[3] > SAFE_BOTTOM + 4:
            it.problems.append("it runs off the part of the frame that phones show: make its text shorter or use full screen")
        it.on_face = any(_hit(r, fr) for fr in face_rects(boxes))
        if it.on_face and not any("no room" in p or "no clear space" in p for p in probs):
            it.problems.append("it covers the face" + ("" if it.kind == "lower_third" else
                                                       ': use the full-screen layout ("layout": "full")'))
        if r[1] < cap_bottom and r[3] > cap_top and any(c["start"] < it.end and c["end"] > it.start for c in caps or []):
            it.problems.append("it sits on the captions")
        if title_rect and it.start < title_end and _hit(r, title_rect):
            it.problems.append(f"it sits on the title, which is on screen until {clock(title_end)}: start it after that")
    live = [it for it in items if it.layer]
    for k, a in enumerate(live):
        for b in live[k + 1:]:
            if a.start < b.end and b.start < a.end and _hit(a.layer.rect, b.layer.rect):
                lo, hi = max(a.start, b.start), min(a.end, b.end)
                b.problems.append(f"it is on screen in the same place as the {a.name} (graphic {a.i}) from {clock(lo)} "
                                  f"to {clock(hi)}: move one of them or shorten it")
    return items


def layers(items):
    return [it.layer for it in items or [] if it.layer]


def captions_on_cards(caps, lays, lk):
    """White outlined captions are hard to read on a white or cream full-screen card. Every caption that plays
    during one gets a second drawing, "on_card": the card's own ink, no outline and no shadow. The renderer uses it
    while the backdrop is behind the caption. The captions are never hidden."""
    from . import captions as C
    full = [L for L in lays if L.full]
    if not full:
        return caps
    plain = dict(lk["captions"], fill=list(full[0].G["ink"]), edge_w=0, shadow=None)
    for c in caps:
        if any(c["start"] < L.end and c["end"] > L.start for L in full):
            c["on_card"] = C.draw(c["text"], plain)
    return caps


def caption_now(c, lays, seq):
    """(image, x, y) for caption c on frame seq: its on-card drawing when a full-screen backdrop is behind it."""
    if "on_card" in c:
        img, x, y = c["on_card"]
        for L in lays:
            rows = L.backdrop(seq - L.f0)
            if rows and rows[0] <= y and y + img.shape[0] <= rows[1]:
                return img, x, y
    return c["img"], c["x"], c["y"]


def fixes(items):
    """Every open problem, one plain line each."""
    return [f"graphic {it.i} ({it.name}): {p}" for it in items or [] for p in it.problems]


def still(layer, frame, f=None):
    """The frame with one graphic on it, fully landed (or at its frame f)."""
    out = frame.copy()
    layer.draw(out, layer.landed() if f is None else f)
    return out


def sheet(items, out, grab, lk, caps=None, title=None):
    """The contact sheet: every graphic, fully landed, on the real frame of that moment, with the captions and the
    title as they are then. Half size, one tile per graphic."""
    from .render import blend
    from . import captions as C
    tiles = []
    for it in items:
        L = it.layer
        if not L:
            continue
        f = L.landed()
        t = (L.f0 + f) / FPS
        frame = grab(t)
        if frame is None:
            frame = np.full((H, W, 3), 90, np.uint8)
        img = still(L, frame, f)
        for c in caps or []:
            if c["start"] <= t < c["end"]:
                arr, x, y = C.draw(c["text"], lk["captions"])
                c = captions_on_cards([dict(c, img=arr, x=x, y=y)], [L], lk)[0]
                blend(img, *caption_now(c, [L], L.f0 + f))
                break
        if title and title["alpha"](t) > 0:
            blend(img, title["img"], title["x"], title["y"] - title["rise"](t), title["alpha"](t))
        tile = Image.fromarray(img).resize((W // 2, H // 2), Image.LANCZOS)
        d = ImageDraw.Draw(tile)
        tag = f" {it.i} {it.name}  {clock(it.start)}  {'FIX' if it.problems else 'ok'} "
        f_tag = font(lk["font"], 26, 700)
        d.rectangle([0, 0, d.textlength(tag, font=f_tag) + 8, 40], fill=(0, 0, 0))
        d.text((4, 4), tag, font=f_tag, fill=(255, 255, 255))
        tiles.append(tile)
    if not tiles:
        return None
    im = Image.new("RGB", (W // 2 * len(tiles), H // 2), "white")
    for k, t in enumerate(tiles):
        im.paste(t, (k * W // 2, 0))
    im.save(out)
    return out


def samples(lk, base):
    """Two stills for a look's sample sheet (`gre look sheet`): the headline card and a stat card on the first (and
    the lower third, only when the member has said yes to one), the full-screen chart on the second. The chart uses
    the saved rate numbers when there are some; otherwise made-up ones, labelled as samples."""
    from . import news
    G, pr = style(lk), profile()
    a = np.array(base.convert("RGB"))
    hc = headline_card({"headline": "Your article's headline goes here, word for word", "outlet": "The outlet",
                        "date": "Nov 12, 2026", "highlight": "word for word"}, G, RIGHT - LEFT, 420)
    _blend(a, hc.hi, (W - hc.w) // 2 - hc.m, SAFE_TOP - hc.m)
    sc = stat_card({"from": "7.40%", "to": "7.11%", "label": "A number you say"}, G, 340, 700, "side")
    _blend(a, sc.img, RIGHT - sc.w - sc.m, 660 - sc.m)
    if pr.get("lower_third") is True and pr.get("name"):      # only for a member who said yes to a name card
        lt = lower_third_card(lower_third_text({}), G, 660, None, True)
        _blend(a, lt.img, LEFT - lt.m, 1160 - lt.m)
    b = np.zeros((H, W, 3), np.uint8)
    b[:] = np.array(G["full_bg"][:3], np.uint8)
    saved = news.read_cache()
    pts = saved["series"][-52:] if saved else [(f"2026-{1 + k // 5:02d}-{1 + k % 5 * 6:02d}",
                                                round(6.6 + 0.35 * math.sin(k / 7) + k * 0.004, 2)) for k in range(52)]
    cc = chart_card({}, G, W - 148, 1000, pts, True, source=None if saved else "Sample numbers, not real rates")
    _blend(b, cc.img, (W - cc.w) // 2, SAFE_TOP + 60)
    return [Image.fromarray(a).convert("RGBA"), Image.fromarray(b).convert("RGBA")]
