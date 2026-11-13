"""0.2.0: where ffmpeg comes from (tools), reading a file without ffprobe, `gre find`, `gre update --check`, gre.sh.
No network: the update check reads a folder through GRE_UPDATE_URL=file://..."""
import json, os, shutil, stat, subprocess, sys, time
from datetime import datetime
from pathlib import Path
import pytest

from gre import cli, common, find, tools, update
from gre.common import UserError, video_info

ROOT = Path(__file__).resolve().parent.parent


def fake_tool(folder, name):
    """A stand-in executable called `name` (enough for the resolver, which only looks for the file)."""
    folder.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        p = folder / f"{name}.cmd"
        p.write_text("@echo off\r\n")
    else:
        p = folder / name
        p.write_text("#!/bin/sh\nexit 0\n")
        p.chmod(p.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return p


@pytest.fixture
def fresh_tools(monkeypatch):
    """Let a test re-run the resolver, then put the session's ffmpeg back."""
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))        # restored after the test
    monkeypatch.setattr(tools, "_STATE", tools._STATE)
    for k in ("GRE_FFMPEG_DIR", "GRE_FFMPEG_SOURCE"):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


# ---------- tools: where ffmpeg comes from ----------

def test_ffmpeg_dir_override_wins_and_goes_first_on_path(tmp_path, fresh_tools):
    d = tmp_path / "my ffmpeg"                                    # a space in the path, like a real home folder
    fake_tool(d, "ffmpeg"), fake_tool(d, "ffprobe")
    fresh_tools.setenv("GRE_FFMPEG_DIR", str(d))
    st = tools.activate(refresh=True)
    assert st["source"] == "GRE_FFMPEG_DIR" and Path(st["ffmpeg"]).parent == d and Path(st["ffprobe"]).parent == d
    assert os.environ["PATH"].split(os.pathsep)[0] == str(d)
    assert Path(shutil.which("ffmpeg")).parent == d and tools.have_ffprobe()
    tools.activate(refresh=True)                                  # twice: the folder is not added twice
    assert os.environ["PATH"].split(os.pathsep).count(str(d)) == 1


def test_ffmpeg_dir_override_without_ffmpeg_is_reported_not_ignored(tmp_path, fresh_tools):
    fresh_tools.setenv("GRE_FFMPEG_DIR", str(tmp_path))
    st = tools._resolve()
    assert st["source"] is None and st["ffmpeg"] is None and "GRE_FFMPEG_DIR" in st["why"]


def test_a_system_ffmpeg_with_ffprobe_is_preferred(tmp_path, fresh_tools):
    d = tmp_path / "bin"
    fake_tool(d, "ffmpeg"), fake_tool(d, "ffprobe")
    fresh_tools.setenv("PATH", str(d))
    st = tools._resolve()
    assert st["source"] == "system" and st["dir"] is None and Path(st["ffmpeg"]).parent == d


def test_bundled_ffmpeg_works_without_any_system_ffmpeg(tmp_path, fresh_tools):
    fresh_tools.setattr(common, "HOME", tmp_path / "home")
    fresh_tools.setenv("GRE_FFMPEG_SOURCE", "bundled")
    fresh_tools.setenv("PATH", str(tmp_path / "empty"))
    said = []
    st = tools.activate(log=said.append, refresh=True)
    assert st["source"] == "bundled" and st["ffprobe"] is None and not tools.have_ffprobe()
    assert Path(st["dir"]).is_relative_to(tmp_path / "home") and said        # one plain line the first time
    assert Path(shutil.which("ffmpeg")).parent == Path(st["dir"])
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout
    assert "libx264" in enc
    said.clear()
    assert tools.activate(log=said.append, refresh=True)["source"] == "bundled" and not said   # set up once


def test_no_ffmpeg_anywhere_is_a_plain_problem(tmp_path, fresh_tools, capsys):
    fresh_tools.setenv("GRE_FFMPEG_SOURCE", "none")
    fresh_tools.setenv("PATH", str(tmp_path))
    st = tools.activate(refresh=True)
    assert st["source"] is None
    with pytest.raises(UserError, match="set me up"):
        common.need("ffmpeg")
    assert cli.main(["doctor"]) == 1
    out = capsys.readouterr().out
    assert "MISSING  ffmpeg" in out and out.strip().splitlines()[-1].startswith("NOT READY")


