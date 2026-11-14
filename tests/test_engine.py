"""The engine's tests. Footage is synthetic (made by ffmpeg at test time), so no member's video is ever in the repo.
Run: uv run --group dev pytest -q"""
import os, subprocess
from pathlib import Path
import pytest
from PIL import Image

os.environ.setdefault("GRE_HOME", str(Path(__file__).parent / ".home"))
from gre import broll, listicle, xreel, captions, plan, cut, render, title          # noqa: E402
from gre.common import UserError, load_look, save_profile, video_info, W, H, FPS, SAFE_TOP, SAFE_BOTTOM  # noqa: E402
from gre.qa import qa, loudness                                                       # noqa: E402

LOOKS = ("clean", "bold", "serif")


@pytest.fixture(scope="session")
def tmp(tmp_path_factory):
    return tmp_path_factory.mktemp("gre")


@pytest.fixture(scope="session")
def clip(tmp):
    """8 s of moving portrait test pattern with a 440 Hz tone, rotated like an iPhone file."""
    p = tmp / "clip.mov"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=8",
                    "-f", "lavfi", "-i", "sine=f=440:d=8", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    "-metadata:s:v:0", "rotate=90", p], check=True)
    return p


@pytest.fixture(scope="session")
def avatar(tmp):
    p = tmp / "me.png"
    Image.new("RGB", (400, 400), (200, 120, 60)).save(p)
    save_profile(name="Test Member", handle="@testmember", avatar=str(p))
    return p


@pytest.mark.parametrize("lk", LOOKS)
def test_listicle_renders_in_every_look(tmp, clip, lk):
    out = tmp / f"listicle-{lk}.mp4"
    spec = {"clip": str(clip), "title": "What $400K buys you", "items": [f"City {i}: 3 bed, 2 bath" for i in range(6)],
            "small": "Source: test", "punchline": "Same money. Different house."}
    listicle.render(spec, load_look(lk), str(out), log=lambda *_: None)
    i = video_info(out)
    assert (i["w"], i["h"]) == (W, H) and abs(i["duration"] - 7.0) < 0.1 and not i["audio"]
    assert qa(str(out)) == 0


@pytest.mark.parametrize("lk", LOOKS)
def test_broll_renders_in_every_look(tmp, clip, lk):
    out = tmp / f"broll-{lk}.mp4"
    spec = {"clip": str(clip), "blocks": [{"text": "I almost told this buyer to wait…", "style": "white"},
                                          {"text": "then we ran the numbers", "style": "black"},
                                          {"text": "Here's what changed:", "style": "black"}]}
    broll.render(spec, load_look(lk), str(out), log=lambda *_: None)
    assert abs(video_info(out)["duration"] - 7.0) < 0.1
    assert qa(str(out)) == 0


@pytest.mark.parametrize("lk", LOOKS)
def test_xreel_renders_in_every_look(tmp, avatar, lk):
    img = tmp / "news.jpg"
    Image.new("RGB", (1280, 720), (30, 80, 160)).save(img)
    out = tmp / f"xreel-{lk}.mp4"
    spec = {"text": "BREAKING: A test headline about a $30 billion build.\n\nHere's what it means 👇", "image": str(img)}
    xreel.render(spec, load_look(lk), str(out), log=lambda *_: None)
    assert abs(video_info(out)["duration"] - 6.0) < 0.1
    assert qa(str(out)) == 0


def test_xreel_emoji_without_apple_font(tmp, avatar, monkeypatch):
    """Windows has no Apple Color Emoji: the bundled Noto font draws the 👇."""
    monkeypatch.setattr(xreel, "APPLE_EMOJI", Path("/nonexistent"))
    monkeypatch.setattr(xreel, "_EF", None)
    img = tmp / "news2.jpg"
    Image.new("RGB", (1280, 720), (30, 80, 160)).save(img)
    card = xreel.card({"text": "JUST IN: test 👇", "image": str(img)}, load_look("clean"))
    colours = {px for px in list(card.convert("RGB").getdata())}
    assert any(r > 200 and 150 < g < 230 and b < 120 for r, g, b in colours)   # the emoji's yellow-orange skin tone


