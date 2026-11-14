"""B-roll reel: 2-3 lines of on-screen text (the tease) over one real clip, revealed in turn; the caption is the payoff.

  spec = {"clip": "IMG_1234.MOV", "start": 0, "duration": 7,
          "blocks": [{"text": "...", "style": "white" | "black" | "outline", "at": s (optional), "y": 0-1 (optional)}],
          "center_y": 0-1 (optional), "avoid_faces": false (optional)}

Blocks appear in order, `stagger_s` apart unless `at` says otherwise, and stay to the end. The lines sit mid-frame as
one block; when that would put them across a face in the footage, the whole block moves up or down to the nearest
spot that clears every face (place). "center_y" in the spec, a block's own "y", or "avoid_faces": false switch that
off. Rendered SILENT: the trending sound is added in the Instagram app at posting."""
import subprocess, tempfile
from pathlib import Path
import numpy as np
from PIL import Image
from .common import (W, H, SAFE_TOP, SAFE_BOTTOM, FILL, X264, die, run, need, clear_rotation, video_info,
                     bg_input, bg_filter, is_image)
from .text import style_font, wrap, block_height, draw_lines, line_height, textlength

FACE_SAMPLES = 5            # looks at a moving clip this many times, spread across the part the reel uses
PHOTO_PUSH_IN = 1.04        # a photo gets a slow push-in (common.bg_filter): a face ends this much further out


def layout(blocks, lk, center_y=None):
    sized = []
    for b in blocks:
        st = lk["styles"].get(b.get("style", "white"))
        if st is None:
            die(f"style {b.get('style')!r} is not in this look. Styles: {', '.join(lk['styles'])}")
        f = style_font(lk, st)
        lines = wrap(b["text"], f, lk["max_width"])
        sized.append((lines, f, st, block_height(lines, f, st, lk)))
    total = sum(x[3] for x in sized) + lk["block_gap"] * (len(sized) - 1)
    y = (lk["center_y"] if center_y is None else float(center_y)) * H - total / 2
    tops = []
    for b, (_, _, _, bh) in zip(blocks, sized):
        top = b["y"] * H - bh / 2 if b.get("y") is not None else y
        if top < SAFE_TOP or top + bh > SAFE_BOTTOM:
            die(f"the text {b['text'][:40]!r} would sit at y{int(top)}-{int(top + bh)}, outside the feed-safe band "
                f"y{SAFE_TOP}-{SAFE_BOTTOM} (Facebook crops reels to 4:5). Shorten it or use fewer lines.")
        tops.append(top)
        y = top + bh + lk["block_gap"]
    return sized, tops


# ---------- keeping the text off faces ----------