def test_doctor_says_where_ffmpeg_comes_from(capsys):
    assert cli.main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert f"ok   ffmpeg ({tools.activate()['source']})" in out and out.strip().splitlines()[-1] == "READY"


# ---------- reading a file without ffprobe ----------

FF7 = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'IMG_0001.MOV':
  Metadata:
    major_brand     : qt
    creation_time   : 2026-01-01T00:00:00.000000Z
  Duration: 00:01:12.48, start: 0.000000, bitrate: 46654 kb/s
  Stream #0:0[0x1](und): Video: hevc (Main 10) (hvc1 / 0x31637668), yuv420p10le(tv, bt2020nc/bt2020/arib-std-b67), 3840x2160, 46000 kb/s, 29.98 fps, 29.97 tbr, 600 tbn (default)
      Metadata:
        handler_name    : Core Media Video
        encoder         : HEVC
      Side data:
        DOVI configuration record: version: 1.0, profile: 8, level: 4, rpu flag: 1, el flag: 0, bl flag: 1, compatibility id: 4
        displaymatrix: rotation of -90.00 degrees
  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, stereo, fltp, 175 kb/s (default)
      Metadata:
        handler_name    : Core Media Audio
  Stream #0:2[0x3](und): Data: none (mebx / 0x7862656D), 0 kb/s (default)
At least one output file must be specified
"""
FF9 = """Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'clip.mov':
  Duration: 00:00:07.17, start: 0.000000, bitrate: 16292 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709, progressive), 1920x1080 [SAR 1:1 DAR 16:9], 16292 kb/s, 60 fps, 60 tbr, 15360 tbn (default)
    Metadata:
      handler_name    : Core Media Video
    Side data:
      Display Matrix: rotation of 90.00 degrees
