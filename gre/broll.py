"""B-roll reel: 2-3 lines of on-screen text (the tease) over one real clip, revealed in turn; the caption is the payoff.

  spec = {"clip": "IMG_1234.MOV", "start": 0, "duration": 7,
          "blocks": [{"text": "...", "style": "white" | "black" | "outline", "at": s (optional), "y": 0-1 (optional)}]}

Blocks appear in order, `stagger_s` apart unless `at` says otherwise, and stay to the end. Rendered SILENT: the
trending sound is added in the Instagram app at posting."""
import tempfile
from pathlib import Path
from PIL import Image
from .common import (W, H, SAFE_TOP, SAFE_BOTTOM, X264, die, run, need, clear_rotation, video_info,
                     bg_input, bg_filter)
from .text import style_font, wrap, block_height, draw_lines


def layout(blocks, lk):
    sized = []
    for b in blocks:
        st = lk["styles"].get(b.get("style", "white"))
        if st is None:
            die(f"style {b.get('style')!r} is not in this look. Styles: {', '.join(lk['styles'])}")
        f = style_font(lk, st)
        lines = wrap(b["text"], f, lk["max_width"])
        sized.append((lines, f, st, block_height(lines, f, st, lk)))
    total = sum(x[3] for x in sized) + lk["block_gap"] * (len(sized) - 1)
    y = lk["center_y"] * H - total / 2
    tops = []
    for b, (_, _, _, bh) in zip(blocks, sized):
        top = b["y"] * H - bh / 2 if b.get("y") is not None else y
        if top < SAFE_TOP or top + bh > SAFE_BOTTOM:
            die(f"the text {b['text'][:40]!r} would sit at y{int(top)}-{int(top + bh)}, outside the feed-safe band "
                f"y{SAFE_TOP}-{SAFE_BOTTOM} (Facebook crops reels to 4:5). Shorten it or use fewer lines.")
        tops.append(top)
        y = top + bh + lk["block_gap"]
    return sized, tops


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
    sized, tops = layout(blocks, lk)
    times, t = [], 0.0
    for i, b in enumerate(blocks):
        t = float(b["at"]) if b.get("at") is not None else (0.0 if i == 0 else t + lk["stagger_s"])
        times.append(t)
    if times[-1] > dur - 1.5:
        log(f"warning: the last line appears at {times[-1]:.1f} s of {dur:.1f} s: viewers get under 1.5 s to read it")
    tmp = Path(tempfile.mkdtemp(prefix="gre-broll-"))
    pngs = []
    for i in range(len(blocks)):                      # one overlay per state: blocks 0..i visible
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for j in range(i + 1):
            lines, f, st, _ = sized[j]
            draw_lines(img, lines, f, st, lk, W / 2, tops[j])
        p = tmp / f"state{i}.png"
        img.save(p)
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
