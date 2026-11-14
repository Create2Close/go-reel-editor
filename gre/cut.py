"""keep.json (which words stay) -> cuts.json (exact source times), measured on the waveform.

  * fillers (um, uh) inside a kept range are cut out
  * every pause of 0.5 s or more inside a kept range is tightened (the commas too: never protect a "beat"). The pause
    is found on the WAVEFORM, not from the word times: a transcript can time a word wrong, a silence is a silence
  * every edge is moved to the real sound: the cut starts 0.06 s before the first sound of the first word and ends
    0.15 s after the last sound of the last word (a soft ending is room tone, never clipped), and never runs into a
    word that was cut. "The sound of the word" is the whole stretch of sound it sits in, up to the next word: a
    number's last digits are never clipped because the transcript timed the number short
  * a stretch named in keep.json "drop" (source seconds) never plays, whatever the words say
  * a piece of sound that no kept word belongs to is left out (and said so): the cut only plays what it can name.
    A piece that is the rest of a kept word (a pause inside a number said digit by digit) plays, marked "more":
    it carries no word of its own
Timing that watches the waveform: 10 ms RMS envelope, speech = the local noise floor + 15 dB."""
import json
from pathlib import Path
import numpy as np
from .common import UserError
from .words import FILLERS, norm
from . import hear

PAUSE = 0.5
HEAD, TAIL = 0.06, 0.15
STRAY, STRAY_GAP = 0.30, 0.15               # a burst this short, this far from the rest, next to a cut word


class Envelope:
    def __init__(self, path):
        x = hear.load(path)
        self.env = hear.envelope(x) if len(x) >= hear.HOP else np.full(1, -180.0)
        self.n = len(self.env)
        self.thr = hear.threshold(self.env)
        # Two levels. `thr` is anything above the room: a breath, the fading end of an s. `soft` is speech: a breath
        # after a sentence is not something to hold a cut open for, and half a second of it is a pause like any other.
        self.soft = hear.speech_level(self.env, self.thr)
        self.isl = hear.islands(self.env, self.soft, pad=0.0)

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

    def fade(self, t, fwd=0.15):
        """t moved forward over a soft ending (sound above the room, up to `fwd` s)."""
        k = min(self.n - 1, int(round(t * 100)))
        hi = min(self.n - 1, k + int(fwd * 100))
        while k < hi and self.env[k] > self.thr:
            k += 1
        return k / 100

    def rise(self, t, back=0.2):
        """t moved back over a soft beginning (an f, an h, a short breath in: up to `back` s)."""
        k = max(0, min(self.n - 1, int(round(t * 100))))
        lo = max(0, k - int(back * 100))
        while k > lo and self.env[k - 1] > self.thr:
            k -= 1
        return k / 100

    def island(self, t, near=0.08):
        """(start, end) of the stretch of speech that t sits in or touches, soft edges included, else None."""
        for a, b in self.isl:
            if a - near <= t <= b + near:
                return self.rise(a), self.fade(b)
            if a > t + near:
                break
        return None

    def silences(self, a, b, said=()):
        """Every pause of PAUSE or more between a and b: no speech in it (a breath alone does not fill a pause).
        Each starts after the soft ending of the sound before it and ends before the soft start of the next.

        Two witnesses. The waveform says where it is quiet; the transcript (`said`: the spans of words timed at a
        believable length) says where a word is. A quiet voice in a loud room sinks under the speech level, and
        "of your business. If you're" must not lose "business. If" as a pause: where a word sits, quiet is not a
        pause. (A word timed far too long vouches for nothing: see `believable`. And if a word really was timed into
        a silence, the listen-back says so: dead air, or the word not heard.)"""
        k0, k1 = max(0, int(round(a * 100))), min(self.n, int(round(b * 100)))
        if k1 <= k0:
            return []
        env = self.env[k0:k1]
        quiet = env <= self.soft
        if said:
            word = np.zeros(k1 - k0, bool)
            for x, y in said:
                word[max(0, int(x * 100) - k0):max(0, int(y * 100) - k0)] = True
            quiet &= ~word
        edges = np.flatnonzero(np.diff(np.concatenate(([0], quiet.view(np.int8), [0]))))
        runs = []
        for x, y in zip(edges[::2], edges[1::2]):
            if runs and x - runs[-1][1] <= 3:           # a click of 30 ms does not end a pause
                runs[-1][1] = int(y)
            else:
                runs.append([int(x), int(y)])
        out = []
        for x, y in runs:
            if y - x < PAUSE * 100:
                continue
            s0, s1 = (k0 + x) / 100, (k0 + y) / 100
            s0, s1 = min(self.fade(s0), s1), max(self.rise(s1), s0)
            if s1 - s0 >= 0.25:
                out.append((s0, s1))
        return out

    def sound(self, a, b):
        return hear.sound(self.env, a, b, self.thr)