def test_text_outside_the_safe_band_is_refused(clip):
    lk = load_look("clean")
    with pytest.raises(UserError):
        broll.layout([{"text": "x", "style": "white", "y": 0.05}], lk)
    with pytest.raises(UserError):
        listicle.check({"clip": str(clip), "title": "t", "items": ["row"] * 15})
    with pytest.raises(UserError):
        broll.check({"clip": str(clip), "blocks": [{"text": "a"}] * 5})


def test_listicle_card_stays_in_the_band():
    for lk in LOOKS:
        img = listicle.card({"title": "Ten things", "items": [f"{i}. A short row of words" for i in range(10)],
                             "punchline": "And one more."}, load_look(lk))
        x0, y0, x1, y1 = img.getbbox()
        assert y0 >= SAFE_TOP - 50 and y1 <= SAFE_BOTTOM + 50       # a panel's padding may sit just outside


# ---------------- captions ----------------

def test_numerals():
    assert captions.numerals("I paid thirty-four dollars".split())[2] == "34"
    out = captions.numerals("back in two thousand nine we".split())
    assert "2009" in out and "" in out
    assert captions.numerals("the thirty-first of May".split())[1] == "31st"
    assert captions.numerals("three years".split())[0] == "three"


def test_split_never_ends_on_a_small_word():
    from PIL import ImageFont
    ws = "So here is the thing about the buyers in this market that nobody talks about".split()
    lines = captions._split(ws, lambda w: 60 * len(" ".join(w)) / 3, 940, 5)
    for ln in lines[:-1]:
        assert ln[-1].lower() not in {"the", "a", "in", "about", "that", "of", "to"}, lines


def _played(text):
    return [{"i": k, "w": w, "heard": w, "start": k * 0.4, "end": k * 0.4 + 0.3} for k, w in enumerate(text.split())]


def test_caption_rules_are_checked():
    lk = load_look("clean")
    played = _played("Bad news, realtors. Rates are up and the buyers wait.")
    lines = ["Bad news, realtors Rates", "are up and the", "buyers wait."]
    caps, problems, hard = captions.build(lines, played, lk)
    text = "\n".join(hard)
    assert "sentence end" in text and "Realtor" in text and "small word" in text and "period" in text


def test_caption_alignment_survives_hyphens_and_fixes():
    lk = load_look("clean")
    played = _played("Most use buy downs the wrong way.")
    caps, problems, hard = captions.build(["Most use buy-downs", "the **wrong** way"], played, lk)
    assert not hard and len(caps) == 2 and caps[1]["start"] > caps[0]["start"]
    caps, problems, hard = captions.build(["Most use buy-downs", "the wrong day"], played, lk)
    assert not hard and any("shown for the heard" in p for p in problems)


# ---------------- the cut ----------------

def _flat(text, gap=0.35):
    out, t = [], 0.0
    for i, w in enumerate(text.split()):
        out.append({"w": w, "start": round(t, 3), "end": round(t + 0.3, 3), "ci": 0, "i": i, "clip": "a.mov"})
        t += gap
    return out


@pytest.mark.parametrize("text,expect", [
    ("Owning a home here in Owning a home here in Texas is great.", "Owning a home here in Texas is great."),
    ("Rates are up. Um rates are up this week. Here's why.", "rates are up this week. Here's why."),
    ("That's it. That's the whole pitch.", "That's it. That's the whole pitch."),
    ("I went to the the store.", "I went to the store."),
])
def test_unscripted_plan_drops_restarts_not_repeats(text, expect):
    f = _flat(text)
    keep, cuts = plan.plan_unscripted(f)
    assert " ".join(f[i]["w"] for i in keep) == expect


def test_scripted_plan_keeps_the_last_complete_take():
    rec = ("Stick with me here. Owning a home here in Owning a home here in Texas is still attainable. "
           "They should be talking about They should be talking about life after closing.")
    script = "Owning a home here in Texas is still attainable. They should be talking about life after closing."
    f = _flat(rec)
    sents = plan.script_sentences(script)
    chosen, display, notes = plan.plan_scripted(f, sents)
    kept = sorted({i for _, k in chosen for i in k})
    assert " ".join(f[i]["w"] for i in kept) == script


