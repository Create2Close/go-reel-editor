"""Runs INSIDE the transcriber's environment (not the gre one). argv: out.json model clip [clip ...]

How it listens (0.2.1). Raw takes are the hardest thing to transcribe: the same line three times, a wrong number, a
restart. Left alone, Whisper tidies that up (it drops the first two takes, or folds them into one), and every word
after it is then timed against the wrong sound. So the SOUND decides what is transcribed, not Whisper:

  1. the waveform is cut into utterances (hear.py: stretches of sound with under 0.6 s of silence inside);
  2. every utterance is decoded on its own, asked for every word as said. A word can only be timed inside the
     utterance it was said in, and a second take is its own utterance, so it cannot vanish;
  3. an utterance with far fewer words than its sound can hold is decoded a second way, and the fuller answer wins;
  4. the word edges are measured by a forced aligner inside the utterance (numerals keep Whisper's own times);
  5. sound that still has no words is written down (`sounds`), so the cut never plays it by accident.

Listening back to a finished cut works the same way, with one change: a tight cut has no silences left to split on,
so the editor says where its own joints are ($GRE_HEAR_AT: a JSON file, {clip name: [[start, end], ...]}) and those
are the utterances. Short pieces keep Whisper from tidying a long run of speech, which is the one thing a listen-back
must not do.

Device ladder: an NVIDIA GPU when one works (float16, then int8_float16), else CPU int8 (always works; Apple Silicon
uses CPU: MPS is still unreliable for these models)."""
import json, os, re, sys

out_path, model_name, clips = sys.argv[1], sys.argv[2], sys.argv[3:]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hear  # noqa: E402  (numpy only: the waveform side)
import logging, warnings  # noqa: E402
warnings.filterwarnings("ignore")                  # torchcodec/lightning chatter: harmless, and it scares members
for name in ("whisperx", "lightning", "lightning_fabric", "pytorch_lightning", "pyannote", "speechbrain",
             "faster_whisper"):
    logging.getLogger(name).setLevel(logging.ERROR)
import numpy as np  # noqa: E402
import whisperx  # noqa: E402
from faster_whisper import WhisperModel, BatchedInferencePipeline  # noqa: E402

SR = hear.SR
# Whisper writes the way its prompt is written. This one stumbles on purpose, so restarts and fillers are written
# down instead of tidied away, and it writes a rate with % and money with $.
PROMPT = ("Um, okay, so, uh, the rate, the rate was at, was at 6.5%, and that's, that's like $50 a month. "
          "Let me, let me do that again.")
DECODE = dict(language="en", beam_size=5, word_timestamps=True, condition_on_previous_text=False, vad_filter=False,
              initial_prompt=PROMPT, temperature=[0.0, 0.2, 0.4])
NO_SPEECH = 0.6                                    # above this Whisper is guessing words into a noise ("Thank you.")
AT = json.load(open(os.environ["GRE_HEAR_AT"], encoding="utf-8")) if os.environ.get("GRE_HEAR_AT") else {}


def say(msg):
    print(f"[transcribe] {msg}", file=sys.stderr, flush=True)


tiers = [("cpu", "int8", 8)]
try:
    import torch
    if torch.cuda.is_available():
        if os.name == "nt":                     # ctranslate2 finds cuDNN/cuBLAS in torch/lib on Windows
            lib = os.path.join(os.path.dirname(torch.__file__), "lib")
            if os.path.isdir(lib):
                os.add_dll_directory(lib)
                os.environ["PATH"] = lib + os.pathsep + os.environ.get("PATH", "")
        tiers = [("cuda", "float16", 16), ("cuda", "int8_float16", 16)] + tiers
except Exception:
    pass


def load(device, ct):
    say(f"loading Whisper {model_name} ({device}, {ct})")
    asr = WhisperModel(model_name, device=device, compute_type=ct,
                       cpu_threads=max(4, min(8, (os.cpu_count() or 4) - 2)))
    say("loading the word aligner")
    al, meta = whisperx.load_align_model(language_code="en", device=device)
    return asr, al, meta


