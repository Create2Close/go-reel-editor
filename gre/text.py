"""Type on the frame: wrapping without orphans, boxed lines (the Instagram text style) and outline lines
(no box: a fill, a hard dark edge, a soft drop shadow). Shared by every format."""
from PIL import Image, ImageDraw, ImageFilter
from .common import font


def style_font(lk, st, size=None, weight=None):
    """The look's font, or the style's own; a style can scale the size (an outline serif reads smaller)."""
    return font(st.get("font", lk["font"]), (size or lk["size"]) * st.get("size_scale", 1),
                weight or st.get("weight") or lk.get("weight", 500), st.get("opsz", lk.get("opsz")))


def _wrap(text, f, max_w, d):
    out = []
    for para in text.split("\n"):
        line = ""
        for w in para.split():
            t = (line + " " + w).strip()
            if d.textlength(t, font=f) <= max_w or not line:
                line = t
            else:
                out.append(line)
                line = w
        out.append(line)
    return out


def wrap(text, f, max_w):
    """The fewest lines that fit max_w, then the narrowest width that keeps that many lines: no orphan words."""
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    lines = _wrap(text, f, max_w, d)
    if len(lines) < 2 or "\n" in text:
        return lines
    lo, hi = 1, int(max_w)
    while lo < hi:
        mid = (lo + hi) // 2
        if len(_wrap(text, f, mid, d)) <= len(lines):
            hi = mid
        else:
            lo = mid + 1
    return _wrap(text, f, lo, d)


def textlength(s, f):
    return ImageDraw.Draw(Image.new("RGBA", (8, 8))).textlength(s, font=f)


def line_height(f, st, lk):
    asc, desc = f.getmetrics()
    return round((asc + desc) * st.get("leading", 0.9)) if st.get("outline") else asc + desc + 2 * lk["pad_y"]


def draw_line(img, x, y, lh, text, f, st, lk):
    """One line, left edge x, top y: in its own tight box, or (outline style) no box: fill + edge + shadow."""
    d = ImageDraw.Draw(img)
    if not st.get("outline"):
        d.rectangle([x - lk["pad_x"], y, x + d.textlength(text, font=f) + lk["pad_x"], y + lh], fill=tuple(st["box"]))
        d.text((x, y + lk["pad_y"]), text, font=f, fill=tuple(st["ink"]))
        return
    s = f.size
    edge = max(1, round(s * st["edge_w"])) if st.get("edge_w", 0.07) > 0 else 0
    sh = st.get("shadow")
    if sh:
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((x, y + s * sh.get("dy", 0.04)), text, font=f, fill=tuple(sh["color"]),
                                   stroke_width=edge + round(s * sh.get("spread", 0.02)), stroke_fill=tuple(sh["color"]))
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(s * sh.get("blur", 0.03))))
    d.text((x, y), text, font=f, fill=tuple(st["ink"]), stroke_width=edge, stroke_fill=tuple(st.get("edge", (0, 0, 0, 255))))
    if st.get("bold"):
        d.text((x, y), text, font=f, fill=tuple(st["ink"]), stroke_width=max(1, round(s * st["bold"])),
               stroke_fill=tuple(st["ink"]))


def draw_lines(img, lines, f, st, lk, cx, top, align="center"):
    """Stack lines centred on cx (or left-aligned at cx); return the bottom y."""
    lh = line_height(f, st, lk)
    y = top
    for ln in lines:
        tw = textlength(ln, f)
        draw_line(img, cx - tw / 2 if align == "center" else cx, y, lh, ln, f, st, lk)
        y += lh + lk["line_gap"]
    return y - lk["line_gap"]


def block_height(lines, f, st, lk):
    return len(lines) * line_height(f, st, lk) + (len(lines) - 1) * lk["line_gap"]
