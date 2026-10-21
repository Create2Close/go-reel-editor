"""gre: the GO! Reel Editor command. Claude runs it; members never have to.

  gre doctor                         check the tools, fonts and looks (what 'set me up' verifies)
  gre profile [--name N] [--handle @h] [--avatar file] [--look L] [--role "..."] [--market "..."]
                                     save who the member is (once; `gre profile` alone prints it)
  gre looks                          list the looks
  gre font "<Google Font name>"      download a free Google Font for the member's look
  gre colors <logo.png>              the main colours of a logo or screenshot (hex)
  gre look new <name> --from clean [--font F] [--caption-font F] [--accent #hex] [--accent2 #hex] [--caption-size N]
  gre look sheet [--look L] [--frame still.png]   one image of every format in a look, to approve it
  gre preview <spec.json> [--look L] [--at 6.5]   a still of the frame (fast; check before rendering)
  gre listicle|broll|xreel <spec.json> [--look L] [--out file.mp4]
  gre qa <video.mp4> [--yap]         check a finished file: size, length, sound, colour tags, rotation, loudness
  gre yap <step> ...                 the yap line: run `gre yap --help`
"""
import argparse, json, shutil, subprocess, sys, tempfile
from pathlib import Path
from . import __version__
from .common import (SKILL, HOME, FONTS, UserError, load_look, look_names, profile, save_profile, read_spec,
                     out_path, video_info, need, W, H)

FORMATS = ("listicle", "broll", "xreel")


def _mod(fmt):
    from . import broll, listicle, xreel
    return {"listicle": listicle, "broll": broll, "xreel": xreel}[fmt]


def cmd_render(fmt, a):
    spec = read_spec(a.spec)
    lk = load_look(a.look or spec.get("look"))
    out = out_path(a.spec, a.out)
    _mod(fmt).render(spec, lk, str(out))
    print(f"look: {lk['_name']}")
    return out


def cmd_preview(a):
    """One frame as a PNG: the card over a frame of the clip, at --at seconds (default: the end, all text shown)."""
    spec = read_spec(a.spec)
    fmt = a.format or spec.get("format") or ("xreel" if spec.get("image") and spec.get("text") else
                                             "listicle" if spec.get("title") else "broll")
    lk = load_look(a.look or spec.get("look"))
    m = _mod(fmt)
    out = out_path(a.spec, a.out, ".preview.png")
    from PIL import Image
    if fmt == "xreel":
        m.check(spec)
        m.card(spec, lk).convert("RGB").save(out)
    else:
        for w in m.check(spec):
            print("warning: " + w)
        if fmt == "listicle":
            overlay = m.card(spec, lk)
        else:
            sized, tops = m.layout(spec["blocks"], lk)
            from .text import draw_lines
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for (lines, f, st, _), top in zip(sized, tops):
                draw_lines(overlay, lines, f, st, lk, W / 2, top)
        from .common import source_filter, FILL, run, is_image
        tmp = Path(tempfile.mkdtemp(prefix="gre-prev-")) / "bg.png"
        t = float(spec.get("start", 0)) + (a.at if a.at is not None else 1.0)
        if is_image(spec["clip"]):
            run(["ffmpeg", "-loglevel", "error", "-y", "-i", spec["clip"], "-frames:v", "1", "-vf", FILL, tmp])
        else:
            run(["ffmpeg", "-loglevel", "error", "-y", "-ss", str(t), "-i", spec["clip"], "-frames:v", "1",
                 "-vf", f"{source_filter(spec['clip'])}{FILL}", tmp])
        bg = Image.open(tmp).convert("RGBA")
        bg.alpha_composite(overlay)
        bg.convert("RGB").save(out)
    print(f"preview {out} (look: {lk['_name']})")


def cmd_doctor(a):
    ok = True
    def line(good, what, fix=""):
        nonlocal ok
        ok &= bool(good)
        print(("  ok   " if good else "  MISSING  ") + what + ("" if good or not fix else f"  -> {fix}"))
    print(f"GO! Reel Editor {__version__} at {SKILL}")
    for tool in ("ffmpeg", "ffprobe"):
        line(shutil.which(tool), tool, "say 'set me up'")
    if shutil.which("ffmpeg"):
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace").stdout
        e = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, errors="replace").stdout
        line("libx264" in e, "ffmpeg can write H.264 (libx264)", "reinstall ffmpeg with setup.sh")
        print(("  ok   " if " zscale " in r else "  note ") + "HDR tone-mapping (zscale)"
              + ("" if " zscale " in r else ": iPhone HDR clips may look washed out; setup.sh installs a full ffmpeg"))
    for f in ("DMSans-VF.ttf", "Gelasio-VF.ttf", "InstrumentSerif-Regular.ttf", "Inter-Regular.otf", "Inter-Bold.otf",
              "NotoColorEmoji.ttf"):
        line((FONTS / f).exists(), f"font {f}")
    for n in look_names():
        try:
            load_look(n)
            line(True, f"look {n}")
        except Exception as e:
            line(False, f"look {n}: {e}")
    pr = profile()
    print(f"  profile: {json.dumps({k: v for k, v in pr.items()}) if pr else 'not set yet (needed for X-reels: name, handle, avatar)'}")
    from . import transcribe
    print("  yap transcription: " + transcribe.status())
    print("READY" if ok else "NOT READY: fix the MISSING lines (say 'set me up')")
    return 0 if ok else 1


