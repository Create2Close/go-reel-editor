"""The yap renderer: the cut (any number of clips) + automatic camera moves + captions + title + the audio chain,
in ONE pass, no editing app. Frame-exact: every segment is a whole number of frames at 30 fps and its sound is
trimmed to exactly that length, so picture and sound never drift.

Audio = a STATIC chain, never dynamic loudness: 15 ms equal-power crossfades at every joint (no clicks, never a fade
to silence), an 80 Hz high-pass (phone rooms rumble), then ONE measured gain (the kept speech to -17 LUFS) into a
-6 dBFS limiter."""
import json, re, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import cv2
from .common import W, H, FPS, FILL, UserError, need, run, source_filter, video_info

LIMITER = "alimiter=level_in=1:level_out=1:limit=0.501:attack=5:release=50:level=disabled:latency=1"
XF = 0.015
A_LEVEL, B_LEVEL = (100.0, 103.0), (113.0, 116.0)


def frame_plan(segs):
    """Whole frames per segment from cumulative time, so rounding never accumulates."""
    out, cum = [], 0.0
    for s in segs:
        d = s["end"] - s["start"]
        f0, f1 = round(cum * FPS), round((cum + d) * FPS)
        out.append(max(1, f1 - f0))
        cum += d
    return out


def auto_moves(segs, nframes):
    """Every cut changes the framing by >= 10 %: alternate a wide slow drift (100->103 %) and a tight one
    (113->116 %). Under 0.8 s there is no drift (the cut-in alone carries it)."""
    moves, level = [], A_LEVEL
    for k, (s, n) in enumerate(zip(segs, nframes)):
        if k:
            level = B_LEVEL if level == A_LEVEL else A_LEVEL
        a, b = level
        moves.append({"from": a, "to": a if n < 0.8 * FPS else b})
    return {"auto": True, "rule": "alternate wide 100-103 % / tight 113-116 % at every cut", "clips": moves}


