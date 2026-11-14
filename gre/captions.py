"""Captions: the words as they play in the cut, chunked into one-line captions, checked against the house rules,
timed from the measured words, drawn in the look's caption style.

captions.txt (Claude writes/edits it): one caption per line, in order, every spoken word exactly once.
  **word**  = bold emphasis (about one every 5 s)      a line starting with #  = a comment
House rules (checked): no periods; a "?" stays; never across a sentence end; never end a line on a small word
(a, the, of, to, and ...); never end on a hyphen; numbers over 10 as numerals (2009, 34, 31st); "Realtor" with a capital R;
one line each, inside the look's width."""
import json, re
from difflib import SequenceMatcher
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .common import W, H, FPS, UserError, font
from .words import norm, SMALL, ends_sentence

ONES = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen "
                                   "fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8,
       "ninth": 9, "tenth": 10, "eleventh": 11, "twelfth": 12, "twentieth": 20, "thirtieth": 30}


def _suffix(n):
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def numerals(tokens):
    """Spoken numbers over 10 -> numerals, keeping the punctuation: 'thirty-four' -> 34, 'two thousand nine' -> 2009,
    'thirty-first' -> 31st. Ten and under stay words. Returns new tokens (merged words become '' placeholders)."""
    out = list(tokens)
    i = 0
    while i < len(out):
        j, val, cur, ordn, used = i, 0, 0, False, False
        while j < len(out):
            raw = out[j]
            core = re.sub(r"[^a-z\-]", "", raw.lower())
            parts = [p for p in core.split("-") if p]
            if not parts or not all(p in ONES or p in TENS or p in ORD or p in ("hundred", "thousand", "and")
                                    for p in parts):
                break
            if parts == ["and"] and not used:
                break
            for p in parts:
                if p in ONES:
                    cur += ONES[p]
                elif p in TENS:
                    cur += TENS[p]
                elif p in ORD:
                    cur += ORD[p]
                    ordn = True
                elif p == "hundred":
                    cur = (cur or 1) * 100
                elif p == "thousand":
                    val += (cur or 1) * 1000
                    cur = 0
            used = True
            j += 1
            if ordn or re.search(r"[.,?!:;]$", raw):
                break
        n = val + cur
        if used and n > 10 and j > i:
            if out[j - 1].lower().strip(".,?!:;") == "and":
                j -= 1
            tail = re.search(r"[.,?!:;\"”]*$", out[j - 1]).group(0)
            lead = re.match(r"^[\"“]*", out[i]).group(0)
            out[i] = lead + (f"{n}{_suffix(n)}" if ordn else (f"{n:,}" if n >= 10000 else str(n))) + tail
            for k in range(i + 1, j):
                out[k] = ""
            i = j
        else:
            i += 1
    return out


def played_words(flat, cuts, keep):
    """Every word that plays, in order, with its time in the CUT and the text to show."""
    disp = keep.get("display", {}) if keep else {}
    out, cum = [], 0.0
    for s in cuts["segments"]:
        for gi in range(s["first_word"], s["last_word"] + 1) if not s.get("more") else ():   # "more": no new word
            w = flat[gi]
            if norm(w["w"]) in ("um", "uh", "uhm", "umm", "erm", "er", "hmm", "mm", "mhm", "ah"):
                continue
            t0 = cum + max(0.0, w["start"] - s["start"])
            t1 = cum + min(s["end"] - s["start"], w["end"] - s["start"])
            out.append({"i": gi, "w": disp.get(str(gi), w["w"]), "heard": w["w"], "start": round(t0, 3),
                        "end": round(t1, 3)})
        cum += s["end"] - s["start"]
    return out


# ---------- figures: a rate takes %, money takes $ ----------

DIGIT = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
         "seven": "7", "eight": "8", "nine": "9"}
EDGE = r"[.,?!:;\"”’)]*"
NUM = re.compile(r"^([\"“(]*)(\$?)(\d[\d,]*(?:\.\d+)?)(%?)(" + EDGE + r")$")
PERCENT = {"percent", "percentage"}
DOLLARS = {"dollars", "dollar", "bucks"}
RATE_TALK = {"rate", "rates", "percent", "apr", "mortgage", "mortgages", "interest", "fed", "30-year", "15-year",
             "fixed", "refinance", "refi", "points", "inflation", "yield"}