def cmd_profile(a):
    av = None
    if a.avatar:
        src = Path(a.avatar).expanduser().resolve()
        if not src.exists():
            raise UserError(f"avatar not found: {src}")
        HOME.mkdir(parents=True, exist_ok=True)
        av = f"avatar{src.suffix.lower()}"
        shutil.copy2(src, HOME / av)
    if a.look:
        load_look(a.look)
    h = a.handle
    if h and not h.startswith("@"):
        h = "@" + h.strip()
    d = save_profile(name=a.name, handle=h, avatar=av, look=a.look, role=a.role, market=a.market,
                     audience=a.audience, colors=a.colors, fonts=a.fonts, notes=a.notes)
    print(json.dumps(d, indent=1))
    print(f"saved in {HOME / 'profile.json'}")


def cmd_brand(a):
    from . import brand
    if a.cmd == "font":
        print(brand.fetch_font(a.name))
    elif a.cmd == "colors":
        print("  ".join(brand.logo_colours(a.image)))
    elif a.action == "new":
        if not a.name:
            raise UserError("give the look a name: gre look new jane")
        slug, p = brand.make_look(a.name, a.base, a.font, a.caption_font, a.accent, a.accent2, a.caption_size)
        save_profile(look=slug)
        out = Path(a.out or HOME / f"look-{slug}.png")
        brand.sample_sheet(slug, out, a.frame)
        print(f"look '{slug}' saved ({p}) and set as the default\nsample sheet: {out}")
    else:
        name = a.look or a.name
        lk = load_look(name)
        out = Path(a.out or HOME / f"look-{lk['_name']}.png")
        brand.sample_sheet(lk["_name"], out, a.frame)
        print(f"sample sheet: {out}")


def cmd_qa(a):
    from .qa import qa
    return qa(a.video, yap=a.yap)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["yap"]:
        from .yap import main as yap_main
        return _guard(lambda: yap_main(argv[1:]))
    ap = argparse.ArgumentParser(prog="gre", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor")
    sub.add_parser("looks")
    p = sub.add_parser("profile")
    p.add_argument("--name"); p.add_argument("--handle"); p.add_argument("--avatar"); p.add_argument("--look")
    p.add_argument("--role"); p.add_argument("--market"); p.add_argument("--audience"); p.add_argument("--colors")
    p.add_argument("--fonts"); p.add_argument("--notes")
    p = sub.add_parser("font"); p.add_argument("name")
    p = sub.add_parser("colors"); p.add_argument("image")
    p = sub.add_parser("look"); p.add_argument("action", choices=["new", "sheet"]); p.add_argument("name", nargs="?")
    p.add_argument("--from", dest="base", default="clean"); p.add_argument("--font"); p.add_argument("--caption-font")
    p.add_argument("--accent"); p.add_argument("--accent2"); p.add_argument("--caption-size", type=int)
    p.add_argument("--look"); p.add_argument("--frame"); p.add_argument("--out")
    for f in FORMATS:
        p = sub.add_parser(f)
        p.add_argument("spec"); p.add_argument("--look"); p.add_argument("--out")
    p = sub.add_parser("preview")
    p.add_argument("spec"); p.add_argument("--look"); p.add_argument("--out"); p.add_argument("--at", type=float)
    p.add_argument("--format", choices=FORMATS)
    p = sub.add_parser("qa")
    p.add_argument("video"); p.add_argument("--yap", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "doctor":
        return _guard(lambda: cmd_doctor(a))
    if a.cmd == "looks":
        for n in look_names():
            print(f"{n:10s} {load_look(n).get('_about', '')}")
        return 0
    if a.cmd == "profile":
        return _guard(lambda: cmd_profile(a))
    if a.cmd in FORMATS:
        return _guard(lambda: cmd_render(a.cmd, a))
    if a.cmd == "preview":
        return _guard(lambda: cmd_preview(a))
    if a.cmd == "qa":
        return _guard(lambda: cmd_qa(a))
    if a.cmd in ("font", "colors", "look"):
        return _guard(lambda: cmd_brand(a))


def _guard(fn):
    try:
        r = fn()
        return r if isinstance(r, int) else 0
    except UserError as e:
        print(f"PROBLEM: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