At least one output file must be specified
"""


def test_ffmpeg_text_gives_what_ffprobe_gives():
    d = tools.parse_ffmpeg_info(FF7)                        # ffmpeg 7 wording, an iPhone HDR clip held upright
    v, a = d["streams"][0], d["streams"][1]
    assert (v["codec_name"], v["width"], v["height"], v["pix_fmt"]) == ("hevc", 3840, 2160, "yuv420p10le")
    assert (v["color_space"], v["color_primaries"], v["color_transfer"]) == ("bt2020nc", "bt2020", "arib-std-b67")
    assert v["color_range"] == "tv" and v["side_data_list"][0]["rotation"] == -90
    assert (a["codec_type"], a["codec_name"], a["sample_rate"]) == ("audio", "aac", "44100")
    assert abs(float(d["format"]["duration"]) - 72.48) < 1e-6 and [s["codec_type"] for s in d["streams"]][2] == "data"
    n, den = v["avg_frame_rate"].split("/")
    assert abs(float(n) / float(den) - 29.98) < 1e-6
    d = tools.parse_ffmpeg_info(FF9)                        # ffmpeg 9 wording: "Display Matrix:", one colour name
    v = d["streams"][0]
    assert (v["color_primaries"], v["color_transfer"], v["pix_fmt"]) == ("bt709", "bt709", "yuv420p")
    assert v["side_data_list"][0]["rotation"] == 90 and (v["width"], v["height"]) == (1920, 1080)
    assert len(d["streams"]) == 1 and d["format"]["duration"] == "7.170000"


@pytest.fixture(scope="module")
def small_clip(tmp_path_factory):
    p = tmp_path_factory.mktemp("install") / "IMG_0001.MOV"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=30:d=2", "-f", "lavfi",
                    "-i", "sine=f=440:d=2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", p], check=True)
    return p


def test_probe_with_ffmpeg_on_a_real_file(small_clip, tmp_path, monkeypatch):
    d = tools.probe_with_ffmpeg(small_clip)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    a = next(s for s in d["streams"] if s["codec_type"] == "audio")
    assert (v["codec_name"], v["width"], v["height"], v["pix_fmt"], v["avg_frame_rate"]) == \
        ("h264", 640, 360, "yuv420p", "30000/1000")
    assert a["sample_rate"] == "44100" and abs(float(d["format"]["duration"]) - 2.0) < 0.05
    monkeypatch.setattr(tools, "have_ffprobe", lambda: False)          # the editor's own reader, without ffprobe
    i = video_info(small_clip)
    assert (i["w"], i["h"], i["fps"], i["audio"], i["sample_rate"], i["codec"]) == (640, 360, 30.0, True, 44100, "h264")
    junk = tmp_path / "notes.mov"
    junk.write_text("not a video")
    with pytest.raises(UserError, match="notes.mov"):
        tools.probe_with_ffmpeg(junk)


def test_filter_script_option_matches_the_ffmpeg_version(monkeypatch):
    """ffmpeg 9 dropped -filter_complex_script; ffmpeg 6 and older do not know -/filter_complex."""
    class R:
        stdout = ""
    for banner, expected in (("ffmpeg version 9.0 Copyright", "-/filter_complex"),
                             ("ffmpeg version 7.1.1 Copyright", "-/filter_complex"),
                             ("ffmpeg version n8.0.1 Copyright", "-/filter_complex"),
                             ("ffmpeg version 2026-10-01-git-abc1234-full_build-www.gyan.dev", "-/filter_complex"),
                             ("ffmpeg version 6.1.1-3ubuntu5 Copyright", "-filter_complex_script"),
                             ("ffmpeg version 4.4.2-0ubuntu0.22.04.1", "-filter_complex_script")):
        R.stdout = banner + "\nbuilt with ..."
        monkeypatch.setattr(common.subprocess, "run", lambda *a, **k: R)
        assert common.filter_script("a b.filter") == [expected, "a b.filter"], banner


# ---------- gre find ----------

def touch(p, age_days=0.0, data=b"x" * 2048):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    t = time.time() - age_days * 86400
    os.utime(p, (t, t))
    return p


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "Downloads").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("OneDrive", raising=False)
    work = tmp_path / "Reels"
    work.mkdir()
    monkeypatch.chdir(work)
    return home, work


def test_find_lists_the_newest_media_and_skips_work_folders(fake_home, small_clip, capsys):
    home, work = fake_home
    movies = "Movies" if sys.platform == "darwin" else "Videos"
    shutil.copy(small_clip, home / "Downloads" / "IMG_4821.MOV")           # newest: a real 2 s video
    touch(work / "listing" / "front.jpg", age_days=1.2)
    touch(home / movies / "old-take.mp4", age_days=10)
    touch(home / "Desktop" / "ancient.mp4", age_days=45)                    # older than --days 30
    touch(home / "Downloads" / "notes.pdf")                                  # not media
    for skipped in ("out/final.mp4", "edit/draft.mp4", ".venv/x.mp4", "practice-listicle/a.mp4", ".hidden/b.mp4",
                    "a/b/c/d/too-deep.mp4"):
        touch(work / skipped)
    assert cli.main(["find"]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert [ln.split(" · ")[0] for ln in lines] == ["1. IMG_4821.MOV", "2. front.jpg", "3. old-take.mp4"]
    first = lines[0].split(" · ")
    assert first[1] == "Downloads" and first[2].startswith("today ") and first[2].endswith(("am", "pm"))
    assert first[3] == "0:02" and first[4].endswith(("KB", "bytes"))         # the video's length, then its size
    assert Path(first[5]) == home / "Downloads" / "IMG_4821.MOV"
    second = lines[1].split(" · ")                                           # a photo: no length
    assert second[1] == "listing" and len(second) == 5 and second[3] == "2 KB"
    assert cli.main(["find", "--kind", "image", "--limit", "1"]) == 0
    assert capsys.readouterr().out.strip().splitlines() == ["1." + lines[1][2:]]
    assert cli.main(["find", "--kind", "video", "--days", "60"]) == 0
    assert [ln.split(" · ")[0][3:] for ln in capsys.readouterr().out.strip().splitlines()] == \
        ["IMG_4821.MOV", "old-take.mp4", "ancient.mp4"]
    assert cli.main(["find", str(work / "out")]) == 0                        # a folder named on purpose is searched
    assert capsys.readouterr().out.startswith("1. final.mp4 · out · today")


def test_find_none_found_and_unreadable_folders(fake_home, capsys):
    home, work = fake_home
    assert cli.main(["find", "--kind", "video"]) == 0
    assert capsys.readouterr().out.strip() == "NONE FOUND"
    assert cli.main(["find", str(home / "no-such-folder")]) == 0             # never a crash
    assert capsys.readouterr().out.strip() == "NONE FOUND"
    if os.name == "nt" or os.geteuid() == 0:
        return                                                               # chmod cannot lock a folder here
    touch(home / "Downloads" / "IMG_1.MOV")
    touch(work / "b.mp4", age_days=1)
    (home / "Downloads").chmod(0)                                            # like macOS privacy refusing Downloads
    try:
        assert cli.main(["find"]) == 0
        lines = capsys.readouterr().out.strip().splitlines()
    finally:
        (home / "Downloads").chmod(0o755)
    assert lines[0].startswith("1. b.mp4 · Reels · yesterday") and len(lines) == 2
    assert lines[-1] == "could not look in: Downloads (no permission)"


def test_find_wording():
    now = datetime(2026, 11, 10, 15, 0)
    assert find.when(datetime(2026, 11, 10, 9, 41).timestamp(), now) == "today 9:41 am"
    assert find.when(datetime(2026, 11, 10, 0, 5).timestamp(), now) == "today 12:05 am"
    assert find.when(datetime(2026, 11, 9, 16, 5).timestamp(), now) == "yesterday 4:05 pm"
    assert find.when(datetime(2026, 11, 3, 12, 0).timestamp(), now) == "Nov 3"
    assert find.when(datetime(2025, 12, 31, 12, 0).timestamp(), now) == "Dec 31 2025"
    assert [find.size(n) for n in (900, 38 * 1024, 412 * 2**20, int(1.25 * 2**30), 12 * 2**30)] == \
        ["900 bytes", "38 KB", "412 MB", "1.2 GB", "12 GB"]
    assert [find.length(s) for s in (7, 72, 3725)] == ["0:07", "1:12", "1:02:05"]


# ---------- gre update --check ----------

CHANGELOG = """# Changelog