MONEY_TALK = {"payment", "payments", "pay", "paying", "paid", "save", "saves", "saving", "savings", "cost", "costs",
              "rent", "loan", "price", "mortgage"}
NOT_A_RATE = {"million", "billion", "trillion", "points", "point", "times", "x", "years", "year", "months", "month",
              "weeks", "week", "days", "day", "miles", "k", "grand", "dollars", "dollar", "bucks", "hours", "minutes",
              "seconds", "stars", "acres", "beds", "baths", "percent", "people", "homes", "houses", "loans", "feet"}


def _core(t):
    return re.sub(r"[^a-z0-9\-']", "", t.lower().replace("’", "'"))


def _tail(t):
    return re.search(EDGE + "$", t).group(0)


def _next(out, i):
    for j in range(i + 1, len(out)):
        if out[j]:
            return j
    return None


def decimals(tokens):
    """Numbers said piece by piece, before anything adds them up: 'seven point one one' -> 7.11,
    'six point eight seven five' -> 6.875, '400 thousand' -> 400,000, '20 grand' -> $20,000."""
    out = list(tokens)
    i = 0
    while i < len(out):
        c = _core(out[i])
        whole = str(ONES[c]) if c in ONES else (c if c.isdigit() and len(c) <= 2 else None)
        j = _next(out, i)
        before = _core(out[i - 1]) if i else ""
        if whole is not None and j is not None and _core(out[j]) == "point" and not _tail(out[i]) \
                and not (c == "one" and before in ("at", "some", "this", "that", "which", "the", "a", "any", "no")):
            k, frac, last = _next(out, j), "", None
            while k is not None and len(frac) < 3 and not _tail(out[j]):
                ck = _core(out[k])
                d = DIGIT.get(ck) or (ck if ck.isdigit() and len(ck) <= 2 else
                                      str(ONES[ck]) if ONES.get(ck, 0) >= 10 else None)
                if d is None:
                    break
                frac, last = frac + d, k
                if _tail(out[k]):
                    break
                k = _next(out, k)
            if frac:
                out[i] = re.match(r"^[\"“(]*", out[i]).group(0) + whole + "." + frac + _tail(out[last])
                for x in range(i + 1, last + 1):
                    out[x] = ""
                i = last + 1
                continue
        m = NUM.match(out[i])
        if m and not (m.group(2) or m.group(4) or m.group(5)) and "." not in m.group(3) and j is not None \
                and _core(out[j]) in ("thousand", "grand"):
            n = int(m.group(3).replace(",", "")) * 1000
            out[i] = m.group(1) + ("$" if _core(out[j]) == "grand" else "") + f"{n:,}" + _tail(out[j])
            out[j] = ""
        i += 1
    return out


def figures(tokens, skip=()):
    """A rate takes %, money takes $, and neither is spelled out: '7.4 percent' -> 7.4%, '940 dollars' -> $940,
    '400,000 dollar loan' -> $400,000 loan, 'that's 79 a month' (in a sentence about money) -> $79 a month, and a bare
    '7.11' in a video that talks rates -> 7.11%. Tokens in `skip` are left alone. Merged words become ''."""
    out = list(tokens)
    talk_rates = any(_core(t) in RATE_TALK or "%" in t for t in out if t)
    for i, t in enumerate(out):
        if not t:
            continue
        m = NUM.match(t)
        j = _next(out, i)
        nxt = _core(out[j]) if j is not None else ""
        c = _core(t)
        if not m and ONES.get(c, 99) <= 10 and nxt in PERCENT | DOLLARS and not _tail(t):
            m = NUM.match(str(ONES[c]))                     # "seven percent", "five dollars"
        if not m or _core(m.group(3)) in skip:
            continue
        lead, cur, num, pct, tail = m.groups()
        if not tail and not pct and nxt in PERCENT:
            pct, tail, out[j] = "%", _tail(out[j]), ""
        elif not tail and not cur and nxt in DOLLARS:
            cur, tail, out[j] = "$", _tail(out[j]), ""
        elif not tail and not cur and nxt in ("million", "billion", "trillion"):
            k = _next(out, j)
            if k is not None and _core(out[k]) in DOLLARS and not _tail(out[j]):
                cur, out[j], out[k] = "$", out[j] + _tail(out[k]), ""
        out[i] = lead + cur + num + pct + tail
    sent, sid = [], 0
    for t in out:
        sent.append(sid)
        if t and ends_sentence(t):
            sid += 1
    money = {s for t, s in zip(out, sent) if t and ("$" in t or _core(t) in MONEY_TALK)}
    for i, t in enumerate(out):
        m = NUM.match(t) if t else None
        if not m or m.group(2) or m.group(4) or _core(m.group(3)) in skip:
            continue
        lead, _, num, _, tail = m.groups()
        j = _next(out, i)
        nxt = _core(out[j]) if j is not None else ""
        k = _next(out, j) if j is not None else None
        if "." in num:
            if talk_rates and 1 <= float(num.replace(",", "")) < 20 and (tail or nxt not in NOT_A_RATE):
                out[i] = lead + num + "%" + tail
        elif not tail and nxt in ("a", "per") and k is not None and _core(out[k]) in ("month", "year") \
                and sent[i] in money:
            out[i] = lead + "$" + num
    return out