def _drops(keep, clip_paths):
    """keep.json "drop": [{"clip": name (optional with one clip), "from": s, "to": s, "why": ...}] -> {ci: [(a, b)]}."""
    names = [Path(c).name for c in clip_paths]
    out = {}
    for k, d in enumerate(keep.get("drop") or [], 1):
        name = d.get("clip") or (names[0] if len(names) == 1 else None)
        if name not in names:
            raise UserError(f'keep.json "drop" {k}: "clip" must be one of {", ".join(names)}')
        try:
            a, b = float(d["from"]), float(d["to"])
        except (KeyError, TypeError, ValueError):
            raise UserError(f'keep.json "drop" {k}: needs "from" and "to" in seconds of the clip')
        if b <= a:
            raise UserError(f'keep.json "drop" {k}: "to" must be after "from"')
        out.setdefault(names.index(name), []).append((a, b))
    return out


def believable(w):
    """Is this word timed at a length it could be said in? One that is far longer has swallowed a pause, or a take
    the transcript missed, and vouches for nothing."""
    return w["end"] - w["start"] <= 0.3 + 0.12 * hear.spoken(w["w"]) * max(3, len(w["w"]) / hear.spoken(w["w"]))


def _pieces(start, end, env, drops, said=()):
    """[start, end] minus its real silences (each side keeps its room tone) and minus the dropped stretches."""
    holes = [(s0 + TAIL, s1 - HEAD) for s0, s1 in env.silences(start, end, said)]
    holes += [(a, b) for a, b in drops if b > start and a < end]
    out, t = [], start
    for a, b in sorted(holes):
        if a > t:
            out.append((t, min(a, end)))
        t = max(t, b)
    if t < end:
        out.append((t, end))
    return [(a, b) for a, b in out if b - a >= 0.02 and env.sound(a, b) >= 0.03]


