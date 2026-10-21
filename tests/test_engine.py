"""The engine's tests. Footage is synthetic (made by ffmpeg at test time), so no member's video is ever in the repo.
Run: uv run --group dev pytest -q"""
import json, os, subprocess
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


def test_yap_cut_and_render_keep_sound_on_picture(tmp, talk):
    flat = [{"w": f"word{i}.", "start": float(i), "end": i + 0.6, "ci": 0, "i": i, "clip": "talk.mov"} for i in range(6)]
    keep = {"segments": [{"from": 0, "to": 1}, {"from": 3, "to": 5}]}
    segs = cut.build(flat, keep, [str(talk)])
    assert len(segs) == 2                         # 0.4 s gaps stay inside a piece; the cut word splits it
    cuts = {"clips": [str(talk)], "segments": segs}
    out = tmp / "yap.mp4"
    lk = load_look("clean")
    caps = captions.images([{"text": "word one", "start": 0.0, "end": 1.0}], lk)
    t = title.layer({"lines": ["A test title"], "size": 80, "top": 330}, lk)
    render.render(cuts, out, captions=caps, title=t, label="v1", log=lambda *_: None)
    v = video_info(out)
    n = sum(render.frame_plan(segs))
    assert abs(v["duration"] - n / FPS) < 0.05
    a = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                                   "stream=duration", "-of", "json", str(out)], capture_output=True, text=True).stdout)
    assert abs(float(a["streams"][0]["duration"]) - n / FPS) < 0.06


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