def shown(tokens, skip=()):
    """The words as a caption writes them: numbers as numerals, rates with %, money with $. A token can hold several
    words (a script's 'seven point four zero percent.' shown on the one word they said as '7.4%'): those are written
    the same way inside the token."""
    one = lambda ts: figures(numerals(decimals(ts)), skip)
    return one([" ".join(x for x in one(t.split()) if x) if " " in t else t for t in tokens])


# ---------- the word a call to action asks for ----------

ASK_PLAIN = {"comment", "dm"}                     # "comment RATES", "DM me RATES"
ASK = ASK_PLAIN | {"type", "drop", "text", "reply", "message", "send", "put", "leave", "write", "say"}
NOT_A_KEYWORD = {"below", "down", "me", "us", "your", "my", "our", "a", "an", "the", "this", "that", "it", "if", "and",
                 "or", "to", "on", "in", "here", "now", "today", "tomorrow", "anytime", "anything", "something",
                 "what", "which", "how", "why", "when", "where", "who", "questions", "question", "back", "with",
                 "for", "any", "some", "you", "i", "we", "section", "sections", "there", "them", "one", "more",
                 "directly", "first", "about", "so", "is", "was", "comment", "comments", "word", "keyword"}
AFTER_A_KEYWORD = {"and", "below", "down", "in", "to", "for", "so", "if", "or", "then", "i'll", "we'll", "right"}


def keyword(tokens, skip=()):
    """Indexes of the word a call to action asks people to send: 'comment RATES', 'DM me the word rates',
    'type rates below'. It is written in capitals and bold, so it reads as the thing to type."""
    live = [i for i, t in enumerate(tokens) if t]
    n = [_core(tokens[i]) for i in live]
    at = lambda q: n[q] if 0 <= q < len(n) else ""
    hits = set()
    for k in range(len(n)):
        if n[k] not in ASK or at(k - 1) in ("a", "the", "your", "my", "that", "this", "one", "no"):
            continue
        j, named = k + 1, False
        if at(j) in ("me", "us"):
            j += 1
        if at(j) in ("below", "down"):
            j += 1
        if at(j) in ("the", "a", "this", "that") and at(j + 1) in ("word", "keyword", "code"):
            j, named = j + 2, True
        elif at(j) in ("word", "keyword"):
            j, named = j + 1, True
        c = at(j)
        if len(c) < 2 or c in skip or c in NOT_A_KEYWORD or not re.search(r"[a-z]", c) \
                or any(ends_sentence(tokens[live[x]]) for x in range(k, min(j, len(live)))):
            continue
        end = j + 1 >= len(n) or bool(_tail(tokens[live[j]]))
        if named:
            hits.add(live[j])
        elif n[k] in ASK_PLAIN and (end or at(j + 1) in AFTER_A_KEYWORD):
            hits.add(live[j])
        elif at(j + 1) in ("below", "down") or (at(j + 1) == "in" and "comment" in at(j + 2) + at(j + 3)):
            hits.add(live[j])
    return hits


def mark_keyword(t):
    """rates, -> **RATES**,"""
    m = re.match(r"^([\"“(]*)(.*?)(" + EDGE + r")$", t.replace("**", ""))
    return f"{m.group(1)}**{m.group(2).upper()}**{m.group(3)}"


