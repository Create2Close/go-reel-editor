"""Checklist: the listicle's second layout. One centred column over the clip: a title, three to six full-sentence
points with a check mark, a closing line. Every line of text sits in its own rounded box that hugs it, and the boxes
of a two-line point touch, so the point reads as one stepped shape.

  {"layout": "checklist", "clip": "...", "title": "...", "items": ["...", ...], "punchline": "📌 ..." (optional),
   "bullet": "✅" (the default; "" for none), "duration": s, "punchline_at": s, "center_y": 0-1}

The title and every point are on screen from the first frame; the closing line cuts in three quarters through and
stays. The look draws it: its font, its `red` (or the member's `accent`) box for the title, its `white` box for the
points, its `black` box for the closing line, and the numbers in its optional `listicle.checklist` block."""
import re, tempfile
from pathlib import Path
from PIL import Image, ImageDraw
from .common import W, H, SAFE_TOP, SAFE_BOTTOM, X264, die, run, need, clear_rotation, video_info, bg_input, bg_filter
from .text import style_font
from . import xreel

MAX_ITEMS, MAX_LINES = 6, 2
BULLET = "✅"
WORDS_PER_SECOND = 6.0      # the reference reel: 61 words on screen in 10.0 s
MIN_S, MAX_S = 7.0, 12.0    # the listicle's own range
PUNCHLINE_AT = 0.75         # the closing line cuts in three quarters through
FALLBACK = {"title": ([215, 25, 32, 255], [255, 255, 255, 255]), "item": ([255, 255, 255, 255], [0, 0, 0, 255]),
            "punchline": ([0, 0, 0, 255], [255, 255, 255, 255])}


def numbers(lk, size=None):
    """This layout's numbers: the look's `listicle.checklist` block, and for anything it leaves out a value worked
    out from the look's own type size, so a look made before this layout existed still draws one. `size` asks for
    the same design with smaller type (everything shrinks with it)."""
    L = lk["listicle"]
    c = dict(L.get("checklist") or {})
    s0 = c.get("size") or round(lk["size"] * 0.86)
    d = {"size": s0, "pitch": round(s0 * 1.2), "pad_x": round(s0 * 0.4), "pad_y": round(s0 * 0.16),
         "radius": round(s0 * 0.24), "gap": round(s0 * 0.48)}
    d = {k: c.get(k, v) for k, v in d.items()}
    k = (size or s0) / s0
    out = {n: v * k for n, v in d.items()}
    out["size"] = size or s0
    out["min_size"] = c.get("min_size") or round(s0 * 0.84)
    out["weight"] = c.get("weight") or max(700, lk.get("weight", 500))
    out["max_width"] = c.get("max_width") or L.get("max_width", 930)      # the widest box, edge to edge
    out["center_y"] = c.get("center_y", 0.494)
    out["bullet"] = c.get("bullet", BULLET)
    styles = {**L.get("header_styles", {}), **lk["styles"]}
    for part, names in (("title", ("accent", "red", "black")), ("item", ("white",)), ("punchline", ("black",))):
        st = next((styles[n] for n in ([c[part]] if c.get(part) else names) if n in styles), None)
        if c.get(part) and st is None:
            die(f"style {c[part]!r} is not in this look. Styles: {', '.join(styles)}")
        box, ink = (st["box"], st["ink"]) if st and st.get("box") else FALLBACK[part]   # an outline style has no box
        out[part] = {"box": tuple(box), "ink": tuple(ink), "st": st if st and st.get("box") else {}}
    return out


# ---------- type with emoji in it ----------

_UNIT = [None, 1.0]         # the emoji font the check mark was measured on, and its height per px of size
_EMOJI = {}