def scale_frame(img, s):
    if abs(s - 1) < 1e-6:
        return img
    cx, cy = (W - 1) / 2, (H - 1) / 2
    M = np.float32([[s, 0, (1 - s) * cx], [0, s, (1 - s) * cy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def blend(img, rgba, x, y, alpha=1.0):
    h, w = rgba.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x0 >= x1 or y0 >= y1:
        return
    src = rgba[y0 - y:y1 - y, x0 - x:x1 - x]
    a = src[..., 3:4].astype(np.float32) / 255.0 * alpha
    reg = img[y0:y1, x0:x1].astype(np.float32)
    img[y0:y1, x0:x1] = (reg * (1 - a) + src[..., :3].astype(np.float32) * a).astype(np.uint8)


def loudness(path):
    err = subprocess.run(["ffmpeg", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True, errors="replace").stderr
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", err[err.rfind("Summary:"):])
    return float(m.group(1)) if m else None


def build_audio(segs, clips, nframes, tmp, highpass=80):
    used = sorted({s["ci"] for s in segs})
    pos = {ci: k for k, ci in enumerate(used)}
    ins = []
    for ci in used:
        if not video_info(clips[ci])["audio"]:
            raise UserError(f"{Path(clips[ci]).name} has no sound track")
        ins += ["-i", clips[ci]]
    fc, labels = [], []
    last = len(segs) - 1
    for k, (s, n) in enumerate(zip(segs, nframes)):
        d = n / FPS + (XF if k < last else 0)
        fc.append(f"[{pos[s['ci']]}:a:0]atrim=start={s['start']:.4f}:end={s['start'] + d:.4f},asetpts=PTS-STARTPTS,"
                  f"aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,"
                  f"apad=whole_dur={d:.4f}[a{k}]")
        labels.append(f"a{k}")
    cur = labels[0]
    for k in range(1, len(labels)):
        fc.append(f"[{cur}][{labels[k]}]acrossfade=d={XF}:c1=qsin:c2=qsin[x{k}]")
        cur = f"x{k}"
    hp = f"highpass=f={highpass}:poles=2,highpass=f={highpass}:poles=2" if highpass else "anull"
    fc.append(f"[{cur}]{hp}[aout]")
    wav = Path(tmp) / "cut.wav"
    script = Path(tmp) / "audio.filter"
    script.write_text(";".join(fc))
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex_script", script, "-map", "[aout]",
         "-c:a", "pcm_f32le", wav])
    return wav


def render(cuts, out, moves=None, captions=None, title=None, label=None, gain="auto", highpass=80, log=print,
           preview=False):
    """preview=True: a quick, light review copy (540x960, fast encode) that plays in the chat; the final is full
    quality."""
    need("ffmpeg")
    segs = cuts["segments"]
    clips = cuts["clips"]
    if not segs:
        raise UserError("the cut is empty")
    nframes = frame_plan(segs)
    total = sum(nframes)
    moves = moves or auto_moves(segs, nframes)
    tmp = Path(tempfile.mkdtemp(prefix="gre-yap-"))
    log(f"audio: {len(segs)} joints, crossfaded")
    wav = build_audio(segs, clips, nframes, tmp, highpass)
    if gain == "auto":
        lufs = loudness(wav)
        g = max(-12.0, min(30.0, round(-17 - lufs, 1))) if lufs is not None else 0.0
    else:
        g = float(gain)
    caps = captions or []
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
         "-i", "pipe:0", "-i", str(wav), "-filter_complex",
         f"[0:v]{'scale=540:960:flags=area,' if preview else ''}scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p,"
         f"setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv[v];[1:a]volume={g}dB,{LIMITER}[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast" if preview else "medium",
         "-crf", "26" if preview else "17", "-profile:v", "high",
         "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
         "-color_range", "tv", "-c:a", "aac", "-b:a", "160k" if preview else "256k", "-ar", "48000", "-frames:v", str(total),
         "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE)
    infos = {}
    seq, nbytes = 0, W * H * 3
    for k, (s, n) in enumerate(zip(segs, nframes)):
        clip = clips[s["ci"]]
        info = infos.get(clip) or infos.setdefault(clip, video_info(clip))
        vf = f"{source_filter(clip, info)}{FILL},fps={FPS},scale=in_range=tv:out_range=pc:in_color_matrix=bt709,format=rgb24"
        dec = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{s['start']:.4f}", "-i", clip, "-t",
                                f"{n / FPS + 0.5:.4f}", "-map", "0:v:0", "-vf", vf, "-f", "rawvideo", "-"],
                               stdout=subprocess.PIPE)
        mv = moves["clips"][k] if k < len(moves["clips"]) else {"from": 100, "to": 100}
        prev = None
        for i in range(n):
            buf = dec.stdout.read(nbytes)
            if len(buf) < nbytes:
                if prev is None:
                    raise UserError(f"could not read {Path(clip).name} at {s['start']:.2f} s")
                buf = prev
            prev = buf
            img = np.frombuffer(buf, np.uint8).reshape(H, W, 3).copy()
            sc = mv["from"] + (mv["to"] - mv["from"]) * (i / max(1, n - 1))
            img = scale_frame(img, sc / 100.0)
            t = seq / FPS
            for c in caps:
                if c["start"] <= t < c["end"]:
                    blend(img, c["img"], c["x"], c["y"])
                    break
            if title:
                al = title["alpha"](t)
                if al > 0:
                    blend(img, title["img"], title["x"], title["y"] - title["rise"](t), al)
            if label:
                txt = f"{label}  {int(t // 60)}:{t % 60:04.1f}  f{seq}"
                (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 1.3, 3)
                cv2.rectangle(img, (20, 20), (44 + tw, 44 + th + 8), (0, 0, 0), -1)
                cv2.putText(img, txt, (32, 36 + th), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (255, 255, 255), 3, cv2.LINE_AA)
            try:
                enc.stdin.write(img.tobytes())
            except BrokenPipeError:
                raise UserError("the video encoder stopped (see the ffmpeg message above)")
            seq += 1
        dec.kill()
        dec.wait()
        if (k + 1) % 10 == 0 or k == len(segs) - 1:
            log(f"  {k + 1}/{len(segs)} segments, {seq / FPS:.1f} s")
    enc.stdin.close()
    enc.wait()
    if enc.returncode:
        raise UserError("the video encoder failed")
    log(f"rendered {out}: {total / FPS:.2f} s, {len(segs)} cuts, gain {g:+.1f} dB into the -6 dBFS limiter"
        + (f", {len(caps)} captions" if caps else "") + (", title" if title else "") + (f", DRAFT {label}" if label else ""))
    return out, moves