def test_script_sentences_drop_headings_and_directions():
    s = plan.script_sentences("# 1 CLAIM\nHOOK: Rates are up. [pause]\n- Most people wait (look at camera) too long.")
    assert s == ["Rates are up.", "Most people wait too long."]


# ---------------- the yap render (sync) ----------------

@pytest.fixture(scope="session")
def talk(tmp):
    """A fake talking clip: 6 tone bursts ('words') with silences between them."""
    p = tmp / "talk.mov"
    expr = "0.5*sin(2*PI*300*t)*(lt(mod(t\\,1)\\,0.6))"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=6",
                    "-f", "lavfi", "-i", f"aevalsrc={expr}:s=48000:d=6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", p], check=True)
    return p


@pytest.mark.parametrize("preview", [False, True])
def test_yap_cut_and_render_keep_sound_on_picture(tmp, talk, preview):
    flat = [{"w": f"word{i}.", "start": float(i), "end": i + 0.6, "ci": 0, "i": i, "clip": "talk.mov"} for i in range(6)]
    keep = {"segments": [{"from": 0, "to": 1}, {"from": 3, "to": 5}]}
    segs = cut.build(flat, keep, [str(talk)])
    assert len(segs) == 2                         # 0.4 s gaps stay inside a piece; the cut word splits it
    cuts = {"clips": [str(talk)], "segments": segs}
    out = tmp / "yap.mp4"
    lk = load_look("clean")
    caps = captions.images([{"text": "word one", "start": 0.0, "end": 1.0}], lk)
    t = title.layer({"lines": ["A test title"], "size": 80, "top": 330}, lk)
    render.render(cuts, out, captions=caps, title=t, label="v1", log=lambda *_: None, preview=preview)
    v = video_info(out)
    assert (v["w"], v["h"]) == ((540, 960) if preview else (1080, 1920))   # drafts are light previews
    n = sum(render.frame_plan(segs))
    assert abs(v["duration"] - n / FPS) < 0.05
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-map", "0:a:0", "-f", "s16le", "-ac", "1", "-ar",
                          "48000", "-"], capture_output=True).stdout      # the sound's real length (no ffprobe needed)
    assert abs(len(pcm) / 2 / 48000 - n / FPS) < 0.06


def test_a_photo_can_be_the_background(tmp):
    img = tmp / "photo.jpg"
    Image.new("RGB", (1600, 1200), (90, 140, 90)).save(img)
    out = tmp / "photo-listicle.mp4"
    listicle.render({"clip": str(img), "title": "Five things", "items": [f"Row {i}" for i in range(5)]},
                    load_look("clean"), str(out), log=lambda *_: None)
    assert abs(video_info(out)["duration"] - 7.0) < 0.1 and qa(str(out)) == 0


def test_personal_look_and_logo_colours(tmp, avatar):
    from gre import brand
    logo = tmp / "logo.png"
    Image.new("RGB", (200, 200), (237, 63, 45)).save(logo)
    assert brand.logo_colours(logo)[0].upper() in ("#ED3F2D", "#EC3F2D", "#ED3E2D", "#EC3E2C")
    slug, p = brand.make_look("Test Member", base="bold", accent="#155CFF", caption_size=100)
    lk = load_look(slug)
    assert lk["styles"]["accent"]["box"][:3] == [21, 92, 255] and lk["styles"]["accent"]["ink"][:3] == [255, 255, 255]
    assert lk["listicle"]["punchline"]["style"] == "accent" and lk["captions"]["size"] == 100
    out = brand.sample_sheet(slug, tmp / "sheet.png")
    assert Image.open(out).size[1] == H // 3


