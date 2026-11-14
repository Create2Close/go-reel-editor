"""Listen back: the editor hears its own cut before anyone sees it.

A cut is built from a transcript. If the transcript missed a retake, or timed a word wrong, the cut plays something
other than what the editor believes: a line twice, dead air, captions over the wrong words. So after every cut:

  1. the cut's sound is built exactly as the render builds it;
  2. it is measured: a silence of 0.7 s or more is dead air (the cut should have closed it), and a short burst of
     sound set apart at the edge of a piece, next to a word that was cut, is that word's tail (a stray "s");
  3. it is transcribed again, on its own, and compared word for word with what the cut is meant to say:
       words that play but are not in the cut  -> a retake or a stumble is still in there
       words of the cut that are not heard     -> clipped, or the transcript put them somewhere else
       a run of words heard later than expected -> something between them plays that should not; captions drift
The cut is read in its own pieces (a few seconds each, split at its joints): short pieces are what keeps the
transcriber from tidying a repeat away a second time.

The result is cached in edit/heard.json against the exact cut, so a draft or a final does not listen twice.
GRE_LISTEN=0 switches the transcription off (the tests; a machine with no transcriber skips it by itself): the dead-air
measure still runs."""
import hashlib, json, os, shutil, tempfile
from difflib import SequenceMatcher
from pathlib import Path
from .common import FPS
from .words import norm
from . import hear

DEAD_AIR = 0.7
DRIFT = 0.4
SLIPPED = 4                                 # this many words in a row, all late (or all early): the cut has slipped


