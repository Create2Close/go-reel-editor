"""X-reel: a news story as a styled X post (avatar, name, badge, handle, 2-3 lines, one image). STATIC: no zoom, no
motion, one card held 6-7 s (Cyrus, 2026-10-21). The whole card sits inside the reel safe zone (x65-1015, y300-1248:
the top 14 %, bottom 35 % and sides 6 % stay clear, and the Facebook/Instagram feed crops with them), centred in it.
The story lives in the caption.

  spec = {"text": "BREAKING: ...\n\nHere's what it means 👇", "image": "news.jpg",
          "image_header": "optional strip above the image", "duration": 6, "mode": "dark" | "light",
          "name": "...", "handle": "@...", "avatar": "me.jpg"}     # name/handle/avatar default to the profile

Organic posts only: never put X-post chrome inside a paid ad."""
import math, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .common import (W, H, REEL_LEFT, REEL_RIGHT, REEL_TOP, REEL_BOTTOM, X264, FONTS, HOME, die, run, need,
                     font_file, profile)

APPLE_EMOJI = Path("/System/Library/Fonts/Apple Color Emoji.ttc")


def _emoji_font():
    if APPLE_EMOJI.exists():                     # sbix: any size works
        return ImageFont.truetype(str(APPLE_EMOJI), 160), 160
    return ImageFont.truetype(str(FONTS / "NotoColorEmoji.ttf"), 109), 109   # CBDT bitmaps exist only at 109


def _is_emoji(ch):
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or o in (0x2B50, 0x2B55, 0x203C, 0x2049, 0x2B06, 0x2B07, 0x2934, 0x2935)


def _runs(text):
    out = []
    for ch in text:
        if ord(ch) in (0xFE0F, 0x200D) or 0x1F3FB <= ord(ch) <= 0x1F3FF:
            if out:
                out[-1][1] += ch
            continue
        e = _is_emoji(ch)
        if out and out[-1][0] == e and not e:
            out[-1][1] += ch
        elif out and e and out[-1][0] and out[-1][1].endswith("‍"):
            out[-1][1] += ch
        else:
            out.append([e, ch])
    return out


_EF = None


def _emoji_img(chunk, size):
    global _EF
    _EF = _EF or _emoji_font()
    f, n = _EF
    im = Image.new("RGBA", (n * 3, n + 40), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((0, 0), chunk, font=f, embedded_color=True)
    im = im.crop(im.getbbox() or (0, 0, n, n))
    s = size / n
    return im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)


def _tlen(d, s, f, track):
    return d.textlength(s, font=f) + track * len(s)


def _text(d, xy, s, f, fill, track=0.0):
    if not track:
        d.text(xy, s, font=f, fill=fill)
        return
    for i, ch in enumerate(s):
        d.text((xy[0] + d.textlength(s[:i], font=f) + track * i, xy[1]), ch, font=f, fill=fill)


def _width(d, text, f, size, track=0.0):
    return sum(size * 1.3 if e else _tlen(d, c, f, track) for e, c in _runs(text))


def _wrap(d, text, f, size, max_w, track=0.0):
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            t = (line + " " + word).strip()
            if not line or _width(d, t, f, size, track) <= max_w:
                line = t
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def _draw_text(img, xy, text, f, size, fill, track=0.0):
    d = ImageDraw.Draw(img)
    x, y = xy
    for e, c in _runs(text):
        if e:
            em = _emoji_img(c, size * 1.15)
            x += size * 0.2 if x > xy[0] else 0
            img.alpha_composite(em, (round(x), round(y + size * 0.06)))
            x += em.width + size * 0.08
        else:
            _text(d, (x, y), c, f, fill, track)
            x += _tlen(d, c, f, track)


def _place(d, xy, s, f, fill, track):
    """Draw s so its capital-letter top lands on y (positions were measured off real frames)."""
    _text(d, (xy[0], xy[1] - f.getbbox("H")[1]), s, f, fill, track)