def test_xreel_is_static_and_inside_the_reel_safe_zone(tmp, avatar):
    """Cyrus 2026-10-21: no slow zoom, 6-7 s, the text inside the reel safe zone (top 14 %, bottom 35 %, sides 6 %).
    Cyrus 2026-11-13: the photo may run below it, to the feed-safe line, so a tall photo is not cut to a strip."""
    from gre.common import REEL_LEFT, REEL_RIGHT, REEL_TOP, REEL_BOTTOM, REEL_PHOTO_BOTTOM
    tall = tmp / "tall.jpg"
    Image.new("RGB", (900, 1600), (180, 60, 60)).save(tall)
    spec = {"text": "BREAKING: A long test headline about a very large build in a fast-growing Texas suburb.\n\n"
                    "Here's what it means 👇", "image": str(tall), "name": "A Very Long Display Name Indeed"}
    card = xreel.card(spec, load_look("clean"))
    photo_top = card.info["photo_top"]
    text = card.convert("L").point(lambda v: 255 if v > 12 else 0).crop((0, 0, W, photo_top)).getbbox()
    assert text[0] >= REEL_LEFT and text[1] >= REEL_TOP and text[2] <= REEL_RIGHT and text[3] <= REEL_BOTTOM, text
    assert REEL_PHOTO_BOTTOM - photo_top > 600, "a tall photo keeps most of its height"
    out = tmp / "xreel-static.mp4"
    xreel.render(spec, load_look("clean"), str(out), log=lambda *_: None)
    assert 6.0 <= video_info(out)["duration"] <= 7.0
    frames = []
    for t in (0.0, 5.9):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1", "-f", "rawvideo",
                              "-pix_fmt", "gray", "-"], capture_output=True).stdout
        frames.append(raw)
    import numpy as np
    a, b = (np.frombuffer(f, np.uint8).astype(int) for f in frames)
    d = np.abs(a - b)
    assert d.mean() < 0.05 and (d > 8).mean() < 0.001      # the same card, codec noise only (a zoom moves every pixel)
    img = Image.frombytes("L", (W, H), frames[0]).point(lambda v: 255 if v > 12 else 0)
    x0, y0, x1, y1 = img.getbbox()
    assert x0 >= REEL_LEFT and x1 <= REEL_RIGHT and y0 >= REEL_TOP and REEL_BOTTOM < y1 <= REEL_PHOTO_BOTTOM, (x0, y0, x1, y1)


# ---------------- b-roll: the text keeps clear of faces ----------------
# Face detection never fires on synthetic footage, so the tests hand broll.find_faces the faces (x, y, w, h).

def _broll_spec(clip, n=2, **kw):
    lines = ["I almost told this buyer to wait…", "then we ran the numbers", "Here's what changed:"][:n]
    return {"clip": str(clip), "blocks": [{"text": t, "style": "white" if i == 0 else "black"}
                                          for i, t in enumerate(lines)], **kw}


def _placed(spec, lk, monkeypatch, faces):
    monkeypatch.setattr(broll, "find_faces", lambda *a, **k: list(faces))
    notes = []
    sized, tops, lk2 = broll.place(spec, lk, log=notes.append)
    return sized, tops, lk2, notes, broll._boxes(sized, tops, lk2)


def _clear(boxes, faces):
    return not broll._covers(boxes, 0, broll.face_zones(faces))


@pytest.mark.parametrize("lk", LOOKS)
def test_broll_text_moves_off_a_face_to_the_nearer_side(clip, monkeypatch, lk):
    lk = load_look(lk)
    spec = _broll_spec(clip)
    usual = broll._boxes(*broll.layout(spec["blocks"], lk), lk)
    for face, side in (((390, 700, 300, 300), "below"), ((390, 880, 300, 300), "above")):
        assert not _clear(usual, [face])                               # mid-frame, the text is across this face
        sized, tops, lk2, notes, boxes = _placed(spec, lk, monkeypatch, [face])
        assert _clear(boxes, [face])
        assert min(b[1] for b in boxes) >= SAFE_TOP and max(b[3] for b in boxes) <= SAFE_BOTTOM
        assert lk2["size"] == lk["size"]                               # room at full size: the type is not touched
        assert len(notes) == 1 and notes[0] == f"note: moved the text {side} the face"
        gaps = [b - a for a, b in zip(tops, tops[1:])]                 # one block: the lines moved together
        assert gaps == [b - a for a, b in zip(broll.layout(spec["blocks"], lk)[1], broll.layout(spec["blocks"], lk)[1][1:])]