def _emoji(chunk, size):
    """An emoji at the size it has beside `size` px type: 0.84 of the type size for a full-square one, measured on
    the check mark so Apple's emoji (a Mac) and the bundled Noto (everywhere else) come out the same size."""
    if xreel._EF is None or _UNIT[0] is not xreel._EF:
        u = xreel._emoji_img(BULLET, 100).height / 100          # also loads the emoji font
        _UNIT[:] = [xreel._EF, u]
        _EMOJI.clear()
    key = (chunk, round(size, 2))
    if key not in _EMOJI:
        _EMOJI[key] = xreel._emoji_img(chunk, 0.84 * size / _UNIT[1])
    return _EMOJI[key]


def _width(text, f):
    return sum(_emoji(c, f.size).width + 0.12 * f.size if e else f.getlength(c) for e, c in xreel._runs(text))


def _draw(img, x, mid, text, f, ink):
    """One line, left edge x, its ink (capital top to descender) centred on y = mid. Emoji sit centred on it too."""
    y = mid - (f.getbbox("H")[1] + f.getbbox("gjpqy")[3]) / 2
    d = ImageDraw.Draw(img)
    for e, c in xreel._runs(text):
        if e:
            em = _emoji(c, f.size)
            img.alpha_composite(em, (round(x - 0.08 * f.size), round(mid - em.height / 2)))
            x += em.width + 0.12 * f.size
        else:
            d.text((x, y), c, font=f, fill=ink)
            x += f.getlength(c)


def _greedy(words, f, max_w):
    lines, line = [], ""
    for w in words:
        t = (line + " " + w).strip()
        if not line or _width(t, f) <= max_w:
            line = t
        else:
            lines.append(line)
            line = w
    return lines + [line]


def wrap(text, f, max_w, lead=""):
    """Balanced lines: the fewest that fit max_w, then the narrowest width that keeps that many, so two lines come
    out a similar width instead of one long line and one short word. `lead` (the bullet) stays with the first word.
    A line break typed in the text is kept as typed."""
    out = []
    for n, para in enumerate(text.split("\n")):
        words = para.split()
        if n == 0 and lead and words:
            words[0] = f"{lead} {words[0]}"
        if not words:
            continue
        wide = max(words, key=lambda w: _width(w, f))
        if _width(wide, f) > max_w:
            die(f"{wide.replace(lead, '').strip()!r} is too wide for the frame in one piece: shorten it or split it "
                f"into words.")
        lines = _greedy(words, f, max_w)
        if len(lines) > 1 and "\n" not in text:
            lo, hi = 1, int(max_w)
            while lo < hi:
                mid = (lo + hi) // 2
                if len(_greedy(words, f, mid)) <= len(lines):
                    hi = mid
                else:
                    lo = mid + 1
            lines = _greedy(words, f, lo)
        out += lines
    return out


# ---------- the stack ----------

def _bullet(spec, C, item):
    """The mark before a point: the spec's "bullet", else the look's, else the check mark. None for "" or false,
    and none for a point that already starts with an emoji of its own."""
    b = spec["bullet"] if "bullet" in spec else C["bullet"]
    if b in (None, False):
        return ""
    if not isinstance(b, str):
        die("'bullet' is one emoji or a few characters, or \"\" for none")
    return "" if xreel._is_emoji(item.strip()[:1] or " ") else b.strip()


