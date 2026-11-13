"""The four yap graphics as drawn cards, in the member's look: the headline card, the rate chart, the stat card and
the lower third. Pillow only: everything is drawn at 2x and shrunk, so corners, lines and type are smooth.

`style(look)` reads how a look draws its cards; each `*_card` function draws one at the largest type that fits the
room it is given, or raises NoFit. Timing, placing and motion live in graphics.py."""
import math, re
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .common import font
from .text import wrap, textlength

SS = 2                                   # everything is drawn at 2x and shrunk: smooth corners, lines and type


class NoFit(Exception):
    """The text does not fit the space. kind: 'room' (the space is too small) or 'long' (the text is too long)."""

    def __init__(self, kind, msg=""):
        super().__init__(msg)
        self.kind = kind


# ---------- the look ----------

def _lum(c):
    lin = lambda v: v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(x / 255) for x in c[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _mix(a, b, t):
    return [round(a[i] + (b[i] - a[i]) * t) for i in range(3)] + [255]


def style(lk):
    """How this look draws graphics: the look's optional "graphics" block over defaults taken from the rest of the
    look, so a look without the block still gets its own card. A look with a dark listicle panel gets a dark card
    and heavy type; any other look gets its white box. The accent is the member's own (styles.accent), else the
    look's red; a member's look also gets a rule in that colour across the top of every card, and their second
    colour (styles.accent2) on the small labels."""
    from .brand import ink_for
    st = lk.get("styles", {})
    panel = (lk.get("listicle") or {}).get("panel")
    if panel:
        G = {"card": list(panel["fill"][:3]) + [max(int(panel["fill"][3]), 240)], "ink": [255, 255, 255, 255],
             "radius": int(panel.get("radius", 32)), "shadow": None, "weight": 800}
    else:
        box = st.get("white") or {"box": [255, 255, 255, 255], "ink": [0, 0, 0, 255]}
        G = {"card": list(box["box"]), "ink": list(box["ink"]), "radius": 16,
             "shadow": {"color": [0, 0, 0, 95], "dy": 8, "blur": 16}, "weight": max(700, int(lk.get("weight", 700)))}
    G.update({"font": lk["font"], "number_font": None, "number_weight": 800, "pad": 28, "leading": 1.16,
              "rule": False, "caps": True, "tab": bool(st.get("accent")),
              "accent": list(((st.get("accent") or st.get("red") or {}).get("box")) or [226, 35, 35, 255]),
              "accent2": (st.get("accent2") or {}).get("box")})
    G.update({k: v for k, v in (lk.get("graphics") or {}).items() if not k.startswith("_")})
    solid = list(G["card"][:3]) + [255]
    G.setdefault("muted", _mix(G["ink"], solid, 0.36))
    G.setdefault("highlight", list(G["accent"]))
    G.setdefault("marker", _lum(solid) > 0.55)
    if G["marker"]:                      # a highlighter: the colour washed over the card, the type stays in its ink
        t = 0.62
        while t > 0.2 and contrast(G["ink"], _mix(solid, G["highlight"], t)) < 7:
            t -= 0.04
        G["highlight_fill"], G["highlight_ink"] = _mix(solid, G["highlight"], t), list(G["ink"])
    else:                                # a dark card: a solid strip of the colour, the type in whatever reads on it
        G["highlight_fill"] = list(G["highlight"])
        G.setdefault("highlight_ink", ink_for(G["highlight"]))
    G.setdefault("full_bg", solid)
    G["accent_ink"] = ink_for(G["accent"])
    # a colour that cannot be read on the card (a navy accent on a dark panel) is not used for type or lines
    G["accent_text"] = G["accent"] if contrast(G["accent"], solid) >= 2.4 else None
    a2 = G.get("accent2")
    a2 = list(a2) if a2 and contrast(a2, solid) >= 3 else None
    G["eyebrow"], G["label"], G["dot"] = a2 or list(G["ink"]), a2 or G["muted"], a2
    return G


def Ft(G, size, weight=None, number=False):
    return font((G.get("number_font") or G["font"]) if number else G["font"], size * SS,
                weight or (G["number_weight"] if number else G["weight"]))


def tw(s, f):
    return textlength(s, f) / SS


def cap_h(f):
    """The height of a capital letter in final pixels."""
    return -f.getbbox("H", anchor="ls")[1] / SS


def _digit_w(f):
    return max(textlength(d, f) for d in "0123456789")


def tabw(s, f):
    """Width of a number drawn with every digit in an equal cell (so a count-up does not jitter)."""
    cell = _digit_w(f)
    return sum(cell if ch.isdigit() else textlength(ch, f) for ch in s) / SS


TAB = 10                                 # the rule in the accent colour across the top of a member's cards


class Cv:
    """A drawing surface at 2x. Coordinates are final pixels with (0, 0) at the card's top-left corner; `m` pixels
    of margin around the card hold its shadow. `top` is where the content may start (under the accent rule)."""

    def __init__(self, w, h, G, card=True, fill=None):
        self.w, self.h, self.G = int(math.ceil(w)), int(math.ceil(h)), G
        sh = G.get("shadow") if card else None
        self.m = int(sh["blur"] * 2.5 + abs(sh.get("dy", 0))) if sh else 0
        size = ((self.w + 2 * self.m) * SS, (self.h + 2 * self.m) * SS)
        self.img = Image.new("RGBA", size, tuple(fill) if fill else (0, 0, 0, 0))
        if sh:
            ImageDraw.Draw(self.img).rounded_rectangle(
                [self.P(0), self.P(sh.get("dy", 0)), self.P(self.w), self.P(self.h + sh.get("dy", 0))],
                radius=G["radius"] * SS, fill=tuple(sh["color"]))
            self.img = self.img.filter(ImageFilter.GaussianBlur(sh["blur"] * SS))
        if card:
            self.box(0, 0, self.w, self.h, G["card"], G["radius"])
            if G.get("tab"):             # the top TAB pixels of the same rounded shape, in the accent colour
                mask = Image.new("L", size, 0)
                ImageDraw.Draw(mask).rounded_rectangle([self.P(0), self.P(0), self.P(self.w), self.P(self.h)],
                                                       radius=G["radius"] * SS, fill=255)
                mask.paste(0, (0, self.P(TAB), size[0], size[1]))
                self.img.paste(Image.new("RGBA", size, tuple(G["accent"])), (0, 0), mask)

    def P(self, v):
        return int(round((v + self.m) * SS))

    def box(self, x0, y0, x1, y1, fill, r=0):
        ImageDraw.Draw(self.img).rounded_rectangle([self.P(x0), self.P(y0), self.P(x1), self.P(y1)],
                                                   radius=r * SS, fill=tuple(fill))

    def poly(self, pts, fill):
        ImageDraw.Draw(self.img).polygon([(self.P(x), self.P(y)) for x, y in pts], fill=tuple(fill))

    def text(self, x, base, s, f, fill, tab=0.0, on=None):
        """Text with its left edge at x and its baseline at `base`. Returns its width. tab (0-1): how far every
        digit is spread towards one equal cell, so a number that is counting does not jitter; 0 is normal spacing."""
        d = ImageDraw.Draw(on or self.img)
        px, py = (x + self.m) * SS, (base + self.m) * SS
        if not tab:
            d.text((px, py), s, font=f, fill=tuple(fill), anchor="ls")
            return tw(s, f)
        cell, x0 = _digit_w(f), px
        for ch in s:
            cw = textlength(ch, f) + ((cell - textlength(ch, f)) * tab if ch.isdigit() else 0)
            d.text((px + (cw - textlength(ch, f)) / 2, py), ch, font=f, fill=tuple(fill), anchor="ls")
            px += cw
        return (px - x0) / SS

    def done(self, img=None):
        im = img or self.img
        return np.array(im.convert("RGBa").resize((im.width // SS, im.height // SS), Image.LANCZOS).convert("RGBA"))


class Card:
    """A drawn graphic: `img` (RGBA, the finished state) with the card's rectangle w x h at (m, m) inside it."""

    def __init__(self, cv, img=None):
        self.img = cv.done() if img is None else img
        self.m, self.w, self.h = cv.m, cv.w, cv.h


def _words(s):
    return " ".join(str(s or "").split())


def _caps(s, G):
    return s.upper() if G.get("caps", True) else s


def _top(G, full):
    """Where a card's content starts: its padding, plus the accent rule on a member's card. Full screen (no card):
    a short bar in the accent colour sits above the content instead, drawn by _bar."""
    return (16 + (30 if G.get("tab") else 0)) if full else G["pad"] + (TAB if G.get("tab") else 0)


def _bar(c, G, full, x=16):
    if full and G.get("tab"):
        c.box(x, 16, x + 96, 16 + 12, G["accent"])


# ---------- the headline card ----------

def highlight_words(words, phrase):
    """Which words of the headline the highlighter covers: a set of positions, empty without a phrase, None when the
    phrase is not in the headline."""
    key = lambda s: re.sub(r"[^a-z0-9%$]", "", s.lower())
    want = [key(x) for x in str(phrase or "").split() if key(x)]
    if not want:
        return set()
    have = [key(x) for x in words]
    for i in range(len(have) - len(want) + 1):
        if have[i:i + len(want)] == want:
            return set(range(i, i + len(want)))
    return None


def headline_card(g, G, w, h_max, full=False, force=False):
    """The headline in the look's type, outlet and date above it. `hi` is the same card with the highlighter drawn
    and `rects` are the highlighted strips, for the swipe."""
    text = _words(g.get("headline"))
    outlet, when = _caps(_words(g.get("outlet")), G), _words(g.get("date"))
    marked = highlight_words(text.split(), g.get("highlight")) or set()
    pad, top = (16 if full else G["pad"]), _top(G, full)
    sizes = range(112, 63, -4) if full else range(72, 51, -2)
    most = 8 if full else 3
    egap = 28 if G["rule"] else 22 if full else 12

    def at(size):
        f = Ft(G, size)
        lines = wrap(text, f, (w - 2 * pad) * SS)
        es = max(38 if full else 30, round(size * 0.44))
        lh = round(size * G["leading"])
        h = top + ((round(es * 1.15) + egap) if (outlet or when) else 0) + len(lines) * lh + pad
        return size, f, lines, es, lh, h

    pick = None                          # the biggest type that fits; a little smaller if that saves a line
    for size in sizes:
        t = at(size)
        if len(t[2]) <= most and (h_max is None or t[5] <= h_max):
            if pick is None or (len(t[2]) < len(pick[2]) and size >= pick[0] * 0.84):
                pick = t
        if pick and size < pick[0] * 0.84:
            break
    if pick is None:
        if len(t[2]) > most:
            raise NoFit("long", f"the headline needs {len(t[2])} lines even at the smallest size")
        if not force:
            raise NoFit("room")
        pick = t
    size, f, lines, es, lh, h = pick
    fe, fd = Ft(G, es, 700), Ft(G, es, 500)
    sep = "  ·  " if outlet and when else ""
    wu = w if full else max(560, math.ceil(max([tw(ln, f) for ln in lines] + [tw(outlet, fe) + tw(sep + when, fd)])
                                           + 2 * pad))
    cap = cap_h(f)

    def draw(hi):
        c = Cv(wu, h, G, card=not full, fill=G["full_bg"] if full else None)
        _bar(c, G, full, pad)
        y, rects, k = top, [], 0
        if outlet or when:
            x = pad + c.text(pad, y + es * 0.80, outlet, fe, G["eyebrow"])
            c.text(x, y + es * 0.80, sep + when, fd, G["muted"])
            y += round(es * 1.15)
            if G["rule"]:
                c.box(pad, y + 10, wu - pad, y + 12, G["ink"])
            y += egap
        for ln in lines:
            ws = ln.split()
            base = y + (lh + cap) / 2
            run = [j for j in range(len(ws)) if k + j in marked]
            if hi and run:
                pre, mid, post = " ".join(ws[:run[0]]), " ".join(ws[run[0]:run[-1] + 1]), " ".join(ws[run[-1] + 1:])
                x0 = pad + (tw(pre + " ", f) if pre else 0)
                x1 = x0 + tw(mid, f)
                px = size * 0.12
                if G["marker"]:          # a felt-tip stroke: a little lower than the line, its ends at a slant
                    y0, y1, s = y + lh * 0.14, y + lh * 0.96, size * 0.07
                    c.poly([(x0 - px + s, y0), (x1 + px + s, y0), (x1 + px - s, y1), (x0 - px - s, y1)],
                           G["highlight_fill"])
                else:
                    c.box(x0 - px, y + 1, x1 + px, y + lh - 1, G["highlight_fill"], 5)
                rects.append((max(0, int(x0 - px - size * 0.07 + c.m) - 1), int(y + c.m),
                              int(x1 + px + size * 0.07 + c.m) + 2, int(y + lh + c.m) + 1))
                c.text(pad, base, pre, f, G["ink"])
                c.text(x0, base, mid, f, G["highlight_ink"])
                c.text(x1 + tw(" ", f), base, post, f, G["ink"])
            else:
                c.text(pad, base, ln, f, G["ink"])
            k += len(ws)
            y += lh
        return c, rects

    plain, _ = draw(False)
    card = Card(plain)
    if marked:
        c, card.rects = draw(True)
        card.hi = c.done()
    return card


# ---------- the rate chart ----------

def chart_card(g, G, w, h_max, pts, full=False, force=False, source=None):
    """The weekly 30-year fixed average: the latest number, the line, the source and the date of the latest point.
    `frame(p)` draws it with the line drawn to p (0-1) and the number counted along it. `source` replaces the
    source line (only the look's sample sheet uses it, to say its numbers are samples)."""
    from .news import SOURCE, pretty_date
    vals = [v for _, v in pts]
    n = len(vals)
    label = _caps(_words(g.get("label")) or "30-year fixed", G)
    source = source or f"Source: {SOURCE} · as of {pretty_date(pts[-1][0])}"
    line = tuple(G["accent_text"] or G["ink"])
    dot = tuple(G["dot"] or line)
    lo, hi = min(vals), max(vals)
    span = max(hi - lo, 0.05)
    lo, hi = lo - span * 0.10, hi + span * 0.10
    top = _top(G, full)
    if full:
        pad, es, ns, ss, lw = 16, 38, 176, 32, 9
        y = top
        y_label = y + es * 0.80
        y_num = y + es * 1.25 + ns * 0.76
        y_range = y_num + 62
        cy0 = y_range + 46
        rest = 50 + 54 + pad                       # the months under the chart, the source line, the padding
        ch = max(240, min(520, (h_max or 2000) - cy0 - rest))
        h = cy0 + ch + rest
        if h_max is not None and h > h_max and not force:
            raise NoFit("room")
        fl, fn, fs = Ft(G, es, 700), Ft(G, ns, number=True), Ft(G, ss, 500)
        cx0, cx1, cy1 = pad + 6, w - pad - 18, cy0 + ch
        y_axis, y_src = cy1 + 44, cy1 + 44 + 54
    else:
        pad, es, ss, lw = G["pad"], 30, 30, 6
        h = 270 if h_max is None else min(270, int(h_max))
        if h < top + 172:
            if not force:
                raise NoFit("room")
            h = top + 172
        cy0, cy1 = top + 8, h - pad - 50
        ns = int(min(104, (cy1 - top - 40) / 0.78))
        fl, fn, fs = Ft(G, es, 700), Ft(G, ns, number=True), Ft(G, ss, 500)
        y_label, y_num, y_src = top + es * 0.80, cy1 + 2, h - pad - 4
        cx0, cx1 = pad + max(tabw("0.00%", fn), tw(label, fl)) + 40, w - pad - 14
    base = Cv(w, h, G, card=not full, fill=G["full_bg"] if full else None)
    _bar(base, G, full, pad)
    base.text(pad, y_label, label, fl, G["eyebrow"])
    base.text(pad, y_src, source, fs, G["muted"])
    base.box(cx0, cy1 + 1, cx1, cy1 + 3, _mix(G["ink"], G["full_bg"] if full else G["card"], 0.80))
    if full:
        low, high = min(pts, key=lambda p: p[1]), max(pts, key=lambda p: p[1])
        base.text(pad, y_range, f"{n} weeks: low {low[1]:.2f}%, high {high[1]:.2f}%", fs, G["muted"])
        month = lambda iso: pretty_date(iso).split()[0] + " " + iso[:4]
        fa = Ft(G, 30, 500)
        base.text(cx0, y_axis, month(pts[0][0]), fa, G["muted"])
        base.text(cx1 - tw(month(pts[-1][0]), fa), y_axis, month(pts[-1][0]), fa, G["muted"])
    X = lambda j: (cx0 + (cx1 - cx0) * j / max(1, n - 1) + base.m) * SS
    Y = lambda v: (cy1 - (cy1 - cy0) * (v - lo) / (hi - lo) + base.m) * SS

    def frame(p):
        im = base.img.copy()
        k = max(0.0, min(1.0, p)) * (n - 1)
        i = min(int(k), n - 1)
        cur = vals[i] + (vals[min(i + 1, n - 1)] - vals[i]) * (k - i)
        xy = [(X(j), Y(vals[j])) for j in range(i + 1)] + ([(X(k), Y(cur))] if k - i > 1e-6 else [])
        if len(xy) >= 2:
            lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
            ImageDraw.Draw(lay).polygon(xy + [(xy[-1][0], base.P(cy1)), (xy[0][0], base.P(cy1))], fill=line[:3] + (38,))
            im.alpha_composite(lay)
            ImageDraw.Draw(im).line(xy, fill=line, width=lw * SS, joint="curve")
        d = ImageDraw.Draw(im)
        r = lw * SS * 0.5
        d.ellipse([xy[0][0] - r, xy[0][1] - r, xy[0][0] + r, xy[0][1] + r], fill=line)
        r = lw * SS * 1.6
        d.ellipse([xy[-1][0] - r, xy[-1][1] - r, xy[-1][0] + r, xy[-1][1] + r], fill=dot)
        base.text(pad, y_num, f"{cur:.2f}%", fn, G["ink"], tab=min(1.0, (1 - p) / 0.15), on=im)   # settles at the end
        return base.done(im)

    card = Card(base, frame(1.0))
    card.frame = frame
    return card


# ---------- the stat card ----------

def _arrow(c, x0, y0, x1, y1, t, fill):
    """A plain arrow from (x0, y0) to (x1, y1), t pixels thick."""
    d = ImageDraw.Draw(c.img)
    P = c.P
    ang = math.atan2(y1 - y0, x1 - x0)
    d.line([P(x0), P(y0), P(x1), P(y1)], fill=tuple(fill), width=round(t * SS))
    for da in (2.5, -2.5):
        d.line([P(x1), P(y1), P(x1 + math.cos(ang + da) * t * 3.4), P(y1 + math.sin(ang + da) * t * 3.4)],
               fill=tuple(fill), width=round(t * SS))
    r = t * SS / 2
    for x, y in ((x0, y0), (x1, y1)):
        d.ellipse([P(x) - r, P(y) - r, P(x) + r, P(y) + r], fill=tuple(fill))


def stat_card(g, G, w_max, h_max, mode="side", force=False):
    """One number and a label, or from -> to with the "to" value in the accent colour. mode: 'side' (stacked, narrow,
    beside the head), 'row' (side by side, above the head) or 'full' (stacked, the whole frame). `pre` is the card
    before the "to" value lands, `to_box` its place."""
    a, b = _words(g.get("from")), _words(g.get("to") or g.get("value"))
    label = _caps(_words(g.get("label")), G)
    full, stack = mode == "full", mode != "row"
    pad = 16 if full else max(20, G["pad"] - 4)
    top = pad if full else _top(G, False) - 4          # full screen: the big accent number is the accent's job
    chip = G["accent_text"] is None                    # the accent cannot be read on the card: it becomes a box
    sizes = range(280, 119, -10) if full else range(104, 63, -4) if mode == "row" else range(88, 51, -4)
    for size in sizes:
        fb, fa = Ft(G, size, number=True), Ft(G, round(size * (0.50 if full else 0.62 if stack else 0.72)), number=True)
        ls = max(40 if full else 30, round(size * (0.16 if full else 0.32)))
        fl = Ft(G, ls, 700)
        bw, aw = tw(b, fb) + (size * 0.36 if chip else 0), tw(a, fa) if a else 0
        gap = size * 0.9
        inner = max(bw, aw) if stack else bw + ((aw + gap) if a else 0)
        lab = wrap(label, fl, max(inner, 640 if full else 190 if stack else 300) * SS) if label else []
        inner = max([inner] + [tw(x, fl) for x in lab])
        bh, ah = size * 0.98, (fa.size / SS) * 0.98
        llh, lgap = round(ls * 1.22), ls * (1.1 if full else 0.6)
        h = top + ((ah + size * 0.62) if a and stack else 0) + bh + ((lgap + len(lab) * llh) if lab else 0) + pad
        w = inner + 2 * pad
        if w <= w_max and (h_max is None or h <= h_max) and len(lab) <= (3 if stack else 2):
            break
    else:
        if w > w_max or len(lab) > 3:
            raise NoFit("long", "the number and its label are too long for the card")
        if not force:
            raise NoFit("room")
    to_ink = G["accent_ink"] if chip else G["accent_text"]

    def draw(with_to):
        c = Cv(w, h, G, card=not full, fill=G["full_bg"] if full else None)
        cx, y, box = w / 2, top, None
        if stack:
            if a:
                c.text(cx - aw / 2, y + ah * 0.76, a, fa, G["muted"])
                y += ah
                box = [cx - bw / 2 - 6, y + 4, cx + bw / 2 + 6, y + size * 0.62 + bh + 4]
                if with_to:
                    _arrow(c, cx, y + size * 0.12, cx, y + size * 0.46, max(3, size * 0.06), G["muted"])
                y += size * 0.62
            bx = cx - bw / 2
        else:
            x = cx - (bw + ((aw + gap) if a else 0)) / 2
            if a:
                c.text(x, y + bh * 0.76, a, fa, G["muted"])
                box = [x + aw + 4, y - 2, x + aw + gap + bw + 8, y + bh + 6]
                if with_to:
                    _arrow(c, x + aw + gap * 0.22, y + bh * 0.50, x + aw + gap * 0.74, y + bh * 0.50,
                           max(3, size * 0.06), G["muted"])
                x += aw + gap
            bx = x
        if with_to or not a:
            if chip:
                c.box(bx, y + bh * 0.02, bx + bw, y + bh * 0.98, G["accent"], 8)
            c.text(bx + (size * 0.18 if chip else 0), y + bh * 0.76, b, fb, to_ink)
        y += bh
        if lab:
            y += lgap
            for ln in lab:
                c.text(cx - tw(ln, fl) / 2, y + ls * 0.78, ln, fl, G["label"])
                y += llh
        return c, box

    c, box = draw(True)
    card = Card(c)
    if a:
        card.pre = draw(False)[0].done()
        card.to_box = (max(0, int(box[0] + c.m)), max(0, int(box[1] + c.m)), int(box[2] + c.m) + 1, int(box[3] + c.m) + 1)
    return card


# ---------- the lower third ----------

def lower_third_card(g, G, w_max, h_max, force=False):
    """Name, title and one line (an NMLS number, a disclosure), marked with the accent colour. When the space is
    low, the title and the line share a row. Nothing is drawn under 30 px."""
    name, title, line = _words(g.get("name")), _words(g.get("title")), _words(g.get("line"))
    pad = 22
    mark = TAB if G.get("tab") else 8 + 14             # the card's own top rule, or a short bar above the name
    tries = [(False, s) for s in range(58, 45, -2)] + ([(True, s) for s in range(54, 43, -2)] if title and line else [])
    for joined, size in tries:
        s2 = max(30, round(size * 0.60))
        rows = [title + "  ·  " + line] if joined else [r for r in (title, line) if r]
        fn, f2, f2b = Ft(G, size), Ft(G, s2, 500), Ft(G, s2, 700)
        w = max([tw(name, fn)] + [tw(r, f2b) for r in rows]) + 2 * pad
        h = pad + mark + size * 1.02 + len(rows) * round(s2 * 1.30) + pad * 0.7
        if w <= w_max and (h_max is None or h <= h_max):
            break
    else:
        if w > w_max:
            raise NoFit("long", "the name, title or line is too long for the lower third")
        if not force:
            raise NoFit("room")
    c = Cv(max(w, 300), h, G)
    if not G.get("tab"):
        c.box(pad, pad, pad + 64, pad + 8, G["accent"], 0)
    y = pad + mark
    c.text(pad, y + size * 0.78, name, fn, G["ink"])
    y += size * 1.02
    for i, r in enumerate(rows):
        first = i == 0 and title and not joined
        c.text(pad, y + s2 * 0.92, r, f2b if first else f2, (G["eyebrow"] if first else G["muted"]))
        y += round(s2 * 1.30)
    return Card(c)