def test_broll_without_a_face_is_exactly_as_before(clip, monkeypatch):
    for name in LOOKS:
        lk = load_look(name)
        spec = _broll_spec(clip, 3)
        before = broll.overlay(*broll.layout(spec["blocks"], lk), lk)
        for faces in ([], [(0, 900, 90, 90)]):                         # none, or one the text does not reach
            sized, tops, lk2, notes, _ = _placed(spec, lk, monkeypatch, faces)
            assert lk2 is lk and not notes
            assert broll.overlay(sized, tops, lk2).tobytes() == before.tobytes()


def test_broll_face_search_never_fails(clip, tmp):
    """The real detector: no face in a test pattern or a flat photo, and footage it cannot read has no faces."""
    photo = tmp / "plain.png"
    Image.new("RGB", (1600, 1200), (90, 140, 90)).save(photo)
    assert broll.find_faces(str(clip), 0, 7) == [] and broll.find_faces(str(photo)) == []
    assert broll.find_faces(str(tmp / "missing.mov")) == [] and broll.find_faces(str(tmp / "missing.jpg")) == []


def test_broll_spec_can_switch_face_avoidance_off(clip, monkeypatch):
    lk = load_look("clean")
    face = [(390, 700, 300, 300)]
    usual = broll.layout(_broll_spec(clip)["blocks"], lk)[1]
    for kw in ({"avoid_faces": False}, {"center_y": 0.5}):
        _, tops, _, notes, _ = _placed(_broll_spec(clip, **kw), lk, monkeypatch, face)
        assert tops == usual and not notes
    _, tops, _, _, _ = _placed(_broll_spec(clip, center_y=0.3), lk, monkeypatch, face)
    assert tops[0] < usual[0] - 300                                    # the spec's own height wins
    spec = _broll_spec(clip)
    spec["blocks"][0]["y"] = 0.45                                      # a pinned line: the member placed it
    assert not _placed(spec, lk, monkeypatch, face)[3]
    with pytest.raises(UserError):
        _placed(_broll_spec(clip, center_y=0.1), lk, monkeypatch, face)


def test_broll_two_faces(clip, monkeypatch):
    lk = load_look("clean")
    spec = _broll_spec(clip)
    apart = [(390, 380, 240, 240), (390, 1150, 240, 240)]              # room between them: nothing moves
    _, tops, lk2, notes, boxes = _placed(spec, lk, monkeypatch, apart)
    assert not notes and tops == broll.layout(spec["blocks"], lk)[1] and _clear(boxes, apart)
    close = [(390, 380, 240, 330), (390, 1010, 240, 440)]              # 205 px between, none outside: smaller type
    _, tops, lk2, notes, boxes = _placed(spec, lk, monkeypatch, close)
    assert _clear(boxes, close) and broll.min_size(lk) <= lk2["size"] < lk["size"]
    assert notes == ["note: moved the text clear of the faces and made it a little smaller so it fits there"]
    tight = [(390, 300, 400, 400), (390, 900, 500, 500)]               # no room anywhere: say so, never crash
    _, tops, lk2, notes, boxes = _placed(spec, lk, monkeypatch, tight)
    assert len(notes) == 1 and notes[0].startswith("note: could not keep the text fully clear of the face")
    assert lk2["size"] >= broll.min_size(lk)
    assert min(b[1] for b in boxes) >= SAFE_TOP and max(b[3] for b in boxes) <= SAFE_BOTTOM
    whole = [(0, 0, W, H)]                                             # a face over the whole frame: left as it was
    _, tops, lk2, notes, _ = _placed(spec, lk, monkeypatch, whole)
    assert tops == broll.layout(spec["blocks"], lk)[1] and lk2 is lk and len(notes) == 1