def build(flat, keep, clip_paths, log=print):
    envs = {}
    drops = _drops(keep, clip_paths)
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
        # A word time can be a little off (a number most of all: "7.4%" is one word and five sounds), so each edge
        # goes out to the end of the SOUND the word sits in, not to where the transcript says the word stops.
        isl0, isl1 = env.island(w0["start"]), env.island(w1["end"])
        # ... except towards a CUT word in the same stretch of sound (a restart: "rates, | mortgage rates"): going
        # out to the start of that sound would bring the cut word's tail back in
        after_cut = f > 0 and flat[f - 1]["ci"] == ci and (f - 1) not in kept and isl0 and flat[f - 1]["end"] > isl0[0]
        start = max(0.0, min(env.onset(w0["start"]), isl0[0] if isl0 and not after_cut else w0["start"]) - HEAD)
        end = (max(isl1[1], w1["end"]) if isl1 else env.offset(w1["end"])) + TAIL
        # never into the word before (kept or cut) or the word after
        if f > 0 and flat[f - 1]["ci"] == ci:
            start = max(start, min(w0["start"] - 0.02, flat[f - 1]["end"] + 0.02))
        if l + 1 < len(flat) and flat[l + 1]["ci"] == ci:      # never into the next word, kept or cut
            end = min(end, max(w1["end"] + 0.03, flat[l + 1]["start"] - 0.03))
        start = min(start, w0["start"])
        end = max(end, w1["end"])
        # At a restart (the word before, or after, was cut and sits right against this run), a short burst of sound
        # set apart from the rest by a gap is the cut word's tail, not ours. It is marked, and the listen-back
        # makes it a FIX: Claude drops it, or says it is the word itself.
        stray = []
        fine = [(start + a, start + b) for a, b in
                hear.islands(env.env[int(start * 100):int(end * 100)], env.thr, gap=0.06, pad=0.0, short=0.02)]
        if len(fine) >= 2:
            if after_cut or (f > 0 and flat[f - 1]["ci"] == ci and (f - 1) not in kept
                             and start - flat[f - 1]["end"] < 0.3):
                (a0, b0), (a1, _) = fine[0], fine[1]
                if b0 - a0 <= STRAY and a1 - b0 >= STRAY_GAP:
                    stray.append((a0, b0, f, "start"))
            if l + 1 < len(flat) and flat[l + 1]["ci"] == ci and (l + 1) not in kept \
                    and flat[l + 1]["start"] - end < 0.3:
                (_, b8), (a9, b9) = fine[-2], fine[-1]
                if b9 - a9 <= STRAY and a9 - b8 >= STRAY_GAP:
                    stray.append((a9, b9, l, "end"))
        # the waveform has the last word: no silence of PAUSE or more plays, and nothing that was dropped
        pieces = _pieces(start, end, env, drops.get(ci, ()),
                         [(flat[i]["start"], flat[i]["end"]) for i in s["words"] if believable(flat[i])])
        if not pieces:
            log(f"  note: W{f}-W{l} ({' '.join(flat[i]['w'] for i in s['words'][:6])}) has no sound: left out")
            continue
        owner = []
        for i in s["words"]:
            w = flat[i]
            if any(a <= (w["start"] + w["end"]) / 2 <= b for a, b in drops.get(ci, ())):
                owner.append(None)                              # the word itself was dropped
                continue
            over = [min(w["end"], b) - max(w["start"], a) for a, b in pieces]
            k = int(np.argmax(over))
            if over[k] <= 0:                                    # a word timed inside a silence: the nearest sound
                mid = (w["start"] + w["end"]) / 2
                k = int(np.argmin([0 if a <= mid <= b else min(abs(mid - a), abs(mid - b)) for a, b in pieces]))
            owner.append(max(k, max((o for o in owner if o is not None), default=0)))
        for k, (a, b) in enumerate(pieces):
            mine = [i for i, o in zip(s["words"], owner) if o == k]
            seg = {"clip": Path(clip).name, "ci": ci, "start": round(a, 3), "end": round(b, 3), "group": s["group"]}
            here = [[round(x, 2), round(y, 2), i, side] for x, y, i, side in stray if a - 0.01 <= x < b]
            if here:
                seg["stray"] = here
            if mine:
                out.append(dict(seg, first_word=mine[0], last_word=mine[-1]))
                continue
            # no word starts here. Is it the rest of one? ("seven ... point four percent" is ONE written word,
            # 7.4%, and a pause inside it must not cost its second half.) Then it plays, as more of that word.
            rest = [i for i, o in zip(s["words"], owner)
                    if o is not None and min(flat[i]["end"], b) - max(flat[i]["start"], a) >= 0.05]
            if rest:
                out.append(dict(seg, first_word=rest[0], last_word=rest[0], more=True))
            elif b - a >= 0.3:
                log(f"  note: {b - a:.1f} s of sound with no words in it at {Path(clip).name} {a:.1f} s: left out")
    # no two segments of the same clip may overlap in the source (a continuous split shares one boundary)
    by = sorted(range(len(out)), key=lambda k: (out[k]["ci"], out[k]["start"]))
    for p, q in zip(by, by[1:]):
        A, B = out[p], out[q]
        if A["ci"] == B["ci"] and A["end"] > B["start"]:
            mid = round((flat[A["last_word"]]["end"] + flat[B["first_word"]]["start"]) / 2, 3)
            mid = mid if A["start"] < mid < B["end"] else round((A["end"] + B["start"]) / 2, 3)
            A["end"], B["start"] = mid, mid
    out = [s for s in out if s["end"] - s["start"] >= 0.12]
    return out


def summary(segs, flat):
    total = sum(s["end"] - s["start"] for s in segs)
    return {"segments": len(segs), "seconds": round(total, 2),
            "words": sum(s["last_word"] - s["first_word"] + 1 for s in segs if not s.get("more"))}


def source_time(segs, t):
    """Where a moment of the cut sits in the source: (clip name, seconds)."""
    cum = 0.0
    for s in segs:
        d = s["end"] - s["start"]
        if t < cum + d or s is segs[-1]:
            return s["clip"], round(s["start"] + min(d, max(0.0, t - cum)), 2)
        cum += d
    return None, 0.0


def write(edit_dir, segs, clip_paths):
    p = Path(edit_dir) / "cuts.json"
    p.write_text(json.dumps({"clips": [str(c) for c in clip_paths], "segments": segs}, indent=1), encoding="utf-8")
    return p