def identity(spec):
    pr = profile()
    name = spec.get("name") or pr.get("name")
    handle = spec.get("handle") or pr.get("handle")
    avatar = spec.get("avatar") or pr.get("avatar")
    missing = [k for k, v in (("name", name), ("handle", handle), ("avatar", avatar)) if not v]
    if missing:
        die("an X-reel needs your " + ", ".join(missing) + ". Tell Claude your name as it shows on X/Instagram, "
            "your @handle and a headshot file, once: it saves them with `gre profile`.")
    avatar = Path(avatar).expanduser()
    if not avatar.is_absolute():
        avatar = HOME / avatar
    if not avatar.exists():
        die(f"avatar not found: {avatar}")
    if not handle.startswith("@"):
        handle = "@" + handle
    return name, handle, avatar


def check(spec):
    warn = []
    if not spec.get("text"):
        die("an X-reel needs 'text': the hook label, the hook and the tease line")
    if not spec.get("image"):
        die("an X-reel needs 'image': the news photo (the image sells the headline)")
    if not Path(spec["image"]).exists():
        die(f"image not found: {spec['image']}")
    paras = [p for p in spec["text"].split("\n") if p.strip()]
    if len(paras) > 4:
        warn.append(f"{len(paras)} lines of post text: the format is 2-3 lines, never a block. A paragraph gets swiped.")
    if "👇" not in spec["text"]:
        warn.append("no 👇 tease line: the format ends the post text on a line that sends viewers to the caption")
    return warn