def test_broll_preview_and_render_place_the_text_the_same(tmp, monkeypatch, capsys):
    import json
    import numpy as np
    from gre import cli
    photo = tmp / "flat.png"
    Image.new("RGB", (1080, 1920), (70, 110, 150)).save(photo)
    spec = tmp / "face-broll.json"
    spec.write_text(json.dumps(_broll_spec("flat.png")), encoding="utf-8")
    monkeypatch.setattr(broll, "find_faces", lambda *a, **k: [(390, 700, 300, 300)])
    still, video = tmp / "face-broll.png", tmp / "face-broll.mp4"
    assert cli.main(["preview", str(spec), "--look", "clean", "--out", str(still)]) == 0
    assert cli.main(["broll", str(spec), "--look", "clean", "--out", str(video)]) == 0
    assert capsys.readouterr().out.count("note: moved the text below the face") == 2
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "6.5", "-i", str(video), "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True).stdout
    frame = np.frombuffer(raw, np.uint8).reshape(H, W)
    prev = np.array(Image.open(still).convert("L"))

    def white_rows(a):                                                 # the white box of the first line
        ys = np.where((a > 235).sum(1) > 200)[0]
        return int(ys.min()), int(ys.max())

    a, b = white_rows(prev), white_rows(frame)
    assert abs(a[0] - b[0]) <= 2 and abs(a[1] - b[1]) <= 2 and a[0] > 1000, (a, b)


# ---------------- listicle: the checklist layout ----------------

from gre import checklist                                              # noqa: E402

CHECKLIST = {"layout": "checklist", "title": "Buying your first home? Read this first",
             "items": ["Get pre-approved before you tour a single house.",
                       "Your payment is more than principal and interest.",
                       "Closing costs run 2% to 5% of the price.",
                       "A lower rate is not always the cheaper loan.",
                       "Keep your credit quiet until the keys are yours."],
             "punchline": "📌 Save this before you start your search"}


def _frame(video, t):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-f",
                          "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3).astype(int)


@pytest.mark.parametrize("lk", LOOKS)
def test_checklist_renders_in_every_look(tmp, clip, lk):
    out = tmp / f"checklist-{lk}.mp4"
    spec = {**CHECKLIST, "clip": str(clip)}
    look = load_look(lk)
    said = []
    listicle.render(spec, look, str(out), log=said.append)
    i = video_info(out)
    dur = listicle.duration_for(spec, look)
    assert (i["w"], i["h"]) == (W, H) and abs(i["duration"] - dur) < 0.1 and not i["audio"]
    assert 7.0 <= dur <= 12.0 and qa(str(out)) == 0
    assert "the closing line from" in said[-1]
    x0, y0, x1, y1 = [b[1:] for b in checklist.boxes(spec, look) if b[0] == "punchline"][0]
    inside = (slice(y0 + 14, y1 - 6), slice(x0 + 6, x0 + 16))          # a strip of the closing line's box
    half, late = _frame(out, dur * 0.5)[inside], _frame(out, dur * 0.9)[inside]
    assert (late.max(2) < 40).mean() > 0.95                            # there at 90 %: its black box
    assert (half.max(2) < 40).mean() < 0.5                             # not there at 50 %: the footage shows


def test_checklist_boxes_stay_in_the_band_and_the_frame():
    from gre.common import REEL_LEFT, REEL_RIGHT
    for name in LOOKS:
        lk = load_look(name)
        for spec in (CHECKLIST, {**CHECKLIST, "items": CHECKLIST["items"] + ["Ask what the seller will pay toward your costs."]}):
            bs = checklist.boxes(spec, lk)
            assert len({b[0] for b in bs}) == 3
            for part, x0, y0, x1, y1 in bs:
                assert SAFE_TOP <= y0 < y1 <= SAFE_BOTTOM and REEL_LEFT <= x0 < x1 <= REEL_RIGHT, (name, part, x0, y0, x1, y1)
            img = listicle.card(spec, lk)                              # what `gre preview` draws: the whole stack
            bb = img.getbbox()
            assert bb[1] == bs[0][2] and bb[3] == bs[-1][4]            # nothing drawn outside the boxes
            mids = [(a[2] + a[4]) / 2 for a in bs]
            assert mids == sorted(mids) and abs(W / 2 - (bs[0][1] + bs[0][3]) / 2) <= 1


