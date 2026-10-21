"""Shared pieces: the frame, the feed-safe band, looks, fonts, the member profile, ffmpeg helpers."""
import json, os, shutil, subprocess, sys
from pathlib import Path
from PIL import ImageFont

SKILL = Path(__file__).resolve().parent.parent
LOOKS = SKILL / "looks"
FONTS = LOOKS / "fonts"
HOME = Path(os.environ.get("GRE_HOME") or Path.home() / ".go-reel-editor")
W, H, FPS = 1080, 1920, 30
# The feed-safe band: Facebook's feed shows reels as a 4:5 crop (y285-1635), Instagram's grid as 3:4 (y240-1680),
# and the reels UI covers the top ~200 px and the bottom from ~y1620. All text stays inside y300-1600.
SAFE_TOP, SAFE_BOTTOM = 300, 1600


class UserError(Exception):
    """A problem the member (or Claude) can fix: printed plainly, no traceback."""


def die(msg):
    raise UserError(msg)


# ---------- the member profile (name, handle, avatar, chosen look) ----------

def profile():
    p = HOME / "profile.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_profile(**kw):
    HOME.mkdir(parents=True, exist_ok=True)
    d = profile()
    d.update({k: v for k, v in kw.items() if v is not None})
    (HOME / "profile.json").write_text(json.dumps(d, indent=1))
    return d


# ---------- looks ----------

def look_names():
    names = sorted(p.stem for p in LOOKS.glob("*.json"))
    names += sorted(p.stem for p in (HOME / "looks").glob("*.json")) if (HOME / "looks").exists() else []
    return names


def look_path(name=None):
    name = name or profile().get("look") or "clean"
    p = Path(name).expanduser()
    if p.suffix == ".json" and p.exists():
        return p
    for d in (HOME / "looks", LOOKS):
        if (d / f"{name}.json").exists():
            return d / f"{name}.json"
    die(f"no look named {name!r}. Looks: {', '.join(look_names())}")


def load_look(name=None):
    p = look_path(name)
    lk = json.loads(p.read_text())
    lk["_path"] = str(p)
    lk["_name"] = p.stem
    return lk


def font_file(name):
    """A font: a file bundled in looks/fonts, a file in ~/.go-reel-editor/fonts, or an absolute path."""
    p = Path(str(name)).expanduser()
    if p.is_absolute() and p.exists():
        return p
    for d in (HOME / "fonts", FONTS):
        if (d / name).exists():
            return d / name
    die(f"font not found: {name} (put the file in {HOME / 'fonts'} or use a bundled one: "
        f"{', '.join(sorted(x.name for x in FONTS.glob('*.[ot]tf')))})")


def font(fname, size, weight=None, opsz=None):
    f = ImageFont.truetype(str(font_file(fname)), max(1, round(size)))
    try:                                   # variable fonts: weight by number, optical size if asked, else the max
        f.set_variation_by_axes([
            (weight or 400) if a["name"] in (b"Weight", "Weight")
            else (opsz or a["maximum"]) if a["name"] in (b"Optical size", "Optical size")
            else a["default"] for a in f.get_variation_axes()])
    except Exception:                      # a static font has no axes
        pass
    return f


# ---------- ffmpeg ----------

def need(tool):
    if not shutil.which(tool):
        die(f"{tool} is not installed. Say 'set me up' and Claude will install it.")
    return tool


def run(cmd, **kw):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, errors="replace", **kw)
    if r.returncode:
        die(f"{Path(str(cmd[0])).name} failed:\n{(r.stderr or r.stdout)[-1500:]}")
    return r


def probe(path):
    need("ffprobe")
    if not Path(path).exists():
        die(f"file not found: {path}")
    r = run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path])
    return json.loads(r.stdout)


