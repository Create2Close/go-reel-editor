"""qa: the checks every finished file must pass before Claude hands it over."""
import json, re, subprocess
from pathlib import Path
from .common import probe, W, H


def loudness(path):
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-vn", "-af", "ebur128=peak=sample", "-f", "null", "-"],
                         capture_output=True, text=True, errors="replace").stderr
    s = err[err.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", s)
    p = re.search(r"Peak:\s+(-?[\d.inf]+) dBFS", s, re.S)
    return (float(i.group(1)) if i else None), (float(p.group(1)) if p and "inf" not in p.group(1) else None)


def qa(video, yap=False):
    d = probe(video)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    a = [s for s in d["streams"] if s["codec_type"] == "audio"]
    dur = float(d["format"]["duration"])
    rot = any("rotation" in sd and int(sd["rotation"]) for sd in v.get("side_data_list", []))
    fails, notes = [], []
    if (int(v["width"]), int(v["height"])) != (W, H):
        fails.append(f"size {v['width']}x{v['height']}, expected {W}x{H}")
    if rot:
        fails.append("a rotation flag is set: players may turn it sideways")
    if v.get("codec_name") != "h264" or v.get("pix_fmt") != "yuv420p":
        fails.append(f"codec {v.get('codec_name')}/{v.get('pix_fmt')}: Instagram wants H.264 yuv420p")
    if v.get("color_primaries") != "bt709":
        notes.append("no BT.709 colour tag")
    if yap:
        if not a:
            fails.append("no sound")
        else:
            i, p = loudness(video)
            notes.append(f"loudness {i} LUFS, peak {p} dBFS")
            if i is None or not (-20 <= i <= -14):
                fails.append(f"loudness {i} LUFS: the yap chain lands about -17")
            if p is not None and p > -5.0:
                fails.append(f"peak {p} dBFS: above the -6 dBFS limiter ceiling")
        if dur > 180:
            notes.append(f"{dur:.0f} s long: Instagram reels top out at 3 minutes")
    else:
        if a:
            notes.append("has a sound track: EZ reels ship silent (add the sound in the Instagram app)")
        if not 4 <= dur <= 15:
            notes.append(f"{dur:.1f} s: EZ reels run 6-8 s (listicles up to 12 s)")
    print(f"{Path(video).name}: {v['width']}x{v['height']} {dur:.2f} s {v.get('codec_name')} "
          f"{'sound' if a else 'silent'}")
    for n in notes:
        print("  note  " + n)
    for f in fails:
        print("  FAIL  " + f)
    print("PASS" if not fails else "FAIL")
    return 0 if not fails else 1