def card(spec, lk):
    X = lk["xreel"]
    name, handle, avatar = identity(spec)
    light = spec.get("mode", X.get("mode", "dark")) == "light"
    bg, ink = ((255, 255, 255, 255), (15, 20, 25)) if light else ((0, 0, 0, 255), (255, 255, 255))
    reg = ImageFont.truetype(str(font_file(X["font"])), X["text_size"])
    bold = ImageFont.truetype(str(font_file(X["font_bold"])), X["name_size"])
    handle_f = ImageFont.truetype(str(font_file(X["font"])), X["handle_size"])
    img = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(img)
    x0 = X["left"]
    tr = X.get("tracking", 0.0) * X["text_size"]
    tx = X.get("text_left", x0)
    lines = _wrap(d, spec["text"], reg, X["text_size"], W - tx - x0, tr)
    lh = X["text_size"] * X["leading"]
    iw = X.get("image_width", W - 2 * x0)
    pic = Image.open(spec["image"]).convert("RGBA")
    pic = pic.resize((iw, round(pic.height * iw / pic.width)), Image.LANCZOS)
    hdr_h = round(X["header_size"] * 2.0) if spec.get("image_header") else 0
    text_h = X["body_dy"] + (len(lines) - 1) * lh + X["image_gap"] + hdr_h
    room = REEL_BOTTOM - REEL_TOP - text_h
    if room < 240:
        die(f"the post text is too long for the reel safe zone (y{REEL_TOP}-{REEL_BOTTOM}): keep it to 2-3 short lines")
    if pic.height > room:                          # a tall photo is cropped, biased up: faces sit in the top third
        c = int((pic.height - room) * spec.get("crop_y", 0.2))
        pic = pic.crop((0, c, pic.width, c + int(room)))
    top = int(REEL_TOP + (REEL_BOTTOM - REEL_TOP - text_h - pic.height) // 2)   # the card, centred in the safe zone
    while _tlen(d, name, bold, 0) + X["name_left"] + X.get("badge_gap", 10) + X["badge_size"] > REEL_RIGHT \
            and bold.size > 30:                    # a long name shrinks rather than run under the buttons
        bold = ImageFont.truetype(str(font_file(X["font_bold"])), bold.size - 2)
    av = X["avatar_size"]
    a = Image.open(avatar).convert("RGBA")
    s = min(a.size)
    a = a.crop(((a.width - s) // 2, (a.height - s) // 2, (a.width + s) // 2, (a.height + s) // 2)).resize((av, av), Image.LANCZOS)
    m = Image.new("L", (av, av), 0)
    ImageDraw.Draw(m).ellipse([0, 0, av - 1, av - 1], fill=255)
    img.paste(a, (x0, top), m)
    nx = X["name_left"]
    _place(d, (nx, top + X["name_dy"]), name, bold, ink, 0)
    bx = nx + _tlen(d, name, bold, 0) + X.get("badge_gap", 10)
    bs = X["badge_size"]
    by = top + X["name_dy"] + X.get("badge_dy", 0)
    cx, cy, r = bx + bs / 2, by + bs / 2, bs / 2           # X's scalloped verified badge
    d.polygon([(cx + r * (0.9 + 0.1 * math.cos(8 * t)) * math.cos(t), cy + r * (0.9 + 0.1 * math.cos(8 * t)) * math.sin(t))
               for t in (k * math.pi / 64 for k in range(128))], fill=tuple(X["check"]))
    d.line([(bx + bs * 0.27, by + bs * 0.52), (bx + bs * 0.44, by + bs * 0.68), (bx + bs * 0.74, by + bs * 0.34)],
           fill=(255, 255, 255), width=max(3, bs // 8), joint="curve")
    _place(d, (nx, top + X["handle_dy"]), handle, handle_f, tuple(X["handle_color"]), 0)
    y = top + X["body_dy"]
    off = reg.getbbox("H")[1]
    for ln in lines:
        _draw_text(img, (tx, round(y - off)), ln, reg, X["text_size"], ink, tr)
        y += lh
    y = round(y - lh + X["image_gap"])
    ix = X.get("image_left", x0)
    if hdr_h:
        hf = ImageFont.truetype(str(font_file(X["font_bold"])), X["header_size"])
        d.rectangle([ix, y, ix + iw, y + hdr_h], fill=(255, 255, 255) if not light else (15, 20, 25))
        d.text((ix + 24, y + (hdr_h - X["header_size"]) / 2 - 4), spec["image_header"], font=hf,
               fill=(20, 20, 20) if not light else (255, 255, 255))
        y += hdr_h
    rad = X.get("image_radius", 0)
    if rad:
        mk = Image.new("L", pic.size, 0)
        ImageDraw.Draw(mk).rounded_rectangle([0, 0, pic.width - 1, pic.height - 1], radius=rad, fill=255)
        pic.putalpha(mk)
    img.alpha_composite(pic, (ix, y))
    return img


def check_safe(img, bg):
    """Every drawn pixel inside the reel safe zone (x65-1015, y300-1248), or a clear error."""
    from PIL import ImageChops
    diff = ImageChops.difference(img.convert("RGB"), Image.new("RGB", img.size, bg[:3])).convert("L").point(lambda v: 255 if v > 12 else 0)
    bb = diff.getbbox()
    if bb and (bb[0] < REEL_LEFT or bb[1] < REEL_TOP or bb[2] > REEL_RIGHT or bb[3] > REEL_BOTTOM):
        die(f"the X-reel card spans x{bb[0]}-{bb[2]}, y{bb[1]}-{bb[3]}: outside the reel safe zone "
            f"(x{REEL_LEFT}-{REEL_RIGHT}, y{REEL_TOP}-{REEL_BOTTOM}). Shorten the text or the name.")
    return bb


def render(spec, lk, out, log=print):
    for w in check(spec):
        log("warning: " + w)
    need("ffmpeg")
    X = lk["xreel"]
    dur = float(spec.get("duration") or X.get("duration_s", 6.0))
    if not 6.0 <= dur <= 7.0:
        log(f"warning: {dur:.1f} s: an X-reel holds 6-7 s")
    light = spec.get("mode", X.get("mode", "dark")) == "light"
    img = card(spec, lk)
    bb = check_safe(img, (255, 255, 255) if light else (0, 0, 0))
    tmp = Path(tempfile.mkdtemp(prefix="gre-xreel-"))
    png = tmp / "card.png"
    img.convert("RGB").save(png)
    n = round(dur * 30)                            # static: one card, every frame identical, no zoom
    run(["ffmpeg", "-loglevel", "error", "-y", "-loop", "1", "-framerate", "30", "-i", png, "-vf",
         "format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv",
         "-frames:v", str(n), "-tune", "stillimage", *X264, out])
    log(f"rendered {out} ({dur:.1f} s, static, card at x{bb[0]}-{bb[2]} y{bb[1]}-{bb[3]} inside the reel safe zone, silent)")
    return out