Newest first.

## 9.9.9 · 2027-01-01 · easier everything

- **No more Homebrew**: the video tool ships with the editor, so setup needs no password
  and no Terminal.
  - a nested bullet that is not a headline
- **Find my video:** Claude offers the newest files instead of asking you to move them.
- A plain bullet without a bold lead-in. It has a second sentence.
- **A fourth thing**: not shown.

## 0.1.7 · 2026-11-10 · older

- **Old news**: not shown either.
"""


@pytest.fixture
def remote(tmp_path, monkeypatch):
    r = tmp_path / "remote"
    r.mkdir()
    (r / "VERSION").write_text("9.9.9\n")
    (r / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    monkeypatch.setenv("GRE_UPDATE_URL", r.as_uri())
    monkeypatch.setattr(update, "HOME", tmp_path / "gre-home")
    return r


def test_update_check_reports_a_newer_version_once_a_day(remote, capsys):
    local = (ROOT / "VERSION").read_text().strip()
    assert cli.main(["update", "--check"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"UPDATE AVAILABLE {local} -> 9.9.9", "- No more Homebrew", "- Find my video",
        "- A plain bullet without a bold lead-in."]
    cache = json.loads((update.HOME / "update-check.json").read_text())
    assert cache["remote"] == "9.9.9" and time.time() - cache["checked"] < 60
    assert cli.main(["update", "--check"]) == 0                       # the same day: no second network check
    assert capsys.readouterr().out.strip() == "CHECK SKIPPED (checked in the last 24 hours)"
    assert cli.main(["update", "--check", "--force"]) == 0
    assert capsys.readouterr().out.startswith(f"UPDATE AVAILABLE {local} -> 9.9.9\n- No more Homebrew\n")
    assert update.check(now=time.time() + 25 * 3600)[0].startswith("UPDATE AVAILABLE")     # a day later it looks again


def test_update_check_up_to_date_offline_and_garbage(remote, capsys):
    local = (ROOT / "VERSION").read_text().strip()
    (remote / "VERSION").write_text(local + "\n")
    assert cli.main(["update", "--check", "--force"]) == 0
    assert capsys.readouterr().out.strip() == f"UP TO DATE {local}"
    (remote / "VERSION").write_text("0.0.1\n")                        # an older remote is not an update
    assert update.check(force=True) == [f"UP TO DATE {local}"]
    (remote / "VERSION").write_text("<html>Not Found</html>")
    assert update.check(force=True) == ["CHECK SKIPPED (the update server gave an unexpected answer)"]
    (remote / "VERSION").unlink()                                     # nothing answers: the same as offline
    assert cli.main(["update", "--check", "--force"]) == 0
    out = capsys.readouterr().out.strip()
    assert out.startswith("CHECK SKIPPED (") and len(out.splitlines()) == 1
    (remote / "VERSION").write_text("9.9.9\n")
    (remote / "CHANGELOG.md").unlink()                                # no changelog: still says there is an update
    assert update.check(force=True) == [f"UPDATE AVAILABLE {local} -> 9.9.9"]


def test_versions_agree():
    from gre import __version__
    assert (ROOT / "VERSION").read_text().strip() == __version__
    assert f'version = "{__version__}"' in (ROOT / "pyproject.toml").read_text()


# ---------- gre.sh ----------

@pytest.mark.skipif(not shutil.which("bash"), reason="needs bash")
def test_launcher_says_set_me_up_when_uv_is_missing(tmp_path):
    if os.name == "nt" or any(os.access(Path(d, "uv"), os.X_OK) for d in ("/opt/homebrew/bin", "/usr/local/bin")):
        pytest.skip("uv is installed system-wide on this computer: the launcher would find it")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    r = subprocess.run(["bash", str(ROOT / "gre.sh"), "doctor"], env=env, capture_output=True, text=True)
    assert r.returncode == 3 and r.stdout == ""
    assert r.stderr.strip() == 'PROBLEM: the editor is not set up yet. Say "set me up".'


@pytest.mark.skipif(not shutil.which("bash") or os.name == "nt", reason="needs bash on Mac or Linux")
def test_clean_test_file_hides_homebrew_from_the_launcher_and_the_tools(tmp_path, fresh_tools):
    home = tmp_path / ".go-reel-editor"
    home.mkdir()
    (home / "clean-test").write_text("")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    r = subprocess.run(["bash", str(ROOT / "gre.sh"), "doctor"], env=env, capture_output=True, text=True)
    assert r.returncode == 3, "with the file in place, a uv in /opt/homebrew or /usr/local must not be found"
    fresh_tools.setattr(tools, "_home", lambda: home)
    assert tools.clean_test()
    assert tools._resolve()["source"] == "bundled"


def git_bash():
    """The bash Claude Code runs. On Windows a bare `bash` started from Python is the WSL launcher in System32,
    not Git Bash, so look for Git's own."""
    if os.name != "nt":
        return shutil.which("bash")
    git = shutil.which("git")
    spots = [Path(os.environ.get(v, "")) / "Git" / "bin" / "bash.exe" for v in ("ProgramFiles", "ProgramW6432")]
    if git:
        spots.insert(0, Path(git).resolve().parent.parent / "bin" / "bash.exe")
    return next((str(p) for p in spots if p.is_file()), None)


@pytest.mark.skipif(not git_bash() or not shutil.which("uv"), reason="needs bash and uv")
def test_launcher_runs_gre_from_a_folder_with_spaces(tmp_path):
    work = tmp_path / "My Reels"
    work.mkdir()
    r = subprocess.run([git_bash(), str(ROOT / "gre.sh"), "looks"], cwd=work, capture_output=True, text=True)
    assert r.returncode == 0 and "clean" in r.stdout, r.stdout + r.stderr
