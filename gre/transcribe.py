"""Local transcription for yaps: WhisperX (Whisper large-v3 + wav2vec2 word alignment), free, on this computer.

It lives in its own Python environment (~/.go-reel-editor/whisperx-venv) because it pulls PyTorch: about 1 GB of
packages plus about 3 GB of model downloads, ONCE, the first time a member edits a yap. EZ reels never need it."""
import json, os, shutil, subprocess, sys
from pathlib import Path
from .common import HOME, SKILL, UserError

VENV = HOME / "whisperx-venv"
WHISPERX = "whisperx==3.8.6"
WORKER = Path(__file__).with_name("_whisperx_worker.py")


def venv_python():
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ready():
    return venv_python().exists() and (VENV / ".ok").exists()


def status():
    if ready():
        return "ready (WhisperX, local)"
    return "not installed yet: it installs itself the first time you edit a yap (about 4 GB, 10-20 minutes, once)"


def ensure(log=print):
    if ready():
        return
    uv = shutil.which("uv")
    if not uv:
        raise UserError("uv is not installed. Say 'set me up'.")
    log("first yap on this computer: installing the transcriber (WhisperX). About 1 GB now, ~3 GB of models on the "
        "first run. This happens once.")
    if not venv_python().exists():
        subprocess.run([uv, "venv", "--python", "3.11", str(VENV)], check=True)
    r = subprocess.run([uv, "pip", "install", "--python", str(venv_python()), WHISPERX])
    if r.returncode:
        raise UserError("installing WhisperX failed (see above). Check the internet connection and run it again.")
    (VENV / ".ok").write_text(WHISPERX + "\n")
    log("transcriber installed")


def transcribe(clips, out_json, model=None, log=print):
    """Transcribe the clips (in order) into one words.json: {"clips": [{"clip", "path", "duration", "words": [...]}]}."""
    ensure(log)
    model = model or os.environ.get("GRE_WHISPER_MODEL", "large-v3")
    env = dict(os.environ, PYTHONUNBUFFERED="1", TOKENIZERS_PARALLELISM="false", PYTHONWARNINGS="ignore",
               HF_HUB_ENABLE_HF_TRANSFER="0")       # some machines set it; the package it needs is not installed
    log(f"transcribing {len(clips)} clip(s) with Whisper {model} on this computer (first run downloads the model)")
    r = subprocess.run([str(venv_python()), str(WORKER), str(out_json), model, *map(str, clips)], env=env)
    if r.returncode:
        raise UserError("transcription failed (see the messages above)")
    return json.loads(Path(out_json).read_text())