def _stack(spec, lk, size):
    """Every block at this type size, top to bottom, as [part, lines, font, top y]; this size's numbers; and a
    plain-words reason when it does not fit (None when it does)."""
    C = numbers(lk, size)
    blocks = [("title", spec["title"], "")]
    blocks += [("item", it, _bullet(spec, C, it)) for it in spec["items"]]
    if spec.get("punchline"):
        blocks.append(("punchline", spec["punchline"], ""))
    out, why = [], None
    for part, text, lead in blocks:
        f = style_font(lk, C[part]["st"], size, C["weight"])
        lines = wrap(text.strip(), f, C["max_width"] - 2 * C["pad_x"], lead)
        if len(lines) > MAX_LINES and not why:
            name = {"title": "the title", "item": "the point", "punchline": "the closing line"}[part]
            why = (f"{name} {text.strip()[:40]!r} needs {len(lines)} lines: {MAX_LINES} is the most a checklist "
                   f"holds. Shorten it to about {round(len(text.split()) * MAX_LINES / len(lines)) - 1} words.")
        out.append([part, lines, f, 0])
    heights = [round(len(b[1]) * C["pitch"] + 2 * C["pad_y"]) for b in out]
    gap = round(C["gap"])
    total = sum(heights) + gap * (len(out) - 1)
    if total > SAFE_BOTTOM - SAFE_TOP and not why:
        why = (f"the checklist is {total} px tall and the feed-safe band (y{SAFE_TOP}-{SAFE_BOTTOM}) is "
               f"{SAFE_BOTTOM - SAFE_TOP}: cut a point or shorten the long ones.")
    cy = spec.get("center_y")
    y = round((C["center_y"] if cy is None else float(cy)) * H - total / 2)
    if cy is None:
        y = max(min(y, SAFE_BOTTOM - total), SAFE_TOP)             # near the look's centre line, inside the band
    elif (y < SAFE_TOP or y + total > SAFE_BOTTOM) and not why:
        why = (f"at that height the checklist would sit at y{y}-{y + total}, outside the feed-safe band "
               f"y{SAFE_TOP}-{SAFE_BOTTOM}. Move it back toward the middle.")
    for b, h in zip(out, heights):
        b[3] = y
        y += h + gap
    return out, C, why


def fit(spec, lk):
    """The stack at the look's type size, or the largest smaller size (never under its min_size) at which every
    point is two lines at most and the whole stack fits the feed-safe band. Refuses, in plain words, when none does."""
    C = numbers(lk)
    why = None
    small = min(C["min_size"], C["size"])
    for size in dict.fromkeys([C["size"], *range(int(C["size"]) - 2, int(small), -2), small]):
        blocks, Cs, w = _stack(spec, lk, size)
        if not w:
            return blocks, Cs
        why = why or w                                  # say what was wrong at the look's own size
    die(why)


