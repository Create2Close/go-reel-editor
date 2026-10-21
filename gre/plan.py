"""The first cut, proposed: which words stay (keep.json). Claude reviews and edits it before `gre yap cut`.

Two ways in:
  * SCRIPTED (a script file sits in the folder): every script sentence is found in the transcript and its LAST
    complete take is kept; stumbles and restarts inside that take go; the script's own words become the caption text
    (the transcript only times them). Lines the speaker never said are reported.
  * UNSCRIPTED: everything is kept except fillers (um, uh), restarts (a phrase begun and begun again: the last one
    wins) and repeated sentences (the last complete one wins). Claude then makes the judgement cuts from the rules.

keep.json = {"mode": "scripted"|"unscripted", "segments": [{"from": W#, "to": W#}, ...]  (playback order),
             "cuts": [{"from": W#, "to": W#, "why": "retake"}, ...], "display": {"W#": "script word"}, "notes": [...]}"""
import json, re
from difflib import SequenceMatcher
from pathlib import Path
from .words import FILLERS, norm, ends_sentence

SCRIPT_NAMES = ("script.txt", "script.md", "Script.txt", "Script.md")


def find_script(folder):
    folder = Path(folder)
    for n in SCRIPT_NAMES:
        if (folder / n).exists():
            return folder / n
    cands = [p for p in folder.glob("*.txt") if "script" in p.stem.lower()] + \
            [p for p in folder.glob("*.md") if "script" in p.stem.lower()]
    return cands[0] if cands else None


def script_sentences(text):
    """Spoken lines only: headings, labels and stage directions ([...], (...), 'HOOK:', '#', '---') are dropped."""
    out = []
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln or ln.startswith(("#", "---", "===", "*", ">")) and not re.match(r"^\*\*?[A-Za-z]", ln):
            continue
        ln = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", ln)            # stage directions
        ln = re.sub(r"^\s*[-•]\s*", "", ln)
        ln = re.sub(r"^\s*(\*\*)?[A-Z0-9 &/]{2,30}(\*\*)?\s*[:—-]\s*", "", ln)   # "HOOK:", "PILLAR 1 —"
        ln = ln.replace("**", "").replace("__", "").strip()
        if not ln or not re.search(r"[A-Za-z0-9]", ln):
            continue
        for s in re.split(r"(?<=[.?!])\s+", ln):
            s = re.sub(r"\s+", " ", s).strip()
            if s:
                out.append(s)
    return out


def _restart_of(run, after):
    """True when an inserted run is a false start of what follows (its words begin the next matched words)."""
    if not run or not after:
        return False
    k = min(len(run), len(after))
    return [norm(x) for x in run[-k:]] == [norm(x) for x in after[:k]] or norm(run[0]) == norm(after[0])


def plan_scripted(flat, sentences):
    T = [norm(w["w"]) for w in flat]
    keep_idx, display, notes, chosen = [], {}, [], []
    for si, sent in enumerate(sentences):
        toks = sent.split()
        S = [norm(t) for t in toks]
        S_ok = [x for x in S if x]
        if not S_ok:
            continue
        n = len(S)
        # a take starts on the line's first word, or on its second when the first was swallowed or misheard
        # (but never on the second word of a take that did start on the first: that is the same take)
        starts = [i for i, t in enumerate(T) if t and (t == S[0] or (n > 1 and t == S[1] and (i == 0 or T[i - 1] != S[0])))]
        takes = []
        for i in starts:
            win = T[i:i + int(n * 1.6) + 4]
            sm = SequenceMatcher(None, S, win, autojunk=False)
            blocks = [b for b in sm.get_matching_blocks() if b.size]
            m = sum(b.size for b in blocks)
            if not blocks:
                continue
            last_s = blocks[-1].a + blocks[-1].size
            score = m / n
            complete = score >= 0.75 and last_s >= n - 1
            takes.append((i, score, complete, sm, win))
        if not takes:
            notes.append(f"line {si + 1} was not found in the recording: \"{sent}\"")
            continue
        good = [t for t in takes if t[2]]
        i, score, complete, sm, win = (good[-1] if good else max(takes, key=lambda t: t[1]))
        if not complete:
            notes.append(f"line {si + 1} has no complete take (best {score:.0%}): \"{sent}\" (check it by ear)")
        if len(good) > 1:
            notes.append(f"line {si + 1}: {len(good)} takes found, kept the last one (W{i})")
        ops = sm.get_opcodes()
        last_b = max((b.b + b.size for b in sm.get_matching_blocks() if b.size), default=0)
        kept = []
        pend_script = []                                  # script words with no transcript word yet
        for tag, a0, a1, b0, b1 in ops:
            if b0 >= last_b and tag in ("insert", "replace") and b1 > last_b:
                b1 = last_b
            if tag == "equal" or (tag == "replace" and b1 > b0):
                for k in range(b1 - b0):
                    gi = i + b0 + k
                    kept.append(gi)
                    if tag == "replace":
                        # more heard words than script words ("four hundred thousand" for "400,000"): the script
                        # word sits on the first, the rest show nothing; fewer: the last heard word carries the rest
                        display[gi] = toks[a0 + k] if a0 + k < a1 else ""
                        if k == b1 - b0 - 1 and a1 - a0 > b1 - b0:
                            display[gi] = " ".join([display[gi]] + toks[a0 + k + 1:a1])
                    else:
                        display[gi] = toks[a0 + k]
                    if pend_script:
                        display[gi] = " ".join(pend_script + [display[gi]])
                        pend_script = []
            elif tag == "delete":                          # said in the script, not heard: shown on the next word
                pend_script += toks[a0:a1]
            elif tag == "insert":
                run = [flat[i + b]["w"] for b in range(b0, b1)]
                after = [flat[i + b]["w"] for b in range(b1, min(b1 + len(run) + 1, len(win)))]
                if all(norm(x) in FILLERS for x in run) or _restart_of(run, after):
                    continue                               # a stumble or a filler inside the take
                for b in range(b0, b1):                    # an ad-lib: kept, said as said
                    kept.append(i + b)
                notes.append(f"line {si + 1}: kept words not in the script: \"{' '.join(run)}\"")
        if pend_script and kept:
            display[kept[-1]] = display.get(kept[-1], flat[kept[-1]]["w"]) + " " + " ".join(pend_script)
        if kept:
            chosen.append((si, kept))
            keep_idx += kept
    return chosen, display, notes


