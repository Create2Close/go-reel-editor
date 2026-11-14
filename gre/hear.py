"""Hearing on the waveform, with no transcript: where there is sound and where there is none.

The transcript says which words were said; only the waveform says where they are. Everything that must be true of the
SOUND is measured here: the islands of sound a take is made of (each is transcribed on its own, so a second take is
never folded into the first), the silences inside a cut (dead air), and the sound a transcript has no words for.

numpy only: the transcriber's own Python environment imports this file too (it has no Pillow and no gre)."""
import re
import subprocess
import numpy as np

SR = 16000
HOP = 160                                   # 10 ms


def load(path):
    """Mono 16 kHz samples in -1..1."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le",
                          "-"], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def envelope(x):
    """Loudness every 10 ms, in dBFS."""
    x = np.asarray(x, dtype=np.float64)
    if len(x) < HOP:
        return np.full(1, -180.0)
    x = x[:len(x) // HOP * HOP].reshape(-1, HOP)
    return 20 * np.log10(np.sqrt((x ** 2).mean(1)) + 1e-9)


def threshold(env):
    """The level sound has to pass to count: 12 dB over the room, and never more than 32 dB under the loud speech
    (a tight cut has almost no room tone to measure, so the room is then taken from the speech)."""
    live = env[env > -85]
    if len(live) < 20:
        return -50.0
    p95, room = np.percentile(live, 95), np.percentile(live, 10)
    return float(max(room + 12, p95 - 32) if room < p95 - 20 else p95 - 32)


def islands(env, thr=None, gap=0.25, pad=0.15, short=0.12):
    """[(start, end)] in seconds: every stretch of sound, joined across gaps under `gap`, blips under `short` dropped,
    each widened by `pad` (never past the middle of the silence next to it)."""
    thr = threshold(env) if thr is None else thr
    on = env > thr
    n = len(on)
    edges = np.flatnonzero(np.diff(np.concatenate(([0], on.view(np.int8), [0]))))
    runs = [[int(a), int(b)] for a, b in zip(edges[::2], edges[1::2])]
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] < gap * 100:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    merged = [(a, b) for a, b in merged if b - a >= short * 100]
    out = []
    for k, (a, b) in enumerate(merged):
        lo = merged[k - 1][1] if k else 0
        hi = merged[k + 1][0] if k + 1 < len(merged) else n
        out.append((max((a + lo) // 2, a - round(pad * 100)) / 100, min((b + hi + 1) // 2, b + round(pad * 100)) / 100))
    return out


def utterances(isl, join=0.6, longest=20.0):
    """Islands closer than `join` are one utterance (one thing said in one breath), up to `longest` seconds."""
    out = []
    for a, b in isl:
        if out and a - out[-1][1] < join and b - out[-1][0] <= longest:
            out[-1][1] = b
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def fit(utts, env, longest=28.0):
    """No utterance longer than `longest` (the transcriber reads 30 s at a time): a longer one, which happens when a
    loud room leaves no silence to find, is split at its quietest moment in the second half of each window."""
    out = []
    for a, b in utts:
        while b - a > longest:
            k0, k1 = int((a + longest / 2) * 100), int((a + longest) * 100)
            win = np.convolve(env[k0:k1], np.ones(20) / 20, mode="same")
            cut = (k0 + int(np.argmin(win))) / 100
            out.append((a, cut))
            a = cut
        out.append((a, b))
    return out


def silences(env, thr=None, shortest=0.5, a=0.0, b=None, blip=0.03):
    """[(start, end)] of every stretch between a and b with no sound for `shortest` seconds or more. A click shorter
    than `blip` does not end a silence."""
    thr = threshold(env) if thr is None else thr
    k0 = max(0, int(round(a * 100)))
    k1 = len(env) if b is None else min(len(env), int(round(b * 100)))
    if k1 <= k0:
        return []
    quiet = env[k0:k1] <= thr
    edges = np.flatnonzero(np.diff(np.concatenate(([0], quiet.view(np.int8), [0]))))
    runs = [[int(x), int(y)] for x, y in zip(edges[::2], edges[1::2])]
    merged = []
    for x, y in runs:
        if merged and x - merged[-1][1] <= blip * 100:
            merged[-1][1] = y
        else:
            merged.append([x, y])
    return [((k0 + x) / 100, (k0 + y) / 100) for x, y in merged if y - x >= shortest * 100]


def sound(env, a, b, thr=None):
    """Seconds of sound between a and b."""
    thr = threshold(env) if thr is None else thr
    k0, k1 = max(0, int(round(a * 100))), min(len(env), int(round(b * 100)))
    return float((env[k0:k1] > thr).sum()) / 100 if k1 > k0 else 0.0


def spoken(word):
    """About how many words it takes to SAY a written word: '$400,000' is four, '7.11%' is five, 'payment' is one."""
    parts = word.replace("—", "-").split("-")
    words = sum(1 for p in parts if any(c.isalpha() for c in p) and not any(c.isdigit() for c in p))
    core = "".join(c for c in word if c.isdigit())
    if not core:
        return max(1, words)
    zeros = len(core) - len(core.rstrip("0"))
    said = max(1, len(core) - zeros) + (zeros >= 2) + (zeros >= 3)
    return said + words + ("$" in word) + ("%" in word) + ("." in word.strip(".,!?%"))


# ---------- figures as they are said, and word boundaries where the sound puts them ----------

ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen").split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def number(n):
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + (" " + ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return ONES[n // 100] + " hundred" + (" " + number(n % 100) if n % 100 else "")
    for size, name in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= size:
            return number(n // size) + " " + name + (" " + number(n % size) if n % size else "")


def spell(word):
    """A written figure the way it is SAID, for the aligner (it matches letters to sound, and a digit has none):
    '$400,000' -> 'four hundred thousand dollars', '7.11%' -> 'seven point one one percent', '30-year' -> 'thirty
    year', '2026' -> 'twenty twenty six'. A word with no digit comes back as it is."""
    if not any(c.isdigit() for c in word):
        return word
    if re.search(r"\d[-–]|[-–]\d", word) or re.search(r"[A-Za-z]{2,}", word):       # 30-year, 12th, 401k
        parts = [p for p in re.split(r"[-–]|(?<=\d)(?=[A-Za-z])|(?<=[A-Za-z])(?=\d)", word) if p]
        if len(parts) > 1:
            return " ".join(spell(p) for p in parts if re.sub(r"\W", "", p).lower() not in ("st", "nd", "rd", "th", ""))
    m = re.match(r"^\D*?(\$?)(\d[\d,]*)(?:\.(\d+))?(%?)([kK]?)\W*$", word)
    if not m:
        return word
    cur, whole, frac, pct, k = m.groups()
    n = int(whole.replace(",", ""))
    if 1900 <= n <= 2099 and "," not in whole and not (cur or frac or pct or k):
        said = number(n // 100) + " " + (number(n % 100) if n % 100 >= 10 else "oh " + ONES[n % 100] if n % 100 else "hundred")
    else:
        said = number(n) if n < 10 ** 12 else " ".join(ONES[int(d)] for d in whole if d.isdigit())
    if frac:
        said += " point " + " ".join(ONES[int(d)] for d in frac)
    return said + (" thousand" if k else "") + (" dollars" if cur else "") + (" percent" if pct else "")


def settle(words, env, thr):
    """Put each word boundary where the sound says it is. The aligner starts a word the moment the one before it
    ends, so after a pause the word 'begins' early: its span opens with the tail of the previous word (the s of
    "rates,"), then the silence, then the word itself. When a restart is cut there ("Mortgage rates, | mortgage
    rates just dropped"), that tail plays as a stray sound. So: a silence of 0.2 s or more inside a one-word span,
    with sound running into it straight from the previous word, is the gap BETWEEN the two words. The previous
    word gets the sound before it; this word starts after it."""
    for k in range(1, len(words)):
        p, w = words[k - 1], words[k]
        if w["start"] - p["end"] > 0.06 or len(spell(w["w"]).split()) != 1:
            continue                                # already apart, or a figure (a pause inside "7.4%" is its own)
        room = words[k + 1]["start"] if k + 1 < len(words) else w["end"] + 0.6
        gaps = silences(env, thr, 0.2, w["start"], max(w["end"], room))
        if not gaps or gaps[0][0] >= w["end"] or gaps[0][0] - w["start"] > 0.45:
            continue                                # no gap in the span, or too much sound before it to be a tail
        g0, g1 = gaps[0]
        if g1 >= room - 0.03:
            continue                                # nothing left for the word itself: leave it alone
        if sound(env, w["start"], g0, thr) >= 0.02:
            p["end"] = round(g0, 3)
        w["start"] = round(g1, 3)
        w["end"] = round(min(max(w["end"], g1 + 0.08), room), 3)
    return words