def video_info(path):
    if is_image(path):
        if not Path(path).exists():
            die(f"file not found: {path}")
        from PIL import Image
        w, h = Image.open(path).size
        return {"w": w, "h": h, "fps": 0.0, "duration": 0.0, "transfer": "", "audio": False, "sample_rate": 0,
                "codec": "image"}
    d = probe(path)
    v = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    if not v:
        die(f"{Path(path).name} has no video stream")
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    rot = 0
    for sd in v.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(sd["rotation"])
    rot = int(v.get("tags", {}).get("rotate", rot))
    w, h = int(v["width"]), int(v["height"])
    if abs(rot) in (90, 270):
        w, h = h, w
    num, den = (v.get("avg_frame_rate") or "0/1").split("/")
    return {"w": w, "h": h, "fps": float(num) / float(den) if float(den) else 0.0,
            "duration": float(d["format"].get("duration") or v.get("duration") or 0),
            "transfer": v.get("color_transfer", ""), "audio": a is not None,
            "sample_rate": int(a["sample_rate"]) if a else 0, "codec": v.get("codec_name")}


_ZSCALE = None


def has_zscale():
    global _ZSCALE
    if _ZSCALE is None:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, errors="replace")
        _ZSCALE = " zscale " in r.stdout
    return _ZSCALE


TONEMAP = ("zscale=tin={tin}:min=bt2020nc:pin=bt2020:t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
           "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p,")


def source_filter(clip, info=None):
    """iPhone footage is often HDR (HLG/PQ): tone-map it to BT.709 first, or it comes out flat and washed."""
    info = info or video_info(clip)
    if info["transfer"] in ("arib-std-b67", "smpte2084"):
        if has_zscale():
            return TONEMAP.format(tin=info["transfer"])
        print(f"note: {Path(clip).name} is HDR and this ffmpeg has no zscale filter: colours may look washed out",
              file=sys.stderr)
    return ""


FILL = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
X264 = ["-c:v", "libx264", "-crf", "17", "-preset", "slow", "-pix_fmt", "yuv420p", "-color_primaries", "bt709",
        "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv", "-movflags", "+faststart"]


IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def is_image(path):
    return Path(str(path)).suffix.lower() in IMAGE_EXT


def bg_input(clip, start, dur, loop=False):
    """ffmpeg input args for the background: a video clip (trimmed, looped if short) or a still photo (held, with a
    slow push-in added by bg_filter so it never looks frozen)."""
    if is_image(clip):
        return ["-loop", "1", "-framerate", "30", "-t", str(dur), "-i", str(clip)]
    return (["-stream_loop", "-1"] if loop else []) + ["-ss", str(start), "-t", str(dur), "-i", str(clip)]


def bg_filter(clip, dur, info=None):
    """The filter that turns the background into a 1080x1920 30 fps picture."""
    if is_image(clip):
        n = round(dur * 30)
        return (f"scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
                f"zoompan=z='1+0.04*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={n}:s={W}x{H}:fps=30")
    return f"{source_filter(clip, info)}{FILL},fps=30"


def clear_rotation(out):
    """iPhone clips carry a rotation flag ffmpeg copies to the output though the pixels are already upright."""
    fixed = Path(str(out) + ".tmp.mp4")
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-display_rotation", "0", "-i", str(out), "-c", "copy",
                        "-movflags", "+faststart", str(fixed)], capture_output=True, text=True)
    if r.returncode == 0:
        fixed.replace(out)
    else:
        fixed.unlink(missing_ok=True)


def out_path(spec_path, out, suffix=".mp4"):
    if out:
        p = Path(out)
    else:
        sp = Path(spec_path)
        p = sp.parent / "out" / (sp.stem + suffix)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def read_spec(path):
    try:
        spec = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"spec not found: {path}")
    except json.JSONDecodeError as e:
        die(f"{path} is not valid JSON: {e}")
    base = Path(path).resolve().parent
    for k in ("clip", "image", "avatar"):          # paths in a spec are relative to the spec file
        if spec.get(k) and not Path(spec[k]).expanduser().is_absolute():
            spec[k] = str(base / spec[k])
    return spec