def clock(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def key(w):
    """A word as the comparison sees it: '$79' = '79', '7.11%' = '7.11' = '711', 'Rates,' = 'rates'."""
    return norm(w).replace("$", "").replace("%", "")


def cut_id(cuts):
    sig = [(s["ci"], s["start"], s["end"], s["first_word"], s["last_word"], bool(s.get("more")), s.get("stray"))
           for s in cuts["segments"]]
    return hashlib.sha1(json.dumps(sig).encode()).hexdigest()[:16]


def chunks(lengths, shortest=3.0, longest=8.0):
    """The cut as the listen-back reads it: its own pieces, joined until each is at least `shortest` seconds (a
    lone word is hard to hear right) and cut at a joint before it passes `longest`."""
    out, t = [], 0.0
    for d in lengths:
        if out and (out[-1][1] - out[-1][0] < shortest or (d < shortest and out[-1][1] - out[-1][0] + d <= longest)):
            out[-1][1] = round(t + d, 3)
        else:
            out.append([round(t, 3), round(t + d, 3)])
        t += d
    return out


def _hear(wav, lengths, log):
    """The cut transcribed on its own -> [{"w", "start", "end"}], or None when this computer cannot (or must not)."""
    from . import transcribe
    if os.environ.get("GRE_LISTEN", "1") == "0" or not transcribe.ready():
        return None
    out = Path(wav).with_suffix(".json")
    log("listening back to the cut (about as long as the cut itself)")
    d = transcribe.transcribe([wav], out, quiet=True, at={Path(wav).name: chunks(lengths)})
    return d["clips"][0]["words"]


def compare(expected, heard, segs=None, ok=()):
    """expected: the played words ({"i", "heard", "start", "end"}); heard: the listen-back words. ok: words Claude
    has checked and accepts as they are (keep.json "heard_ok"): a difference on one of them is only a note.
    -> (times {word index: [start, end]}, fixes, notes)."""
    from .cut import source_time
    E = [key(p["heard"]) for p in expected]
    Hw = [w for w in heard if key(w["w"])]
    H = [key(w["w"]) for w in Hw]
    times, fixes, notes, late = {}, [], [], []
    ok = {key(x) for x in ok}
    digits = lambda ks: sorted(k for k in ks if any(c.isdigit() for c in k))
    seg_of = {i: n for n, sg in enumerate(segs or []) if not sg.get("more")
              for i in range(sg["first_word"], sg["last_word"] + 1)}

    def joint(lo, hi):
        """Is there a cut between expected word lo and expected word hi? When the take plays unbroken from one to
        the other, a word in between cannot have been clipped: it was only heard another way. The two ends of the
        video count as cuts."""
        if not segs:
            return True
        if lo < 0 or hi >= len(expected):
            return True
        n0, n1 = seg_of.get(expected[lo]["i"]), seg_of.get(expected[hi]["i"])
        if n0 is None or n1 is None or n1 < n0:
            return True
        return any(A["ci"] != B["ci"] or abs(B["start"] - A["end"]) > 0.02 for A, B in zip(segs[n0:n1], segs[n0 + 1:n1 + 1]))

    def where(t0, t1):
        if not segs:
            return ""
        (c, a), (_, b) = source_time(segs, t0), source_time(segs, t1)
        return f' ({c} {a:.1f}-{b:.1f} s: to cut it, add {{"from": {a:.1f}, "to": {b:.1f}}} to "drop" in keep.json)'
    for tag, a0, a1, b0, b1 in SequenceMatcher(None, E, H, autojunk=False).get_opcodes():
        said = " ".join(p["heard"] for p in expected[a0:a1])
        got = " ".join(w["w"] for w in Hw[b0:b1])
        if tag == "equal":
            run = []
            for k in range(a1 - a0):
                e, h = expected[a0 + k], Hw[b0 + k]
                times[e["i"]] = [h["start"], h["end"]]
                off = h["start"] - e["start"]
                if abs(off) > DRIFT and (not run or (run[-1][2] > 0) == (off > 0)):
                    run.append((e, h, off))
                    continue
                late += run if len(run) >= SLIPPED else []
                run = [(e, h, off)] if abs(off) > DRIFT else []
            late += run if len(run) >= SLIPPED else []
        elif tag == "insert":
            t0, t1 = Hw[b0]["start"], Hw[b1 - 1]["end"]
            if b1 - b0 >= 2 or t1 - t0 >= 0.6:
                fixes.append(f'{clock(t0)}-{clock(t1)} plays words that are not in the cut: "{got}". '
                             f'A retake or a stumble is still in there{where(t0, t1)}')
            else:
                notes.append(f'{clock(t0)} an extra "{got}" is heard')
        elif tag == "delete":
            if all(k in ok for k in E[a0:a1]):
                notes.append(f'{clock(expected[a0]["start"])} "{said}" is not heard clearly (accepted)')
            elif not joint(a0 - 1, a1):
                notes.append(f'{clock(expected[a0]["start"])} "{said}" is not heard clearly, and nothing was cut '
                             f'there: said softly, or run together')
            elif a1 - a0 >= 2 or len(E[a0]) >= 4 or digits(E[a0:a1]):
                fixes.append(f'{clock(expected[a0]["start"])} the cut should say "{said}" and it is not heard there '
                             f'(clipped, or those words are somewhere else in the take). If you have checked it and '
                             f'it is right, list the word in "heard_ok" in keep.json')
            else:
                notes.append(f'{clock(expected[a0]["start"])} "{said}" is not heard clearly')
        else:
            t0, t1 = Hw[b0]["start"], Hw[b1 - 1]["end"]
            if "".join(E[a0:a1]) == "".join(H[b0:b1]):          # "30 year" and "30-year": the same words
                for k in range(a1 - a0):
                    times[expected[a0 + k]["i"]] = [t0, t1]
            elif digits(E[a0:a1]) != digits(H[b0:b1]) and not all(k in ok for k in digits(E[a0:a1])) \
                    and joint(a0 - 1, a1):
                fixes.append(f'{clock(t0)} the cut should say "{said}" and it sounds like "{got}": a number may be '
                             f'clipped or misheard. Numbers are the argument: check that piece ends after the whole '
                             f'number. If it is right as it is, list it in "heard_ok" in keep.json')
            elif max(a1 - a0, b1 - b0) >= 3 and SequenceMatcher(None, "".join(E[a0:a1]), "".join(H[b0:b1])).ratio() < 0.6:
                fixes.append(f'{clock(t0)}-{clock(t1)} the cut should say "{said}" and it plays "{got}"{where(t0, t1)}')
            else:
                notes.append(f'{clock(t0)} "{said}" is heard as "{got}" (fine if the caption says what they meant)')
                for k in range(a1 - a0):            # one sound heard two ways: spread the time over the words
                    f0 = t0 + (t1 - t0) * k / (a1 - a0)
                    times[expected[a0 + k]["i"]] = [round(f0, 3), round(f0 + (t1 - t0) / (a1 - a0), 3)]
    if late:
        e, h, _ = late[0]
        fixes.append(f'from {clock(e["start"])} ("{" ".join(x["heard"] for x, _, _ in late[:5])}") the words play '
                     f'{abs(h["start"] - e["start"]):.1f} s {"later" if h["start"] > e["start"] else "earlier"} than '
                     f'the cut expects ({len(late)} words): something between them is in the cut that should not be')
    return times, fixes, notes


def strays(segs, lengths):
    """The leftover sounds cut.py marked at the joints of a restart (the s of a cut "rates,"), in cut time.
    -> [[cut time, seconds of sound, word index, "start" | "end", clip, seconds in the clip]]"""
    out, t = [], 0.0
    for s, d in zip(segs, lengths):
        for a, b, i, side in s.get("stray") or []:
            out.append([round(t + max(0.0, a - s["start"]), 2), round(b - a, 2), i, side, s["clip"], a])
        t += d
    return out


def judge(res, cuts, flat, keep):
    """The FIX lines and notes for a listen-back (measured silences + heard words) against this cut and keep.json."""
    from .captions import played_words
    from .cut import source_time
    segs = cuts["segments"]
    res.update(fix=[], notes=[], times={})
    for a, b in res.get("silences") or []:
        c, s0 = source_time(segs, a)
        res["fix"].append(f"{clock(a)}-{clock(b)} is dead air: {b - a:.1f} s with no sound ({c} {s0:.1f} s)")
    ok = {key(x) for x in keep.get("heard_ok") or ()}
    for t, d, i, side, c, s0 in res.get("strays") or []:
        if i >= len(flat) or key(flat[i]["w"]) in ok:
            continue
        other = flat[i - 1]["w"] if side == "start" else flat[min(i + 1, len(flat) - 1)]["w"]
        res["fix"].append(
            f'{clock(t)} a stray sound ({d:.2f} s, set apart by a gap) at the {side} of the piece with '
            f'"{flat[i]["w"]}", next to the cut word "{other}": the cut word\'s tail is still in ({c} {s0:.1f} s: add '
            f'{{"from": {s0 - 0.03:.2f}, "to": {s0 + d + 0.05:.2f}}} to "drop" in keep.json; if it is the word '
            f'itself, list it in "heard_ok")')
    if res.get("listened"):
        times, fixes, notes = compare(played_words(flat, cuts, keep), res["words"], segs, keep.get("heard_ok") or ())
        res.update(times={str(k): v for k, v in times.items()}, notes=notes)
        res["fix"] += fixes
    return res


def run(E, cuts, flat, keep, log=print):
    from .render import build_audio, frame_plan
    segs = cuts["segments"]
    res = {"cut": cut_id(cuts), "listened": False, "silences": [], "strays": [], "words": None}
    if not segs:
        return judge(res, cuts, flat, keep)
    tmp = Path(tempfile.mkdtemp(prefix="gre-listen-"))
    try:
        nframes = frame_plan(segs)
        wav = build_audio(segs, cuts["clips"], nframes, tmp)
        env = hear.envelope(hear.load(wav))
        res["silences"] = [[a, b] for a, b in hear.silences(env, None, DEAD_AIR, 0.0, len(env) / 100 - 0.3)]
        res["strays"] = strays(segs, [n / FPS for n in nframes])
        heard = _hear(wav, [n / FPS for n in nframes], log)
        if heard is not None:
            res.update(listened=True, words=heard)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return judge(res, cuts, flat, keep)


def ensure(E, cuts_path, flat, keep, log=print):
    """The listen-back for this exact cut. The listening is done once per cut (edit/heard.json); the judging is done
    every time, so a word added to "heard_ok" counts at once."""
    cuts = json.loads(Path(cuts_path).read_text(encoding="utf-8"))
    hj = Path(E) / "heard.json"
    res = None
    if hj.exists():
        try:
            res = json.loads(hj.read_text(encoding="utf-8"))
        except ValueError:
            res = None
        want = os.environ.get("GRE_LISTEN", "1") != "0"
        if res and (res.get("cut") != cut_id(cuts) or (want and not res.get("listened") and _can_listen())):
            res = None
    res = judge(res, cuts, flat, keep) if res else run(E, cuts, flat, keep, log)
    hj.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    return res


def _can_listen():
    from . import transcribe
    return transcribe.ready()


def report(res, log=print):
    """The lines Claude reads. Returns the FIX lines (a draft with one of them is not shown to the member)."""
    for f in res["fix"]:
        log("  FIX   " + f)
    for n in res["notes"]:
        log("  note  " + n)
    if not res["listened"]:
        log("  note  the cut was measured for dead air but not listened back (no transcriber on this computer yet)")
    elif not res["fix"]:
        log("listened back: the cut plays the words it is meant to, with no dead air")
    return res["fix"]