for i, (device, ct, bs) in enumerate(tiers):
    try:
        asr, al, meta = load(device, ct)
        break
    except Exception as e:
        if i == len(tiers) - 1:
            raise
        say(f"{device}/{ct} failed ({e}); trying the next option")
batched = BatchedInferencePipeline(asr)


def words_of(seg, shift=0.0):
    """Whisper's word list, with a word it split back in one piece ('7' + '.11%' -> '7.11%', '$400' + ',000',
    '30' + '-year'): a piece with no space in front of it belongs to the word before."""
    out = []
    for w in seg.words or []:
        raw = w.word
        if out and raw and not raw[0].isspace() and re.match(r"^[.,\-–]\w", raw):
            out[-1]["w"] += raw.strip()
            out[-1]["end"] = round(float(w.end) + shift, 3)
            continue
        if raw.strip():
            out.append({"w": raw.strip(), "start": round(float(w.start) + shift, 3),
                        "end": round(float(w.end) + shift, 3), "prob": round(float(w.probability), 3)})
    return out


def decode_all(audio, utts):
    """Every utterance on its own, in batches. -> one {"words", "nsp"} per utterance."""
    res = [{"words": [], "nsp": 1.0} for _ in utts]
    if not utts:
        return res
    segs, _ = batched.transcribe(audio, clip_timestamps=[{"start": a, "end": b} for a, b in utts], batch_size=bs,
                                 without_timestamps=True, **DECODE)
    mids = [(a + b) / 2 for a, b in utts]
    for s in segs:
        k = int(np.argmin([abs((s.start + s.end) / 2 - m) for m in mids]))
        if not (utts[k][0] - 0.5 <= (s.start + s.end) / 2 <= utts[k][1] + 0.5):
            continue
        res[k]["words"] += words_of(s)
        res[k]["nsp"] = min(res[k]["nsp"], float(s.no_speech_prob))
    return res


def decode_one(audio, a, b, **change):
    """One utterance the slow way (Whisper reads it start to end with timestamps): the second opinion."""
    segs, _ = asr.transcribe(audio[int(a * SR):int(b * SR)], **dict(DECODE, **change))
    out = {"words": [], "nsp": 1.0}
    for s in segs:
        out["words"] += words_of(s, a)
        out["nsp"] = min(out["nsp"], float(s.no_speech_prob))
    return out


def said(words):
    return sum(hear.spoken(w["w"]) for w in words)


def refine(audio, a, b, words, env=None, thr=None):
    """Word edges from the forced aligner, inside the utterance. Figures are aligned as they are said ('7.4%' as
    'seven point four percent'), so a number gets its whole length and the words around it their real places. A word
    the aligner cannot place, or places far from where Whisper heard it, keeps Whisper's time."""
    if not words:
        return words
    said = [hear.spell(w["w"]).split() or [w["w"]] for w in words]
    try:
        r = whisperx.align([{"start": a, "end": b, "text": " ".join(t for ts in said for t in ts)}], al, meta, audio,
                           device, return_char_alignments=False)
        got = [w for s in r.get("segments", []) for w in s.get("words", [])]
    except Exception:
        return words
    if len(got) != sum(len(ts) for ts in said):
        return words
    k = 0
    for w, ts in zip(words, said):
        mine, k = [g for g in got[k:k + len(ts)] if "start" in g and "end" in g], k + len(ts)
        if not mine:
            continue
        g0, g1 = float(mine[0]["start"]), float(mine[-1]["end"])
        if a - 0.05 <= g0 < g1 <= b + 0.05 and abs(g0 - w["start"]) < (0.5 if len(ts) == 1 else 1.0):
            w["start"], w["end"] = round(g0, 3), round(g1, 3)
            w["prob"] = round(min(float(g.get("score", w["prob"])) for g in mine), 3)
    for p, w in zip(words, words[1:]):              # in order, never overlapping
        if w["start"] < p["end"]:
            mid = round((p["end"] + max(w["start"], p["start"])) / 2, 3)
            p["end"], w["start"] = mid, mid
        w["end"] = max(w["end"], w["start"] + 0.02)
    return hear.settle(words, env, thr) if env is not None else words


