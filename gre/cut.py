"""keep.json (which words stay) -> cuts.json (exact source times), measured on the waveform.

  * fillers (um, uh) inside a kept range are cut out
  * every pause of 0.5 s or more inside a kept range is tightened (the commas too: never protect a "beat")
  * every edge is moved to the real sound: the cut starts 0.06 s before the first sound of the first word and ends
    0.15 s after the last sound of the last word (a soft ending is room tone, never clipped), and never runs into a
    word that was cut
Timing that watches the waveform: 10 ms RMS envelope, speech = the local noise floor + 15 dB."""
import json, subprocess
from pathlib import Path
import numpy as np
from .common import UserError
from .words import FILLERS, norm

PAUSE = 0.5
HEAD, TAIL = 0.06, 0.15


class Envelope:
    def __init__(self, path):
        x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                                          "-f", "s16le", "-"], capture_output=True).stdout, dtype=np.int16).astype(float)
        H = 160
        x = x[:len(x) // H * H].reshape(-1, H) if len(x) >= H else np.zeros((1, H))
        self.env = 20 * np.log10(np.sqrt((x ** 2).mean(1)) / 32768 + 1e-9)
        self.n = len(self.env)

    def floor(self, t):
        k = int(t * 100)
        w = self.env[max(0, k - 300):k + 300]
        w = w[w > -90]
        return float(np.percentile(w, 10)) if len(w) else -60.0

    def onset(self, t, back=0.15):
        """The first sound at or before word start t (searching back up to `back` s)."""
        th = self.floor(t) + 15
        k = int(t * 100)
        lo = max(0, k - int(back * 100))
        j = k
        while j > lo and self.env[j - 1] > th:
            j -= 1
        return j / 100

    def offset(self, t, fwd=0.35):
        """The last sound at or after word end t (a soft ending trails above floor + 8 dB)."""
        th = self.floor(t) + 8
        k = min(self.n - 1, int(t * 100))
        hi = min(self.n - 1, k + int(fwd * 100))
        j = k
        while j < hi and self.env[j:j + 3].max() > th:
            j += 1
        return j / 100


def build(flat, keep, clip_paths, log=print):
    envs = {}
    segs = []
    for si, r in enumerate(keep["segments"]):
        a, b = int(r["from"]), int(r["to"])
        if not (0 <= a <= b < len(flat)):
            raise UserError(f"segment {si + 1}: W{a}-W{b} is outside the transcript (W0-W{len(flat) - 1})")
        idx = [i for i in range(a, b + 1) if norm(flat[i]["w"]) not in FILLERS]
        # split at clip changes and at pauses >= PAUSE
        runs = []
        for i in idx:
            if runs and flat[i]["ci"] == flat[runs[-1][-1]]["ci"] and i == runs[-1][-1] + 1 \
                    and flat[i]["start"] - flat[runs[-1][-1]]["end"] < PAUSE:
                runs[-1].append(i)
            elif runs and flat[i]["ci"] == flat[runs[-1][-1]]["ci"] and i > runs[-1][-1] + 1 \
                    and all(norm(flat[x]["w"]) in FILLERS for x in range(runs[-1][-1] + 1, i)) \
                    and flat[i]["start"] - flat[runs[-1][-1]]["end"] < PAUSE:
                runs[-1].append(i)            # a filler between two words with no pause: cut later by the joint
            else:
                runs.append([i])
        for run in runs:
            segs.append({"group": si, "words": run})
    kept = {i for s in segs for i in s["words"]}
    out = []
    for s in segs:
        f, l = s["words"][0], s["words"][-1]
        ci = flat[f]["ci"]
        clip = clip_paths[ci]
        env = envs.get(ci) or envs.setdefault(ci, Envelope(clip))
        w0, w1 = flat[f], flat[l]
        start = max(0.0, env.onset(w0["start"]) - HEAD)
        end = env.offset(w1["end"]) + TAIL
        # never into a cut word: the word before (if cut) and the word after (if cut)
        if f > 0 and flat[f - 1]["ci"] == ci and (f - 1) not in kept:
            start = max(start, min(w0["start"] - 0.02, flat[f - 1]["end"] + 0.02))
        if l + 1 < len(flat) and flat[l + 1]["ci"] == ci:      # never into the next word, kept or cut
            end = min(end, max(w1["end"] + 0.03, flat[l + 1]["start"] - 0.03))
        start = min(start, w0["start"])
        end = max(end, w1["end"])
        out.append({"clip": Path(clip).name, "ci": ci, "start": round(start, 3), "end": round(end, 3),
                    "first_word": f, "last_word": l, "group": s["group"]})
    # no two segments of the same clip may overlap in the source (a continuous split shares one boundary)
    by = sorted(range(len(out)), key=lambda k: (out[k]["ci"], out[k]["start"]))
    for p, q in zip(by, by[1:]):
        A, B = out[p], out[q]
        if A["ci"] == B["ci"] and A["end"] > B["start"]:
            mid = round((flat[A["last_word"]]["end"] + flat[B["first_word"]]["start"]) / 2, 3)
            A["end"], B["start"] = mid, mid
    out = [s for s in out if s["end"] - s["start"] >= 0.12]
    return out


def summary(segs, flat):
    total = sum(s["end"] - s["start"] for s in segs)
    return {"segments": len(segs), "seconds": round(total, 2),
            "words": sum(s["last_word"] - s["first_word"] + 1 for s in segs)}


def write(edit_dir, segs, clip_paths):
    p = Path(edit_dir) / "cuts.json"
    p.write_text(json.dumps({"clips": [str(c) for c in clip_paths], "segments": segs}, indent=1), encoding="utf-8")
    return p
