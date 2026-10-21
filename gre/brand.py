"""The member's own brand: fonts fetched free from Google Fonts, colours picked from a logo, a personal look built from
a starter look, and a one-page sample sheet to approve it."""
import colorsys, json, re, shutil, urllib.request
from pathlib import Path
from PIL import Image, ImageDraw
from .common import HOME, LOOKS, W, H, UserError, load_look, save_profile, font_file

GF_API = "https://api.github.com/repos/google/fonts/contents/{lic}/{slug}"


def fetch_font(name, log=print):
    """Download a Google Font (free, SIL OFL / Apache) into ~/.go-reel-editor/fonts. Prefers the variable file (any
    weight). Returns the file name. A paid font (Proxima Nova, SF Pro, Gotham...) can't be fetched: the member drops
    the .ttf/.otf files in ~/.go-reel-editor/fonts instead."""
    slug = re.sub(r"[^a-z0-9]", "", name.lower())
    files = None
    for lic in ("ofl", "apache", "ufl"):
        try:
            req = urllib.request.Request(GF_API.format(lic=lic, slug=slug), headers={"User-Agent": "go-reel-editor"})
            files = json.loads(urllib.request.urlopen(req, timeout=20).read())
            break
        except Exception:
            continue
    if not files:
        raise UserError(f"'{name}' is not a Google Font (or there's no internet). If it's a paid font, put its "
                        f".ttf/.otf files in {HOME / 'fonts'} and use the file name.")
    ttf = [f for f in files if f["name"].endswith(".ttf")]
    upright = [f for f in ttf if "Italic" not in f["name"]] or ttf
    var = [f for f in upright if "[" in f["name"]]
    pick = (var or sorted(upright, key=lambda f: ("Regular" not in f["name"], f["name"])))[0]
    dest = HOME / "fonts"
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / pick["name"]
    with urllib.request.urlopen(pick["download_url"], timeout=60) as r, open(out, "wb") as f:
        shutil.copyfileobj(r, f)
    lic = next((f for f in files if f["name"] in ("OFL.txt", "LICENSE.txt")), None)
    if lic:
        with urllib.request.urlopen(lic["download_url"], timeout=30) as r:
            (dest / f"{out.stem}-LICENSE.txt").write_bytes(r.read())
    log(f"font saved: {out.name}" + (" (variable: any weight)" if "[" in out.name else ""))
    return out.name


def logo_colours(path, n=5):
    """The main colours of a logo or screenshot, most used first, skipping near-white and near-black backgrounds."""
    im = Image.open(path).convert("RGBA")
    im.thumbnail((300, 300))
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    q = bg.convert("RGB").quantize(colors=12, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    out = []
    for c, idx in counts:
        r, g, b = pal[idx * 3: idx * 3 + 3]
        hls = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if hls[1] > 0.93 or hls[1] < 0.06:
            continue
        hx = f"#{r:02X}{g:02X}{b:02X}"
        if all(sum(abs(int(hx[i:i + 2], 16) - int(o[i:i + 2], 16)) for i in (1, 3, 5)) > 60 for o in out):
            out.append(hx)
        if len(out) >= n:
            break
    return out


def rgba(hx, a=255):
    hx = hx.strip().lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", hx):
        raise UserError(f"'{hx}' is not a colour: use a hex code like #ED3F2D")
    return [int(hx[i:i + 2], 16) for i in (0, 2, 4)] + [a]


def ink_for(c):
    """White or black text on a box of colour c, whichever reads better."""
    r, g, b = [x / 255 for x in c[:3]]
    lum = 0.2126 * r ** 2.2 + 0.7152 * g ** 2.2 + 0.0722 * b ** 2.2
    return [0, 0, 0, 255] if lum > 0.35 else [255, 255, 255, 255]


def make_look(name, base="clean", font=None, caption_font=None, accent=None, accent2=None, caption_size=None):
    """A personal look: a copy of a starter look with the member's fonts and colours. accent = their main brand colour
    (punchline and title boxes, an "accent" style for b-roll); accent2 = an optional second colour ("accent2")."""
    lk = load_look(base)
    for k in ("_path", "_name"):
        lk.pop(k, None)
    lk["_about"] = f"{name}'s look, built from '{base}'" + (f", font {font}" if font else "") + \
                   (f", accent {accent}" if accent else "")
    if font:
        font_file(font)
        lk["font"] = font
        for st in lk["styles"].values():
            if st.get("font") and not st.get("outline"):
                st["font"] = font
        lk["xreel"]["font"] = lk["xreel"].get("font")                # X-reels keep X's own look (Inter)
    if caption_font or font:
        cf = caption_font or font
        font_file(cf)
        lk["captions"]["font"] = cf
        for st in lk["styles"].values():
            if st.get("outline") and st.get("font"):
                st["font"] = cf
    if caption_size:
        lk["captions"]["size"] = int(caption_size)
    if accent:
        c = rgba(accent)
        lk["styles"]["accent"] = {"box": c, "ink": ink_for(c)}
        lk["listicle"]["punchline"]["style"] = "accent"
        lk["title"]["style"] = "accent"
    if accent2:
        c2 = rgba(accent2)
        lk["styles"]["accent2"] = {"box": c2, "ink": ink_for(c2)}
    d = HOME / "looks"
    d.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-") or "mine"
    p = d / f"{slug}.json"
    p.write_text(json.dumps(lk, indent=1))
    return slug, p


def _bg():
    """A neutral photo-like background for sample stills: a soft vertical gradient."""
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(70 + 60 * t), int(80 + 50 * t), int(95 + 30 * t)))
    return img.convert("RGBA")