def ranges(idx):
    out = []
    for i in idx:
        if out and i == out[-1][1] + 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return out


def plan_unscripted(flat):
    n = len(flat)
    drop = {}
    T = [norm(w["w"]) for w in flat]
    for i, t in enumerate(T):
        if t in FILLERS:
            drop[i] = "filler"
    same_clip = lambda a, b: flat[a]["ci"] == flat[b]["ci"]
    # 1. restarts and stutters inside a sentence: a phrase said, (up to 3 abandoned words,) then said again
    #    ("Owning a home here in, Owning a home here in Texas"; "the the"). The first attempt goes.
    for i in range(n):
        if i in drop:
            continue
        for k in (6, 5, 4, 3, 2, 1):
            hit = None
            for g in ((0,) if k == 1 else range(0, 4 if k >= 3 else 3)):
                j = i + k + g
                if j + k > n or not same_clip(i, j + k - 1):
                    continue
                if T[i:i + k] == T[j:j + k] and all(T[i:i + k]) and not any(x in FILLERS for x in T[i:i + k]):
                    if k == 1 and T[i] in ("that", "had", "is", "very", "really", "no", "so"):
                        continue
                    if any(ends_sentence(flat[x]["w"]) for x in range(i, j)):
                        continue                      # a finished sentence is not a restart (see 2.)
                    hit = j
                    break
            if hit is not None:
                for x in range(i, hit):
                    drop.setdefault(x, "restart")
                break
    # 2. a sentence said again: the next 1-3 sentences include one that starts with the same 3 words, or reads
    #    at least 70 % the same. Everything from the first attempt up to the last attempt goes.
    sents, cur = [], []
    for i in range(n):
        cur.append(i)
        if ends_sentence(flat[i]["w"]) or i == n - 1 or not same_clip(i, min(i + 1, n - 1)) or \
                (i + 1 < n and flat[i + 1]["start"] - flat[i]["end"] >= 1.2):
            sents.append(cur)
            cur = []
    toks = [[T[x] for x in s if T[x] and T[x] not in FILLERS] for s in sents]
    for a in range(len(sents)):
        if len(toks[a]) < 3:
            continue
        for b in range(a + 1, min(len(sents), a + 4)):
            if not same_clip(sents[a][0], sents[b][0]) or len(toks[b]) < 3:
                continue
            same_start = toks[a][:3] == toks[b][:3]
            ratio = SequenceMatcher(None, toks[a], toks[b], autojunk=False).ratio()
            if same_start or ratio >= 0.7:
                for s in sents[a:b]:
                    for x in s:
                        drop.setdefault(x, "retake (the last take wins)")
                break
    keep = [i for i in range(n) if i not in drop]
    cuts = []
    for a, b in ranges(sorted(drop)):
        cuts.append({"from": a, "to": b, "why": drop[a]})
    return keep, cuts


def make_plan(flat, script_path=None):
    if script_path:
        sents = script_sentences(Path(script_path).read_text(encoding="utf-8", errors="replace"))
        chosen, display, notes = plan_scripted(flat, sents)
        found = len(chosen) / max(1, len(sents))
        if found >= 0.6:
            segs = []
            for _, kept in chosen:
                for a, b in ranges(sorted(set(kept))):
                    if segs and segs[-1]["to"] + 1 == a and flat[a]["ci"] == flat[segs[-1]["to"]]["ci"]:
                        segs[-1]["to"] = b
                    else:
                        segs.append({"from": a, "to": b})
            kept_all = {i for s in segs for i in range(s["from"], s["to"] + 1)}
            cuts = [{"from": a, "to": b, "why": "not the kept take"} for a, b in
                    ranges([i for i in range(len(flat)) if i not in kept_all])]
            return {"mode": "scripted", "script": str(script_path), "segments": segs, "cuts": cuts,
                    "display": {str(k): v for k, v in display.items()},
                    "notes": [f"{len(chosen)} of {len(sents)} script lines found"] + notes}
        note = (f"a script was found but only {found:.0%} of its lines match the recording (an outline, or a "
                f"different video?): cut as UNSCRIPTED instead")
    else:
        note = "no script file: cut as UNSCRIPTED (put the script in the folder as script.txt for exact captions)"
    keep, cuts = plan_unscripted(flat)
    segs = [{"from": a, "to": b} for a, b in ranges(keep)]
    merged = []
    for s in segs:                                     # drop-gaps of one filler are re-split later by cut.py anyway
        merged.append(s)
    return {"mode": "unscripted", "segments": merged, "cuts": cuts, "display": {}, "notes": [note]}
