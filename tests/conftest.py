"""Runs before any test module: a private home for the editor, and ffmpeg resolved the way `gre` resolves it at
startup (the computer's own, or the one bundled with the editor), so bare `ffmpeg` calls in the tests find it."""
import os
from pathlib import Path

os.environ.setdefault("GRE_HOME", str(Path(__file__).parent / ".home"))
os.environ.setdefault("GRE_LISTEN", "0")       # no test runs the transcriber: the listen-back is tested on word lists
from gre import tools  # noqa: E402

tools.activate()


def pytest_report_header(config):
    st = tools.activate()
    return f"ffmpeg: {st['source']} ({st['ffmpeg']}), ffprobe: {st['ffprobe'] or 'none (read with ffmpeg)'}"