def listen(path):
    audio = whisperx.load_audio(path)
    env = hear.envelope(audio)
    thr = hear.threshold(env)
    given = AT.get(os.path.basename(path))
    utts = hear.fit([tuple(u) for u in given] if given else hear.utterances(hear.islands(env, thr)), env)
    end = len(audio) / SR                               # never past the last sample (a cut is whole frames long)
    utts = [(max(0.0, a), min(b, end)) for a, b in utts if min(b, end) - max(0.0, a) > 0.05]
    say(f"{os.path.basename(path)}: {len(audio) / SR:.0f} s, {len(utts)} stretches of speech")
    res = decode_all(audio, utts)
    level = hear.speech_level(env, thr)
    # 3. the second opinion, where the words do not fill the sound: far fewer words than the sound can hold, or
    #    speech and no words at all (the batch decoder now and then returns nothing for a short piece)
    rate = [said(r["words"]) / max(0.3, hear.sound(env, a, b, thr)) for r, (a, b) in zip(res, utts)]
    usual = float(np.median([x for x, r in zip(rate, res) if len(r["words"]) >= 3] or [3.0]))
    again = [k for k, ((a, b), r) in enumerate(zip(utts, res))
             if (r["nsp"] <= NO_SPEECH and r["words"] and hear.sound(env, a, b, thr) >= 1.5 and rate[k] < 0.6 * usual)
             or ((r["nsp"] > NO_SPEECH or not r["words"]) and hear.sound(env, a, b, level) >= 0.6)]
    for k in again:
        a, b = utts[k]
        alt = decode_one(audio, a, b)
        if alt["nsp"] <= NO_SPEECH and said(alt["words"]) > (said(res[k]["words"]) if res[k]["nsp"] <= NO_SPEECH else 0) \
                and said(alt["words"]) / max(0.3, hear.sound(env, a, b, thr)) <= 6.5:
            res[k] = alt
    # a short noise (a breath, a chair) can come back as a word or two because the prompt invites them: ask again
    # with no prompt, and believe Whisper when it then says there is no speech
    for k, ((a, b), r) in enumerate(zip(utts, res)):
        if given:
            break                                       # a cut's own pieces are speech: nothing to ask twice
        if r["words"] and len(r["words"]) <= 3 and r["nsp"] <= NO_SPEECH and hear.sound(env, a, b, thr) < 1.5:
            r["nsp"] = max(r["nsp"], decode_one(audio, a, b, initial_prompt=None)["nsp"])
    words, sounds, twice = [], [], len(again)
    for k, ((a, b), r) in enumerate(zip(utts, res)):
        if r["nsp"] > NO_SPEECH or not r["words"]:
            sounds.append([round(a, 2), round(b, 2)])
            continue
        mine = refine(audio, a, b, r["words"], env, thr)
        # 3b. once the words are timed: a stretch of speech that no word covers ("...when it's time to hire" and the
        #     sound runs on: "an accountant" was left off). Read the utterance the slow way, and take that reading
        #     when it puts words there.
        bare = hear.uncovered(env, level, a, b, mine)
        if bare and k not in again:
            twice += 1
            alt = decode_one(audio, a, b)
            if alt["nsp"] <= NO_SPEECH and alt["words"]:
                theirs = refine(audio, a, b, alt["words"], env, thr)
                left = hear.uncovered(env, level, a, b, theirs)
                if sum(y - x for x, y in left) < sum(y - x for x, y in bare) and said(theirs) >= said(mine):
                    mine, bare = theirs, left
        sounds += [[round(x, 2), round(y, 2)] for x, y in bare if y - x >= 0.5]
        for w in mine:
            w["start"], w["end"] = max(round(a, 3), w["start"]), min(round(b, 3), max(w["end"], w["start"] + 0.02))
            words.append(dict(w, u=k))
    if twice:
        say(f"listened twice to {twice} of them (more sound than words)")
    return {"clip": os.path.basename(path), "path": os.path.abspath(path), "duration": round(len(audio) / SR, 3),
            "words": words, "sounds": sounds, "utterances": [[round(a, 2), round(b, 2)] for a, b in utts]}


result = {"heard": 2, "clips": [listen(p) for p in clips]}
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=1, ensure_ascii=False)
say(f"wrote {out_path}")
