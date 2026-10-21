"""Listicle reel: the whole payload on screen, static, all at once, over one real clip.

  {"clip": "...", "title": "...", "items": ["...", ...], "small": "Source: ..." (optional), "punchline": "..." (optional)}
  {"clip": "...", "title": "...", "columns": [{"header": "RENTING:", "color": "red", "items": [...]},
                                              {"header": "OWNING:", "color": "green", "items": [...]}], ...}

7 s unless the spec sets "duration" (a 13-14 row table can earn 10-12 s)."""
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw
from .common import (W, H, SAFE_TOP, SAFE_BOTTOM, X264, die, run, need, clear_rotation, video_info,
                     bg_input, bg_filter)
from .text import style_font, wrap, block_height, draw_lines


def rows(spec):
    if spec.get("columns"):
        return max(len(c["items"]) for c in spec["columns"])
    return len(spec.get("items") or [])


def duration_for(spec, lk=None):
    """7 s unless the spec says otherwise (Cyrus, 2026-10-15: listicles and b-rolls are 7 s unless noted)."""
    if spec.get("duration"):
        return float(spec["duration"])
    return float((lk or {}).get("duration_s", 7.0))


def check(spec):
    warn = []
    if not spec.get("title"):
        die("a listicle needs a 'title'")
    if not (spec.get("items") or spec.get("columns")):
        die("a listicle needs 'items' (or 'columns')")
    if not spec.get("clip"):
        die("a listicle needs 'clip': the background footage")
    n = rows(spec)
    if n > 14:
        die(f"{n} rows: a listicle holds 14 at most. Split it into two posts or cut the weakest rows.")
    if n < 5 and not spec.get("columns"):
        warn.append(f"only {n} items: the format wants 5 or more")
    if len(spec["title"].split()) > 8:
        warn.append("the title is over 8 words: it should read in one second")
    for it in spec.get("items") or [x for c in spec.get("columns", []) for x in c["items"]]:
        words = [w for w in it.split() if not any(ch.isdigit() for ch in w)]
        if len(words) > 10:
            warn.append(f"a long row ({it[:30]}…): about 8 words per line keeps the type big")
    return warn


def card(spec, lk):
    L = lk["listicle"]
    styles = {**lk["styles"], **L.get("header_styles", {})}
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def part(name):
        p = L[name]
        st = styles[p.get("style", "white")] if p.get("style") else {}
        return p, st, style_font(lk, st, p["size"], p.get("weight", 500))

    tp, tst, tf = part("title")
    tl = wrap(spec["title"], tf, L["max_width"])
    th = block_height(tl, tf, tst, lk)
    draw_lines(img, tl, tf, tst, lk, W / 2, L["title"]["center_y"] * H - th / 2)
    ip, ist, itf = part("item")
    y0 = L["list_top"] * H
    if spec.get("columns"):
        hp = L["header"]
        cols = spec["columns"]
        cw = L["column_width"]
        bottom = y0
        for i, col in enumerate(cols):                 # columns are left-aligned
            hst = styles.get(col.get("color", "black")) or die(f"column colour {col.get('color')!r} is not in this look")
            hf = style_font(lk, hst, hp["size"], hp.get("weight", 700))
            x = W / 2 + (i - (len(cols) - 1) / 2) * (cw + 30) - cw / 2 + lk["pad_x"]
            y = draw_lines(img, [col["header"]], hf, hst, lk, x, y0, align="left") + ip["gap"] * 2
            for it in col["items"]:
                y = draw_lines(img, wrap(it, itf, cw - 2 * lk["pad_x"]), itf, ist, lk, x, y, align="left") + ip["gap"]
            bottom = max(bottom, y)
    else:
        y = y0
        for it in spec["items"]:
            y = draw_lines(img, wrap(it, itf, L["max_width"]), itf, ist, lk, W / 2, y) + ip["gap"]
        bottom = y
    if spec.get("small"):
        sp, sst, sf = part("small")
        bottom = draw_lines(img, wrap(spec["small"], sf, L["max_width"]), sf, sst, lk, W / 2, bottom + 6) + 24
    if spec.get("punchline"):
        pp, pst, pf = part("punchline")
        pl = wrap(spec["punchline"], pf, L["max_width"])
        top = bottom + 36
        if top + block_height(pl, pf, pst, lk) > SAFE_BOTTOM:
            die(f"the list is too long for this look: the punchline would end at "
                f"y{int(top + block_height(pl, pf, pst, lk))}, below the feed-safe y{SAFE_BOTTOM}. Cut rows or shorten them.")
        draw_lines(img, pl, pf, pst, lk, W / 2, top)
    elif bottom > SAFE_BOTTOM:
        die(f"the list is too long for this look: it ends at y{int(bottom)}, below the feed-safe y{SAFE_BOTTOM}")
    bb = img.getbbox()
    if bb and bb[1] < SAFE_TOP:
        die(f"the title starts at y{bb[1]}, above the feed-safe y{SAFE_TOP}: shorten the title")
    return _under_panel(img, L["panel"]) if L.get("panel") else img


def _under_panel(img, pn):
    """One rounded see-through panel under everything drawn, laid UNDER the text so no stroke cuts into it."""
    x0, y0, x1, y1 = img.getbbox()
    w = pn["width"]
    base = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(base).rounded_rectangle([W / 2 - w / 2, y0 - pn["pad"], W / 2 + w / 2, y1 + pn["pad"]],
                                           radius=pn["radius"], fill=tuple(pn["fill"]))
    base.alpha_composite(img)
    return base


def render(spec, lk, out, log=print):
    for w in check(spec):
        log("warning: " + w)
    need("ffmpeg")
    clip = spec["clip"]
    info = video_info(clip)
    dur = duration_for(spec, lk)
    tmp = Path(tempfile.mkdtemp(prefix="gre-listicle-"))
    png = tmp / "card.png"
    card(spec, lk).save(png)
    start = float(spec.get("start", 0))
    loop = bool(spec.get("loop") or (info["duration"] and info["duration"] - start < dur))
    vf = f"[0:v]{bg_filter(clip, dur, info)},format=yuv420p[b];[b][1:v]overlay=0:0[v]"
    run(["ffmpeg", "-loglevel", "error", "-y", *bg_input(clip, start, dur, loop),
         "-loop", "1", "-t", str(dur), "-i", png, "-filter_complex", vf, "-map", "[v]",
         "-an", "-t", str(dur), *X264, out])
    clear_rotation(out)
    log(f"rendered {out} ({dur:.1f} s for {rows(spec)} rows, silent)")
    return out