def clean_token(t):
    t = t.replace("'", "’") if "'" in t else t
    t = re.sub(r"(?i)\brealtor", lambda m: "R" + m.group(0)[1:], t)
    return t


def draft(played, lk):
    """A first chunking: one line per caption, by width and the break rules. Claude reads and fixes it."""
    C = lk["captions"]
    toks = shown([p["w"] for p in played])
    for i in keyword(toks):
        toks[i] = mark_keyword(toks[i])
    toks = [clean_token(t) for t in toks if t]
    f = font(C["font"], C["size"], C.get("weight", 700))
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    maxw, maxn = C["max_width"], C.get("max_words", 5)
    sents, cur = [], []
    for t in toks:                                  # never across a sentence end
        cur.append(t)
        if ends_sentence(t):
            sents.append(cur)
            cur = []
    if cur:
        sents.append(cur)
    lines = []
    for s in sents:
        s[0] = re.sub(r"[a-z]", lambda m: m.group(0).upper(), s[0], count=1) if re.match(r"^[\"“(*]*[a-z]", s[0]) else s[0]
        lines += _split(s, lambda ws: d.textlength(strip(" ".join(ws)).replace("**", ""), font=f), maxw, maxn)
    return [strip(" ".join(l)) for l in lines if l]


BREAK_BEFORE = {"and", "but", "so", "or", "because", "when", "if", "that", "which", "who", "to", "for", "with",
                "from", "in", "on", "at", "before", "after", "than", "like", "as", "then", "while", "until"}


def _split(ws, width, maxw, maxn):
    """Best line breaks for one sentence (dynamic programming): every line fits; ending on a small word, a one-word
    line and a split mid-phrase cost; a break after a comma or before a joining word is cheap."""
    n = len(ws)
    INF = float("inf")
    best = [0.0] + [INF] * n
    prev = [0] * (n + 1)
    for j in range(1, n + 1):
        for i in range(max(0, j - maxn), j):
            line = ws[i:j]
            w = width(line)
            if w > maxw and j - i > 1:
                continue
            c = ((maxw - w) / maxw) ** 2 * 2            # prefer fuller lines, gently
            last = norm(line[-1])
            if j < n:
                if last in SMALL:
                    c += 6                              # never end on a dangling small word
                if line[-1].endswith((",", ":", ";")):
                    c -= 1.2
                elif norm(ws[j]) in BREAK_BEFORE:
                    c -= 0.6
                else:
                    c += 0.8
            if j - i == 1 and n > 1:
                c += 3                                  # a lonely word
            if best[i] + c < best[j]:
                best[j], prev[j] = best[i] + c, i
    out, j = [], n
    while j > 0:
        out.append(ws[prev[j]:j])
        j = prev[j]
    return out[::-1]


def strip(text):
    """No periods (an ellipsis or a decimal stays), no trailing commas/colons/semicolons; '?' and '!' stay."""
    text = re.sub(r"(?<!\.)\.(?!\.)(?!\d)", "", text)
    return re.sub(r"[,;:]+(\**)$", r"\1", text.strip()).strip()


def parse(path):
    return [ln.strip() for ln in Path(path).read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]


def parse_ok(path):
    """Words the member wants left exactly as written: a line `#ok 7.11 questions` in captions.txt. The % / $ check
    and the comment-word check skip them."""
    out = set()
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#\s*ok\b[:\s]*(.*)$", ln.strip(), re.I)
        if m:
            out |= {_core(t) for t in m.group(1).split() if _core(t)}
    return out


def figure_problems(lines, ok=()):
    """A rate without %, money without $ or spelled out, and a comment word that is not in bold capitals."""
    raw = [(ln, t) for ln, text in enumerate(lines, 1) for t in text.split()]
    bare = [t.replace("**", "") for _, t in raw]
    fixed = figures(decimals(bare), ok)
    out, said = [], set()
    for (ln, _), b, f in zip(raw, bare, fixed):
        if b != f and ln not in said:
            said.add(ln)
            new = " ".join(x for (l2, _), x in zip(raw, fixed) if l2 == ln and x)
            out.append(f"line {ln}: a rate takes %, money takes $, neither is spelled out: write \"{new}\" "
                       f"(or list the number after `#ok` in captions.txt if it is neither)")
    for i in sorted(keyword(bare, ok)):
        ln, t = raw[i]
        core = re.sub(r"[^A-Za-z0-9]", "", bare[i])
        if "**" not in t or core != core.upper():
            out.append(f"line {ln}: '{core}' is the word they are asked to send: write it in bold capitals, "
                       f"{mark_keyword(bare[i])} (or list it after `#ok` if it is not)")
    return out