def sample_sheet(look_name, out, clip_frame=None):
    """One image: a listicle, a b-roll, an X-reel (if the profile has a photo) and a yap caption + title, in this look."""
    from . import listicle, broll, xreel, captions, title as T
    from .text import draw_lines
    lk = load_look(look_name)
    base = Image.open(clip_frame).convert("RGBA").resize((W, H)) if clip_frame else _bg()
    tiles = []
    lst = base.copy()
    lst.alpha_composite(listicle.card({"title": "What $400K buys you", "items": [
        "Austin: 3 bed, 2 bath", "Columbus: 4 bed, 2.5 bath", "Tampa: 3 bed, 2 bath", "Raleigh: 3 bed, 2.5 bath",
        "Phoenix: 3 bed, 2 bath"], "punchline": "Same money. Very different house."}, lk))
    tiles.append(lst)
    br = base.copy()
    blocks = [{"text": "I almost told this buyer to wait…", "style": "white"},
              {"text": "then we ran the real numbers", "style": "accent" if "accent" in lk["styles"] else "black"},
              {"text": "Here's what changed my mind:", "style": "black"}]
    sized, tops = broll.layout(blocks, lk)
    for (lines, f, st, _), top in zip(sized, tops):
        draw_lines(br, lines, f, st, lk, W / 2, top)
    tiles.append(br)
    try:
        tiles.append(xreel.card({"text": "JUST IN: Your market headline goes here.\n\nHere's what it means 👇",
                                 "image": _news_placeholder()}, lk))
    except UserError:
        pass
    yp = base.copy()
    t_img, _, _ = T.card(["Your title goes here"], lk, lk["title"].get("size", 84))
    yp.alpha_composite(t_img, (0, max(330, lk["title"].get("top", 330))))
    arr, x, y = captions.draw("how your **captions** look", lk["captions"])
    yp.alpha_composite(Image.fromarray(arr), (x, y))
    tiles.append(yp)
    sheet = Image.new("RGB", (W // 3 * len(tiles), H // 3), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t.convert("RGB").resize((W // 3, H // 3)), (i * W // 3, 0))
    sheet.save(out)
    return out


def _news_placeholder():
    p = HOME / "_news_placeholder.png"
    if not p.exists():
        HOME.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (1280, 720), (40, 60, 90))
        ImageDraw.Draw(img).rectangle([0, 520, 1280, 720], fill=(25, 35, 55))
        img.save(p)
    return str(p)