def _frame(clip, t=None):
    """One frame of the footage the way the reel shows it (filled to 1080x1920), as RGB. None if it cannot be read."""
    cmd = ["ffmpeg", "-v", "error", *([] if t is None else ["-ss", f"{t:.3f}"]), "-i", str(clip), "-frames:v", "1",
           "-vf", f"{FILL},format=rgb24", "-f", "rawvideo", "-"]
    try:
        raw = subprocess.run(cmd, capture_output=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return np.frombuffer(raw[:W * H * 3], np.uint8).reshape(H, W, 3).copy() if len(raw) >= W * H * 3 else None


def find_faces(clip, start=0.0, dur=7.0, info=None):
    """Every face in the footage as (x, y, w, h) on the 1080x1920 frame: one look at a photo, FACE_SAMPLES looks
    across the part of a moving clip the reel uses. A photo's faces count twice, where the slow push-in starts and
    where it ends. Never raises: footage that cannot be read has no faces."""
    try:
        from .title import all_faces
        if is_image(clip):
            faces = all_faces([f for f in [_frame(clip)] if f is not None])
            z = PHOTO_PUSH_IN
            return faces + [(W / 2 + (x - W / 2) * z, H / 2 + (y - H / 2) * z, w * z, h * z) for x, y, w, h in faces]
        length = (info or video_info(clip))["duration"]
        a, b = (start, start + dur) if length - start >= dur else (0.0, length or dur)   # a short clip loops: all of it
        frames = [_frame(clip, a + (b - a) * (i + 0.5) / FACE_SAMPLES) for i in range(FACE_SAMPLES)]
        return all_faces([f for f in frames if f is not None])
    except Exception:
        return []


def face_zones(faces):
    """What the text stays off, per face, as (x0, y0, x1, y1): the detector's box runs from the brow to the lips, so
    it is grown up over the forehead and down past the chin (title.head_span's proportion), with a little air."""
    return [(x - 0.03 * w, y - 0.06 * h, x + 1.03 * w, y + 1.21 * h) for x, y, w, h in faces]


def _boxes(sized, tops, lk):
    """Every line's box as drawn (x0, y0, x1, y1)."""
    out = []
    for (lines, f, st, _), top in zip(sized, tops):
        lh, y = line_height(f, st, lk), top
        for ln in lines:
            half = textlength(ln, f) / 2 + lk["pad_x"]
            out.append((W / 2 - half, y, W / 2 + half, y + lh))
            y += lh + lk["line_gap"]
    return out


def _covers(boxes, dy, zones):
    return any(x0 < zx1 and zx0 < x1 and y0 + dy < zy1 and zy0 < y1 + dy
               for x0, y0, x1, y1 in boxes for zx0, zy0, zx1, zy1 in zones)


def _nearest_clear(boxes, zones):
    """The smallest move up or down (pixels; up wins a tie) that takes every line off every face and keeps the block
    in the feed-safe band. None if there is no such place."""
    top, bottom = min(b[1] for b in boxes), max(b[3] for b in boxes)
    for d in range(0, SAFE_BOTTOM - SAFE_TOP):
        for dy in ((0,) if d == 0 else (-d, d)):
            if top + dy >= SAFE_TOP and bottom + dy <= SAFE_BOTTOM and not _covers(boxes, dy, zones):
                return dy
    return None


def _largest_clear_band(boxes, zones):
    """The move that puts the block in the tallest face-free strip of the feed-safe band (it will still reach into
    a face: the strip is shorter than the block). None when there is no free strip at all."""
    top, bottom = min(b[1] for b in boxes), max(b[3] for b in boxes)
    x0, x1 = min(b[0] for b in boxes), max(b[2] for b in boxes)
    taken = sorted((max(SAFE_TOP, zy0), min(SAFE_BOTTOM, zy1)) for zx0, zy0, zx1, zy1 in zones if zx0 < x1 and x0 < zx1)
    bands, y = [], SAFE_TOP
    for a, b in taken:
        if a > y:
            bands.append((y, a))
        y = max(y, b)
    if y < SAFE_BOTTOM:
        bands.append((y, SAFE_BOTTOM))
    if not bands:
        return None
    mid = (top + bottom) / 2
    a, b = max(bands, key=lambda s: (s[1] - s[0], -abs((s[0] + s[1]) / 2 - mid)))
    new_top = min(max((a + b) / 2 - (bottom - top) / 2, SAFE_TOP), SAFE_BOTTOM - (bottom - top))
    return new_top - top


def _scaled(lk, size):
    """The look with its b-roll type at `size`: the padding and the gaps shrink with it."""
    k = size / lk["size"]
    return {**lk, "size": size, **{n: lk[n] * k for n in ("pad_x", "pad_y", "line_gap", "block_gap")}}


def min_size(lk):
    """The smallest b-roll type: the look's own `min_size`, else four fifths of its `size`."""
    return int(lk.get("min_size") or round(lk["size"] * 0.8))


def _where(boxes, dy, zones):
    """'below the face', 'above the faces'...: where the block ended up, in the words Claude passes on."""
    top, bottom = min(b[1] for b in boxes) + dy, max(b[3] for b in boxes) + dy
    seen = []                                      # one face found twice (two detectors, two frames) is one face
    for z in zones:
        cx, cy = (z[0] + z[2]) / 2, (z[1] + z[3]) / 2
        if not any(s[0] <= cx <= s[2] and s[1] <= cy <= s[3] for s in seen):
            seen.append(z)
    one = "face" if len(seen) == 1 else "faces"
    if all(z[3] <= top for z in zones):
        return f"below the {one}"
    if all(z[1] >= bottom for z in zones):
        return f"above the {one}"
    return f"clear of the {one}"


def place(spec, lk, log=print, info=None, dur=None):
    """Where the lines go: the look's usual spot, or the nearest spot clear of every face in the footage. Returns
    (sized, tops, look): the look comes back with smaller type (never under min_size) when only smaller type fits
    beside the face. When nothing clears it, the smallest type goes in the tallest face-free strip. Says what it
    did in one `note:` line. No face, or the text is already clear of it: exactly the usual layout."""
    blocks = spec["blocks"]
    sized, tops = layout(blocks, lk, spec.get("center_y"))
    if (spec.get("avoid_faces") is False or spec.get("center_y") is not None
            or any(b.get("y") is not None for b in blocks)):
        return sized, tops, lk                     # the member's own placement wins
    dur = float(dur or spec.get("duration") or lk.get("duration_s", 7.0))
    zones = face_zones(find_faces(spec["clip"], float(spec.get("start", 0)), dur, info))
    boxes = _boxes(sized, tops, lk)
    if not zones or not _covers(boxes, 0, zones):
        return sized, tops, lk
    small = min(min_size(lk), lk["size"])
    for size in [lk["size"], *range(int(lk["size"]) - 2, small, -2), small]:
        lk2 = lk if size == lk["size"] else _scaled(lk, size)
        s2, t2 = (sized, tops) if lk2 is lk else layout(blocks, lk2)
        b2 = _boxes(s2, t2, lk2)
        dy = _nearest_clear(b2, zones)
        if dy is not None:
            log(f"note: moved the text {_where(b2, dy, zones)}"
                + ("" if lk2 is lk else " and made it a little smaller so it fits there"))
            return s2, [t + dy for t in t2], lk2
    dy = _largest_clear_band(b2, zones)            # nothing clears it: the smallest type, where it covers the least
    log("note: could not keep the text fully clear of the face: there is not enough room above or below it"
        + ("" if dy is None else ", so it sits where it covers the least") + ". Fewer or shorter lines, or footage "
        "with more room around the face, would fix it.")
    if dy is None:                                 # a face fills the whole band: leave the text as it was
        return sized, tops, lk
    return s2, [t + dy for t in t2], lk2


def overlay(sized, tops, lk, upto=None):
    """The lines drawn on a clear 1080x1920 frame (blocks 0..upto; all of them by default)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for (lines, f, st, _), top in list(zip(sized, tops))[:None if upto is None else upto + 1]:
        draw_lines(img, lines, f, st, lk, W / 2, top)
    return img


def check(spec):
    warn = []
    blocks = spec.get("blocks") or die("a b-roll spec needs 'blocks': the on-screen lines")
    if not spec.get("clip"):
        die("a b-roll spec needs 'clip': the footage file")
    if len(blocks) > 4:
        die(f"{len(blocks)} text blocks: a b-roll reel carries 2-3 (4 at most). The rest belongs in the caption.")
    if len(blocks) == 4:
        warn.append("4 blocks: the format allows it only rarely; 2-3 reads faster")
    for b in blocks:
        n = len(b["text"].split())
        if n > 12:
            warn.append(f"{n} words in one block ({b['text'][:30]}…): each line should read in under 2 s (4-8 words)")
    return warn


def render(spec, lk, out, log=print):
    for w in check(spec):
        log("warning: " + w)
    need("ffmpeg")
    blocks = spec["blocks"]
    clip = spec["clip"]
    info = video_info(clip)
    dur = float(spec.get("duration") or lk.get("duration_s", 7.0))
    sized, tops, lk = place(spec, lk, log, info, dur)
    times, t = [], 0.0
    for i, b in enumerate(blocks):
        t = float(b["at"]) if b.get("at") is not None else (0.0 if i == 0 else t + lk["stagger_s"])
        times.append(t)
    if times[-1] > dur - 1.5:
        log(f"warning: the last line appears at {times[-1]:.1f} s of {dur:.1f} s: viewers get under 1.5 s to read it")
    tmp = Path(tempfile.mkdtemp(prefix="gre-broll-"))
    pngs = []
    for i in range(len(blocks)):                      # one overlay per state: blocks 0..i visible
        p = tmp / f"state{i}.png"
        overlay(sized, tops, lk, i).save(p)
        pngs.append(p)
    start = float(spec.get("start", 0))
    loop = bool(info["duration"]) and info["duration"] - start < dur
    inputs = bg_input(clip, start, dur, loop)
    for p in pngs:
        inputs += ["-loop", "1", "-t", str(dur), "-i", p]
    fc = [f"[0:v]{bg_filter(clip, dur, info)},format=yuv420p[v0]"]
    cur = "v0"
    for i in range(len(pngs)):
        end = times[i + 1] if i + 1 < len(times) else dur + 1
        fc.append(f"[{cur}][{i + 1}:v]overlay=0:0:enable='between(t,{times[i]:.3f},{end - 0.001:.3f})'[v{i + 1}]")
        cur = f"v{i + 1}"
    run(["ffmpeg", "-loglevel", "error", "-y", *inputs, "-filter_complex", ";".join(fc), "-map", f"[{cur}]",
         "-an", "-t", str(dur), *X264, out])
    clear_rotation(out)
    if loop:
        log(f"note: the clip is shorter than {dur:.0f} s, so it loops")
    log(f"rendered {out} ({dur:.1f} s, lines at {', '.join(f'{x:.1f}' for x in times)} s, silent)")
    return out
