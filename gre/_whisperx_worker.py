"""Runs INSIDE the WhisperX environment (not the gre one). argv: out.json model clip [clip ...]
Device ladder: an NVIDIA GPU when one works (float16, then int8_float16), else CPU int8 (always works; Apple Silicon
uses CPU: MPS is still unreliable for these models)."""
import json, os, sys

out_path, model_name, clips = sys.argv[1], sys.argv[2], sys.argv[3:]
import logging, warnings  # noqa: E402
warnings.filterwarnings("ignore")                  # torchcodec/lightning chatter: harmless, and it scares members
for name in ("whisperx", "lightning", "lightning_fabric", "pytorch_lightning", "pyannote", "speechbrain"):
    logging.getLogger(name).setLevel(logging.ERROR)
import whisperx  # noqa: E402

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
    print(f"[transcribe] loading Whisper {model_name} ({device}, {ct})", file=sys.stderr, flush=True)
    asr = whisperx.load_model(model_name, device, compute_type=ct, language="en")
    print("[transcribe] loading the word aligner", file=sys.stderr, flush=True)
    al, meta = whisperx.load_align_model(language_code="en", device=device)
    return asr, al, meta


for i, (device, ct, bs) in enumerate(tiers):
    try:
        asr, al, meta = load(device, ct)
        break
    except Exception as e:
        if i == len(tiers) - 1:
            raise
        print(f"[transcribe] {device}/{ct} failed ({e}); trying the next option", file=sys.stderr)

result = {"clips": []}
for path in clips:
    name = os.path.basename(path)
    print(f"[transcribe] {name}", file=sys.stderr, flush=True)
    audio = whisperx.load_audio(path)
    tr = asr.transcribe(audio, batch_size=bs, language="en")
    aligned = whisperx.align(tr["segments"], al, meta, audio, device, return_char_alignments=False)
    words = []
    for seg in aligned.get("segments", []):
        for w in seg.get("words", []):
            if "start" not in w or "end" not in w:      # numerals/punctuation the aligner can't place
                continue
            words.append({"w": str(w.get("word", "")).strip(), "start": round(float(w["start"]), 3),
                          "end": round(float(w["end"]), 3), "prob": round(float(w.get("score", 1.0)), 3)})
    result["clips"].append({"clip": name, "path": os.path.abspath(path), "duration": round(len(audio) / 16000, 3),
                            "words": words})

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=1, ensure_ascii=False)
print(f"[transcribe] wrote {out_path}", file=sys.stderr)