def test_checklist_wraps_into_balanced_lines():
    lk = load_look("clean")
    C = checklist.numbers(lk)
    f = checklist.style_font(lk, {}, C["size"], C["weight"])
    room = C["max_width"] - 2 * C["pad_x"]
    text = "Your payment is more than principal and interest."
    greedy = checklist._greedy(("✅ " + text).split(), f, room)
    lines = checklist.wrap(text, f, room, "✅")
    assert len(lines) == len(greedy) == 2 and lines[0].startswith("✅ Your") and greedy[1] == "and interest."
    w = [checklist._width(ln, f) for ln in lines]
    g = [checklist._width(ln, f) for ln in greedy]
    assert min(g) / max(g) < 0.5 < 0.8 < min(w) / max(w)               # greedy leaves a stub; this evens them out
    assert checklist.wrap("One short point.", f, room, "✅") == ["✅ One short point."]
    assert checklist.wrap("First line\nsecond line as typed", f, room) == ["First line", "second line as typed"]


def test_checklist_limits_are_said_in_plain_words(clip):
    lk = load_look("clean")
    base = {**CHECKLIST, "clip": str(clip)}
    with pytest.raises(UserError, match="7 points: a checklist holds 6 at most"):
        listicle.check({**base, "items": ["A point."] * 7})
    with pytest.raises(UserError, match=r"the point .* needs \d lines: 2 is the most a checklist holds. Shorten it to about \d+ words"):
        listicle.card({**base, "items": base["items"][:3] + [
            "A lender will look at every single deposit in your bank statements for the last two full months "
            "before your closing date arrives."]}, lk)
    with pytest.raises(UserError, match=r"the title .* needs \d lines"):
        listicle.card({**base, "title": " ".join(["Buying your first home this year"] * 4)}, lk)
    with pytest.raises(UserError, match="is too wide for the frame in one piece"):
        listicle.card({**base, "items": ["See www.example.com/" + "a-very-long-address" * 4] + base["items"][:2]}, lk)
    tall = load_look("clean")
    tall["listicle"]["checklist"] = {**tall["listicle"]["checklist"], "pitch": 120, "min_size": 50}
    with pytest.raises(UserError, match="px tall and the feed-safe band .y300-1600. is 1300: cut a point"):
        listicle.card(base, tall)
    with pytest.raises(UserError, match="one list"):
        listicle.check({**base, "columns": [{"header": "A", "items": ["x"]}]})
    with pytest.raises(UserError, match="no layout 'grid'"):
        listicle.check({**base, "layout": "grid"})
    with pytest.raises(UserError, match="outside the feed-safe band"):
        listicle.card({**base, "center_y": 0.2}, lk)
    warned = listicle.check({**base, "items": base["items"][:2], "small": "Source: test", "punchline": ""})
    assert len(warned) == 3 and "only 2 points" in warned[0]
    # a point a little too long for two lines at the look's size gets smaller type, never under the look's floor
    longish = {**base, "items": ["Your lender will check your credit again a few days before closing, so keep it quiet."]
               + base["items"][:2]}
    blocks, C = checklist.fit(longish, lk)
    assert checklist.numbers(lk)["min_size"] <= C["size"] < checklist.numbers(lk)["size"]
    assert all(len(b[1]) <= 2 for b in blocks)


def _greens(img):
    import numpy as np
    a = np.array(img.convert("RGBA")).astype(int)
    return int(((a[..., 3] > 0) & (a[..., 1] > a[..., 0] + 40) & (a[..., 1] > a[..., 2] + 40)).sum())