def build(lines, played, lk, ok=()):
    """Match every caption line to the played words in order; time it; check the rules. Returns (captions, problems)."""
    C = lk["captions"]
    f_reg = font(C["font"], C["size"], C.get("weight", 700))
    f_bold = font(C["font"], C["size"], C.get("bold_weight", 900))
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    disp = shown([p["w"] for p in played], ok)
    stream = []                         # (token-norm, first played index, last played index) per shown token
    for k, t in enumerate(disp):
        if not t:
            continue
        k_end = k
        while k_end + 1 < len(disp) and disp[k_end + 1] == "":      # words merged into a numeral or a script word
            k_end += 1
        for piece in t.split():
            stream.append((piece, k, k_end))
    # Align the caption words with the spoken stream as two sequences (hyphenated words split on both sides), so a
    # joined or split word ("buy-downs" / "buy downs"), a merged numeral or a corrected mishear never shifts the rest.
    same = lambda s: norm(s).replace("$", "").replace("%", "")      # "$79" and "79", "7.11%" and "7.11": one word
    sub = lambda s: [x for x in re.split(r"[-–—]", s) if same(x)]
    S = [(same(x), k0, k1) for t, k0, k1 in stream for x in (sub(t) or [t])]
    Cl, owner = [], []                              # caption sub-tokens and the line each belongs to
    for ln, text in enumerate(lines):
        for t in re.sub(r"\*\*", "", text).split():
            for x in sub(t):
                Cl.append(same(x))
                owner.append(ln)
    sm = SequenceMatcher(None, Cl, [s[0] for s in S], autojunk=False)
    hit = [[] for _ in lines]                       # stream positions each line covers
    problems, caps = [], []
    for tag, a0, a1, b0, b1 in sm.get_opcodes():
        if tag == "equal":
            for k in range(a1 - a0):
                hit[owner[a0 + k]].append(b0 + k)
        elif tag == "replace":
            for k in range(a1 - a0):                # spread the replaced span over the caption words
                hit[owner[a0 + k]].append(b0 + min(b1 - b0 - 1, k * (b1 - b0) // max(1, a1 - a0)))
            heardtxt = " ".join(played[S[b][1]]["heard"] for b in range(b0, b1))
            problems.append(f"line {owner[a0] + 1}: '{' '.join(Cl[a0:a1])}' shown for the heard '{heardtxt}' "
                            f"(fine if that is the fix)")
        elif tag == "delete":                       # caption words nobody said
            problems.append(f"line {owner[a0] + 1}: '{' '.join(Cl[a0:a1])}' is not in the audio")
        elif tag == "insert":                       # spoken words with no caption
            said = " ".join(played[S[b][1]]["w"] for b in range(b0, b1))
            problems.append(f"no caption for the spoken words: {said}")
    for i, text in enumerate(lines):
        ln = i + 1
        if not hit[i]:
            problems.append(f"line {ln}: matches no spoken words: {text}")
            continue
        last_k = S[max(hit[i])][1]
        caps.append({"text": text, "start": played[S[min(hit[i])][1]]["start"], "end": played[S[max(hit[i])][2]]["end"]})
        bare = re.sub(r"\*\*", "", text)
        if re.search(r"(?<!\.)\.(?!\.)(?!\d)", bare):
            problems.append(f"line {ln}: has a period (house rule: none): {text}")
        if bare.endswith("-"):
            problems.append(f"line {ln}: ends on a hyphen: {text}")
        last = norm(bare.split()[-1]) if bare.split() else ""
        if last in SMALL and ln < len(lines) and not ends_sentence(disp[last_k]):
            problems.append(f"line {ln}: ends on the small word '{last}': carry it to the next line")
        first_k = S[min(hit[i])][1]
        if any(ends_sentence(w) for w in bare.split()[:-1]) or \
                any(ends_sentence(disp[k]) for k in range(first_k, last_k) if disp[k]):
            problems.append(f"line {ln}: crosses a sentence end: {text}")
        if re.search(r"\brealtor", bare):
            problems.append(f"line {ln}: 'Realtor' takes a capital R")
        for t in bare.split():
            core = re.sub(r"[^a-z\-]", "", t.lower())
            if core and all(p in TENS or p in ("hundred", "thousand") for p in core.split("-") if p) \
                    and any(p in TENS for p in core.split("-")):
                problems.append(f"line {ln}: '{t}' should be a numeral")
        wpx = sum(d.textlength(seg[2:-2] if seg.startswith("**") else seg, font=f_bold if seg.startswith("**") else f_reg)
                  for seg in re.split(r"(\*\*.+?\*\*)", text) if seg)
        if wpx > C["max_width"]:
            problems.append(f"line {ln}: too wide for one line ({wpx:.0f} > {C['max_width']} px): split it: {text}")
    problems += figure_problems(lines, ok)
    for k in range(len(caps)):         # start 1 frame before the word; hold to the next caption across short gaps
        caps[k]["start"] = max(0.0, round(caps[k]["start"] - 1 / FPS, 3))
    for k in range(len(caps)):
        nxt = caps[k + 1]["start"] if k + 1 < len(caps) else None
        caps[k]["end"] = round(nxt if nxt is not None and nxt - caps[k]["end"] < 0.6 else caps[k]["end"] + 0.25, 3)
    hard = [p for p in problems if "fine if that is the fix" not in p]
    return caps, problems, hard


def draw(text, C):
    """One caption as an RGBA image (cropped) plus its top-left position on the frame."""
    f_reg = font(C["font"], C["size"], C.get("weight", 700))
    f_bold = font(C["font"], C["size"], C.get("bold_weight", 900))
    parts = [(seg[2:-2], f_bold) if seg.startswith("**") else (seg, f_reg) for seg in re.split(r"(\*\*.+?\*\*)", text) if seg]
    img = Image.new("RGBA", (W, 400), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W, 400), (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(img), ImageDraw.Draw(sh)
    tw = sum(d.textlength(p, font=f) for p, f in parts)
    x = (W - tw) / 2
    asc = f_reg.getmetrics()[0]
    y = 200 - (asc + f_reg.getmetrics()[1]) / 2
    s = C["size"]
    edge = max(0, round(s * C.get("edge_w", 0.06)))
    S = C.get("shadow")
    ink = tuple(C.get("edge", (0, 0, 0, 255)))
    for p, f in parts:
        # bold must READ as bold at phone size, and one weight step does not (and a serif has no heavier cut): the
        # bold words are also drawn a touch fatter
        fat = max(1, round(s * C.get("bold_fat", 0.02))) if f is f_bold else 0
        if S:
            ds.text((x, y + s * S.get("dy", 0.05)), p, font=f, fill=tuple(S["color"]),
                    stroke_width=edge + fat + round(s * S.get("spread", 0.03)), stroke_fill=tuple(S["color"]))
        if fat:
            d.text((x, y), p, font=f, fill=ink, stroke_width=edge + fat, stroke_fill=ink)
            d.text((x, y), p, font=f, fill=tuple(C["fill"]), stroke_width=fat, stroke_fill=tuple(C["fill"]))
        else:
            d.text((x, y), p, font=f, fill=tuple(C["fill"]), stroke_width=edge, stroke_fill=ink)
        x += d.textlength(p, font=f)
    if S:
        sh = sh.filter(ImageFilter.GaussianBlur(s * S.get("blur", 0.05)))
    sh.alpha_composite(img)
    bb = sh.getbbox() or (0, 0, 1, 1)
    out = sh.crop(bb)
    return np.array(out), bb[0], int(C["center_y"] - 200 + bb[1])


def images(caps, lk):
    C = lk["captions"]
    out = []
    cache = {}
    for c in caps:
        if c["text"] not in cache:
            cache[c["text"]] = draw(c["text"], C)
        img, x, y = cache[c["text"]]
        out.append({"start": c["start"], "end": c["end"], "img": img, "x": x, "y": y, "text": c["text"]})
    return out
