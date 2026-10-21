"""The on-screen title (the visual hook): 3-8 words that ADD to the spoken hook, on screen at full opacity from frame 1
(the first frame is the platform's thumbnail), held 3.5 s, then a short fade. It sits in the feed-safe band above the
head: the head is found on the real frames (face detection) and the title is sized to fit above it."""
import subprocess
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
from .common import W, H, FPS, SAFE_TOP, SAFE_BOTTOM, FILL, UserError, source_filter
from .text import style_font, wrap, block_height, draw_lines

_CASCADE = None


def head_box(frames):
    """(highest head point, lowest chin point) over the frames: face top minus a third of the face for hair, face
    bottom plus a sixth for the chin. (None, None) if no face is found."""
    global _CASCADE
    _CASCADE = _CASCADE or cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    tops, faces_top, chins = [], [], []
    for img in frames:
        g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        small = cv2.resize(g, (W // 2, H // 2))
        faces = _CASCADE.detectMultiScale(small, 1.1, 5, minSize=(80, 80))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            tops.append(int(2 * (y - 0.35 * h)))
            faces_top.append(int(2 * (y + 0.05 * h)))     # the brow line: the face proper starts here
            chins.append(int(2 * (y + h * 1.17)))
    return (min(tops), min(faces_top), max(chins)) if tops else (None, None, None)


def head_top(frames):
    return head_box(frames)[0]


def grab(cuts, moves, t_out):
    """The program frame at output time t (the cut and the move applied), as RGB."""
    from .render import frame_plan, scale_frame
    segs, clips = cuts["segments"], cuts["clips"]
    nf = frame_plan(segs)
    f = int(t_out * FPS)
    for k, (s, n) in enumerate(zip(segs, nf)):
        if f < n:
            src = s["start"] + f / FPS
            clip = clips[s["ci"]]
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{src:.3f}", "-i", clip, "-frames:v", "1",
                                  "-vf", f"{source_filter(clip)}{FILL},format=rgb24", "-f", "rawvideo", "-"],
                                 capture_output=True).stdout
            if len(raw) < W * H * 3:
                return None
            img = np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy()
            mv = moves["clips"][k]
            sc = mv["from"] + (mv["to"] - mv["from"]) * (f / max(1, n - 1))
            return scale_frame(img, sc / 100)
        f -= n
    return None


def card(lines, lk, size):
    T = lk["title"]
    st = lk["styles"][T.get("style", "black")]
    f = style_font(lk, st, size, T.get("weight", 800))
    wrapped = []
    for ln in lines:
        wrapped += wrap(ln, f, T.get("max_width", 960))
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bottom = draw_lines(img, wrapped, f, st, lk, W / 2, 0)
    bb = img.getbbox()
    return img.crop((0, 0, W, int(bottom) + 4)), wrapped, bb


def fit(lines, lk, head, chin=None, caption_top=None, face=None):
    """Where the title goes, in order: above the head at a readable size; over the hair or hat but above the brow
    (never on the face); between the chin and the captions; smaller above the head. Returns (size, top, image, where)."""
    T = lk["title"]
    top = max(SAFE_TOP, T.get("top", 330))
    floor = (head - 40) if head else 0.42 * H
    readable = T.get("min_size", 52) + 12
    sizes = list(range(T.get("max_size", 100), T.get("min_size", 52) - 1, -2))

    def fits(size, y0, y1):
        img, wrapped, bb = card(lines, lk, size)
        ok = bb and bb[0] >= 40 and bb[2] <= W - 40 and y0 + img.height <= y1 and len(wrapped) <= 3
        return img if ok else None

    for size in sizes:
        img = fits(size, top, floor)
        if img is not None and size >= readable:
            return size, top, img, "above the head"
    if face:                                       # over the hair/hat, never the face
        for size in sizes:
            img = fits(size, top, face - 20)
            if img is not None and size >= readable:
                return size, top, img, "over the top of the head, clear of the face"
    if chin and caption_top:                       # no room above the head: under the chin, above the captions
        lo, hi = chin + 30, caption_top - 30
        for size in sizes:
            img = fits(size, lo, hi)
            if img is not None:
                return size, int(lo + (hi - lo - img.height) / 2), img, "between the chin and the captions"
    if caption_top:                                # under the captions, inside the feed-safe band
        lo, hi = caption_top + int(lk["captions"]["size"] * 1.5) + 20, SAFE_BOTTOM
        for size in sizes:
            img = fits(size, lo, hi)
            if img is not None and size >= readable:
                return size, lo, img, "under the captions"
    for size in sizes:
        img = fits(size, top, floor)
        if img is not None:
            return size, top, img, "above the head (small)"
    size = T.get("min_size", 52)
    img, _, _ = card(lines, lk, size)
    return size, top, img, "NO CLEAR SPACE: use a one-line title of 3-5 words"


def layer(title_spec, lk):
    """The title as the renderer wants it: an RGBA strip, its position and its opacity over time."""
    T = lk["title"]
    img, _, bb = card(title_spec["lines"], lk, title_spec["size"])
    arr = np.array(img)
    hold, fade = T.get("hold", 3.5), T.get("fade_out", 0.3)

    def alpha(t):
        if t < hold:
            return 1.0
        return max(0.0, 1 - (t - hold) / fade) if fade else 0.0

    def rise(t):
        return int(12 * (1 - alpha(t))) if t >= hold else 0

    return {"img": arr, "x": 0, "y": int(title_spec["top"]), "alpha": alpha, "rise": rise}