def test_checklist_bullets_on_off_and_the_members_own():
    lk = load_look("clean")
    on = _greens(listicle.card(CHECKLIST, lk))
    assert on > 5 * 600                                                # five green check marks
    assert _greens(listicle.card({**CHECKLIST, "bullet": ""}, lk)) == 0
    assert _greens(listicle.card({**CHECKLIST, "bullet": False}, lk)) == 0
    assert _greens(listicle.card({**CHECKLIST, "bullet": "→"}, lk)) == 0
    own = {**CHECKLIST, "items": ["✅ " + CHECKLIST["items"][0]] + CHECKLIST["items"][1:]}
    assert abs(_greens(listicle.card(own, lk)) - on) < 50              # their own check mark is not doubled
    wide = [b for b in checklist.boxes(CHECKLIST, lk) if b[0] == "item"]
    bare = [b for b in checklist.boxes({**CHECKLIST, "bullet": ""}, lk) if b[0] == "item"]
    assert all(a[3] - a[1] > b[3] - b[1] for a, b in zip(wide, bare) if a[2] == b[2])   # the mark takes its room
    with pytest.raises(UserError):
        listicle.card({**CHECKLIST, "bullet": 3}, lk)


def test_checklist_check_mark_without_apple_emoji(monkeypatch):
    """Windows: the bundled emoji font draws the check mark, at the same size."""
    lk = load_look("clean")
    mac = checklist.boxes(CHECKLIST, lk)
    monkeypatch.setattr(xreel, "APPLE_EMOJI", Path("/nonexistent"))
    monkeypatch.setattr(xreel, "_EF", None)
    assert _greens(listicle.card(CHECKLIST, lk)) > 5 * 600
    assert all(abs(a[1] - b[1]) <= 3 and a[2] == b[2] for a, b in zip(mac, checklist.boxes(CHECKLIST, lk)))
    monkeypatch.undo()
    monkeypatch.setattr(xreel, "_EF", None)                            # back to this computer's own emoji font


def test_checklist_length_follows_the_reading():
    words = lambda n: " ".join(["word"] * n)                           # noqa: E731
    ref = {"layout": "checklist", "title": words(10), "items": [words(8), words(10), words(6), words(9), words(10)],
           "punchline": "📌 " + words(8)}
    assert checklist.words(ref) == 61 and listicle.duration_for(ref) == 10.0     # the reel it was measured from
    assert checklist.punchline_at(ref, 10.0) == 7.5
    assert listicle.duration_for({**ref, "items": [words(4)] * 3}) == 7.0
    assert listicle.duration_for({**ref, "items": [words(14)] * 6}) == 12.0
    assert listicle.duration_for({**ref, "duration": 9}) == 9.0
    assert checklist.punchline_at({**ref, "punchline_at": 0}, 10.0) == 0.0
    assert listicle.duration_for({"title": "t", "items": ["a"] * 12}) == 7.0     # the plain list keeps its 7 s


def test_checklist_draws_in_a_look_made_before_it_existed(tmp, avatar):
    """A member's look has no `checklist` block: the numbers come from the rest of the look, the title box is their
    accent colour, and the type is their font at a bold weight."""
    from gre import brand
    slug, _ = brand.make_look("Checklist Member", base="serif", accent="#155CFF")
    lk = load_look(slug)
    lk["listicle"].pop("checklist")
    C = checklist.numbers(lk)
    assert C["size"] == round(lk["size"] * 0.86) and C["pitch"] == round(C["size"] * 1.2) and C["weight"] >= 700
    assert C["title"]["box"][:3] == (21, 92, 255) and C["item"]["box"][:3] == (255, 255, 255)
    img = listicle.card(CHECKLIST, lk)
    first = checklist.boxes(CHECKLIST, lk)[0]
    assert img.getpixel((first[1] + 6, (first[2] + first[4]) // 2))[:3] == (21, 92, 255)
    assert load_look(slug)["listicle"]["checklist"]["size"] == 48      # and a new look copies the starter's block
    for name in LOOKS:                                                 # the bundled looks: red, white, black
        C = checklist.numbers(load_look(name))
        assert (C["title"]["box"][:3], C["item"]["box"][:3], C["punchline"]["box"][:3]) == \
               ((226, 35, 35), (255, 255, 255), (0, 0, 0))