def _box(img, x0, y0, x1, y1, radius, fill):
    """A rounded box with smooth corners (drawn four times the size, then scaled down)."""
    x0, y0, x1, y1 = round(x0), round(y0), round(x1), round(y1)
    w, h, k = x1 - x0, y1 - y0, 4
    m = Image.new("L", (w * k, h * k), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * k - 1, h * k - 1], radius=min(radius * k, w * k / 2, h * k / 2), fill=255)
    tile = Image.new("RGBA", (w, h), fill)
    tile.putalpha(m.resize((w, h), Image.LANCZOS).point(lambda v: v * fill[3] // 255))
    img.alpha_composite(tile, (x0, y0))


def _lines(blocks, C):
    """Every line of the stack: (part, box x0, y0, x1, y1, the y its ink is centred on, text, font). A block's first
    box starts at its top and its last ends at its bottom; between two lines the boxes meet, so they read as one shape."""
    nudge = round(0.04 * C["size"])                     # the ink sits a touch high in its box, as hand-set text does
    for part, lines, f, top in blocks:
        n = len(lines)
        for i, ln in enumerate(lines):
            half = _width(ln, f) / 2 + C["pad_x"]
            band = top + C["pad_y"] - nudge + i * C["pitch"]
            y0 = top if i == 0 else band
            y1 = top + n * C["pitch"] + 2 * C["pad_y"] if i == n - 1 else band + C["pitch"]
            yield part, round(W / 2 - half), round(y0), round(W / 2 + half), round(y1), band + C["pitch"] / 2, ln, f


def boxes(spec, lk):
    """Every line's box as (part, x0, y0, x1, y1)."""
    return [ln[:5] for ln in _lines(*fit(spec, lk))]


def card(spec, lk, part="all"):
    """The stack on a clear 1080x1920 frame. part: "all" (the preview), "list" (the title and the points, on screen
    from the first frame) or "punchline" (the closing line alone, laid over the list when it cuts in)."""
    blocks, C = fit(spec, lk)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    show = [ln for ln in _lines(blocks, C) if part == "all" or (ln[0] == "punchline") == (part == "punchline")]
    for kind, x0, y0, x1, y1, mid, ln, f in show:       # every box first, then the type, so no box covers a letter
        _box(img, x0, y0, x1, y1, C["radius"], C[kind]["box"])
    for kind, x0, y0, x1, y1, mid, ln, f in show:
        _draw(img, x0 + C["pad_x"], mid, ln, f, C[kind]["ink"])
    return img


# ---------- checks, length, render ----------

def words(spec):
    """Words a viewer reads: the title, the points and the closing line (an emoji alone is not a word)."""
    text = " ".join([spec.get("title", ""), *spec.get("items", []), spec.get("punchline") or ""])
    return sum(1 for w in text.split() if re.search(r"\w", w))


def duration_for(spec, lk=None):
    """About six words a second (the reference reel: 61 words, 10.0 s), to the half second, 7 s at least and 12 s
    at most. "duration" in the spec wins."""
    if spec.get("duration"):
        return float(spec["duration"])
    return min(MAX_S, max(MIN_S, round(words(spec) / WORDS_PER_SECOND * 2) / 2))


def punchline_at(spec, dur):
    """When the closing line cuts in: three quarters through, or the spec's "punchline_at" seconds (0 = from the start)."""
    if spec.get("punchline_at") is not None:
        return min(max(0.0, float(spec["punchline_at"])), dur)
    return round(dur * PUNCHLINE_AT * 30) / 30


def check(spec):
    warn = []
    if not spec.get("title"):
        die("a listicle needs a 'title'")
    if spec.get("columns"):
        die("the checklist layout is one list: give it 'items', or drop \"layout\": \"checklist\" for two columns")
    items = spec.get("items") or die("a listicle needs 'items'")
    if not spec.get("clip"):
        die("a listicle needs 'clip': the background footage")
    if any(not isinstance(it, str) or not it.strip() for it in items):
        die("every point in 'items' is a line of text")
    if len(items) > MAX_ITEMS:
        die(f"{len(items)} points: a checklist holds {MAX_ITEMS} at most, two lines each. Cut the weakest, or use "
            f"the plain list for short rows (it holds 14).")
    if len(items) < 3:
        warn.append(f"only {len(items)} points: a checklist wants 3 to 6")
    if spec.get("small"):
        warn.append("the checklist layout has no small line: 'small' is not shown (put the source in the caption)")
    if not spec.get("punchline"):
        warn.append("no closing line: a checklist usually ends on one (\"Save this before...\")")
    return warn


def render(spec, lk, out, log=print):
    for w in check(spec):
        log("warning: " + w)
    need("ffmpeg")
    clip = spec["clip"]
    info = video_info(clip)
    dur = duration_for(spec, lk)
    tmp = Path(tempfile.mkdtemp(prefix="gre-checklist-"))
    card(spec, lk, "list").save(tmp / "list.png")
    start = float(spec.get("start", 0))
    loop = bool(spec.get("loop") or (info["duration"] and info["duration"] - start < dur))
    inputs = [*bg_input(clip, start, dur, loop), "-loop", "1", "-t", str(dur), "-i", tmp / "list.png"]
    fc = [f"[0:v]{bg_filter(clip, dur, info)},format=yuv420p[b]", "[b][1:v]overlay=0:0[v]"]
    at = None
    if spec.get("punchline"):                          # a hard cut, no fade: on from `at` to the end
        at = punchline_at(spec, dur)
        card(spec, lk, "punchline").save(tmp / "punchline.png")
        inputs += ["-loop", "1", "-t", str(dur), "-i", tmp / "punchline.png"]
        fc = [fc[0], "[b][1:v]overlay=0:0[l]", f"[l][2:v]overlay=0:0:enable='gte(t,{at - 0.001:.3f})'[v]"]
    run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", "[v]",
         "-an", "-t", str(dur), *X264, out])
    clear_rotation(out)
    log(f"rendered {out} ({dur:.1f} s for {len(spec['items'])} points"
        + (f", the closing line from {at:.1f} s" if at is not None else "") + ", silent)")
    return out
