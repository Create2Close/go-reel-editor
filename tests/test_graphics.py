"""Tests for the yap graphics (headline card, rate chart, stat card, lower third), `gre headline` and `gre rates`.
No network: pages and rate files are small made-up fixtures, and the footage is made by ffmpeg at test time.
Run: uv run --group dev pytest -q"""
import json, os, subprocess
from datetime import date
from pathlib import Path
import numpy as np
import pytest

os.environ.setdefault("GRE_HOME", str(Path(__file__).parent / ".home"))
from gre import graphics as G, news, title as T, yap                              # noqa: E402
from gre.common import UserError, load_look, video_info, W, H, FPS, SAFE_TOP, SAFE_BOTTOM  # noqa: E402
from gre.qa import qa                                                             # noqa: E402

LOOKS = ("clean", "bold", "serif")
FIX = Path(__file__).parent / "fixtures"


# ---------------- timing: the words they say ----------------

def _words(text, gap=0.4):
    return [{"i": k, "w": w, "heard": w, "start": round(k * gap, 3), "end": round(k * gap + 0.3, 3)}
            for k, w in enumerate(text.split())]


SAID = "Rates fell again. Here's the headline: the 30-year went from 7.40% to 7.11%. Rates matter, so look at the chart."
PLAYED = _words(SAID)


def test_a_graphic_lands_on_the_words():
    g = {"type": "headline", "at": "here's the HEADLINE", "for": 4}
    start, end = G.when(g, PLAYED, PLAYED, 60.0)
    assert start == pytest.approx(3 * 0.4 - G.LEAD) and end == pytest.approx(start + 4)
    # punctuation, case, a hyphen and a per cent sign never stop a match
    assert G.when({"type": "stat", "at": "30 year", "for": 3}, PLAYED, PLAYED, 60.0)[0] == pytest.approx(7 * 0.4 - G.LEAD)
    assert G.when({"type": "stat", "at": "7.40", "for": 3}, PLAYED, PLAYED, 60.0)[0] == pytest.approx(10 * 0.4 - G.LEAD)
    # seconds work too, and "delay" shifts either kind
    assert G.when({"type": "stat", "at": 12, "delay": 0.5, "for": 3}, PLAYED, PLAYED, 60.0) == (12.5, 15.5)
    # a graphic near the end is cut off with the video, not pushed past it
    assert G.when({"type": "stat", "at": 12, "for": 3}, PLAYED, PLAYED, 14.0) == (12.0, 14.0)


def test_the_nth_time_they_say_it():
    first = G.when({"type": "stat", "at": "rates"}, PLAYED, PLAYED, 60.0)[0]
    second = G.when({"type": "stat", "at": "rates", "nth": 2}, PLAYED, PLAYED, 60.0)[0]
    assert first == 0.0 and second == pytest.approx(13 * 0.4 - G.LEAD)
    start, why = G.when({"type": "stat", "at": "rates", "nth": 3}, PLAYED, PLAYED, 60.0)
    assert start is None and '"rates" is said 2 times' in why


def test_words_that_were_cut_or_never_said_are_named():
    played = [w for w in PLAYED if w["i"] < 3 or w["i"] > 5]              # "Here's the headline:" was cut
    start, why = G.when({"type": "headline", "at": "here's the headline"}, played, PLAYED, 60.0)
    assert start is None and '"here\'s the headline" were cut from the video' in why
    start, why = G.when({"type": "headline", "at": "breaking news"}, played, PLAYED, 60.0)
    assert start is None and '"breaking news" are not said in the video' in why
    assert G.when({"type": "chart"}, played, PLAYED, 60.0)[0] is None
    assert "too close to the end" in G.when({"type": "chart", "at": 59}, played, PLAYED, 60.0)[1]


# ---------------- gre headline ----------------

LD_PAGE = """<html><head><title>Rates fall again | Example Wire</title>
<meta property="og:title" content="Mortgage rates fall for a fourth week - Example Wire">
<meta property="og:site_name" content="ExampleWire.com">
<script type="application/ld+json">{"@context": "https://schema.org", "@graph": [
 {"@type": "WebSite", "name": "Example Wire site"},
 {"@type": "NewsArticle", "headline": "Mortgage rates fall for the fourth straight week &amp; buyers notice",
  "datePublished": "2026-11-12T09:30:00-05:00", "publisher": {"@type": "Organization", "name": "Example Wire"}}]}
</script></head><body><h1>Example Wire</h1><h1>Mortgage rates fall for the fourth straight week</h1></body></html>"""

H1_PAGE = """<html><head><title>Home sales rise | The Example Post</title>
<meta content="The Example Post" property="og:site_name"><meta property='article:published_time' content='2026-11-03'>
</head><body><h1 class="hed">Home sales <em>rise</em> for the first time&nbsp;since spring</h1></body></html>"""

OG_PAGE = """<html><head><title>Example Daily</title>
<meta property="og:title" content="Builders cut prices - again | Example Daily">
<meta property="og:site_name" content="Example Daily"></head><body><div>no heading here</div></body></html>"""

DASH_PAGE = """<html><head><meta property="og:title" content="Fed holds rates - what it means – Example Daily">
<meta property="og:site_name" content="Example Daily"></head><body></body></html>"""

SHORT_LD_PAGE = """<html><head><script type="application/ld+json">{"@type": "Article",
 "headline": "A very long headline about mortgage rates, home prices, inventory and what buyers in every market sh..."}
</script></head><body><h1>A very long headline about mortgage rates, home prices, inventory and what buyers in every
 market should do next</h1></body></html>"""

ROBOT_PAGE = "<html><head><title>Just a moment...</title></head><body><h1>Just a moment...</h1></body></html>"


def test_headline_from_the_article_data():
    d = news.parse_headline(LD_PAGE, "https://www.examplewire.com/a/rates")
    assert d["headline"] == "Mortgage rates fall for the fourth straight week & buyers notice"
    assert d["outlet"] == "Example Wire" and d["date"] == "Nov 12, 2026"


def test_headline_from_the_main_heading_then_the_share_title():
    d = news.parse_headline(H1_PAGE, "https://examplepost.com/x")
    assert d == {"headline": "Home sales rise for the first time since spring", "outlet": "The Example Post",
                 "date": "Nov 3, 2026", "from": "the page's main heading"}
    d = news.parse_headline(OG_PAGE, "https://exampledaily.com/x")
    assert d["headline"] == "Builders cut prices - again" and d["outlet"] == "Example Daily" and d["date"] == ""
    # a dash inside the headline stays; only the outlet's own name is taken off the end
    assert news.parse_headline(DASH_PAGE, "https://exampledaily.com/y")["headline"] == "Fed holds rates - what it means"
    # a data headline that was cut short gives way to the full one on the page
    assert news.parse_headline(SHORT_LD_PAGE)["headline"].endswith("every market should do next")


def test_headline_never_invents(capsys, monkeypatch):
    assert news.parse_headline("<html><body><p>nothing</p></body></html>") == \
        {"headline": "", "outlet": "", "date": "", "from": ""}
    with pytest.raises(news.CouldNotRead):
        news.read_headline("https://example.com/a", get=lambda u: ROBOT_PAGE)
    with pytest.raises(news.CouldNotRead):
        news.fetch("not a link")                               # refused before any request is made

    class A:
        url = "https://example.com/a"
    def blocked(url):
        raise news.CouldNotRead("the site blocked the request: 403")

    monkeypatch.setattr(news, "fetch", blocked)
    assert news.cmd_headline(A) == 0                           # a page that cannot be read is not a crash
    assert "COULD NOT READ (the site blocked the request: 403)" in capsys.readouterr().out
    monkeypatch.setattr(news, "fetch", lambda url: H1_PAGE)
    assert news.cmd_headline(A) == 0
    out = capsys.readouterr().out
    assert "HEADLINE: Home sales rise for the first time since spring" in out
    assert "OUTLET: The Example Post" in out and "DATE: Nov 3, 2026" in out


# ---------------- gre rates ----------------

def test_rates_parse_both_files():
    fred = news.parse_rates((FIX / "rates-fred.csv").read_text(encoding="utf-8"))
    pmms = news.parse_rates((FIX / "rates-pmms.csv").read_text(encoding="utf-8").replace("\n", "\r\n"))
    assert fred == pmms and len(fred) == 70
    assert fred[-2:] == [("2026-11-05", 7.18), ("2026-11-12", 7.11)]
    assert news.parse_rates("observation_date,MORTGAGE30US\n2026-11-05,.\n2026-11-12,7.11\n") == [("2026-11-12", 7.11)]
    s = news.summary(fred)
    assert s["latest"] == ("2026-11-12", 7.11) and s["week"] == ("2026-11-05", 7.18)
    assert s["month"] == ("2026-10-15", 7.4) and s["year"] == ("2025-11-13", 6.24)
    assert s["high"][1] == 7.4 and s["low"] == ("2026-02-26", 5.98)


def test_payment_maths():
    assert round(news.payment(400000, 7.11)) == 2691
    assert round(news.payment(400000, 7.40)) == 2770
    assert round(news.payment(400000, 7.18)) == 2710
    assert news.parse_money("$400,000") == 400000 and news.parse_money("400k") == 400000
    with pytest.raises(UserError):
        news.parse_money("a lot")


def test_rates_cache_and_offline(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(news, "HOME", tmp_path)
    text = (FIX / "rates-fred.csv").read_text(encoding="utf-8")
    calls = []

    def online(url, agent=None):
        calls.append(url)
        return text

    def offline(url, agent=None):
        calls.append(url)
        raise news.CouldNotRead("no internet connection, or the site is down")

    with pytest.raises(UserError) as e:                        # offline, nothing saved: a plain problem
        news.load_rates(get=offline, today=date(2026, 11, 13))
    assert "could not get the mortgage rate data" in str(e.value) and len(calls) == 2     # FRED, then Freddie Mac
    d = news.load_rates(get=online, today=date(2026, 11, 13))
    assert d["series"][-1] == ("2026-11-12", 7.11) and d["via"] == "FRED" and not d["note"]
    assert json.loads((tmp_path / "rates.json").read_text(encoding="utf-8"))["fetched"] == "2026-11-13"
    calls.clear()
    assert news.load_rates(get=offline, today=date(2026, 11, 13))["series"][-1][1] == 7.11 and not calls   # today's copy
    d = news.load_rates(get=offline, today=date(2026, 11, 16))                              # offline, 3 days later
    assert d["series"][-1][1] == 7.11 and "saved 3 days ago" in d["note"]
    assert news.load_rates(refresh=True, get=online, today=date(2026, 11, 13))["note"] == "" and calls
    # FRED down, Freddie Mac's own file answers
    second = lambda url, agent=None: text if "freddiemac" in url else offline(url)
    assert news.load_rates(refresh=True, get=second, today=date(2026, 11, 14))["via"] == "Freddie Mac"

    class A:
        refresh, payment = False, "400000"
    saved = json.loads((tmp_path / "rates.json").read_text(encoding="utf-8"))
    (tmp_path / "rates.json").write_text(json.dumps(dict(saved, fetched="2026-01-02")), encoding="utf-8")
    monkeypatch.setattr(news, "fetch", offline)                # the command itself, offline with an old saved copy
    assert news.cmd_rates(A) == 0
    out = capsys.readouterr().out
    assert "LATEST: 7.11% (Nov 12, 2026)" in out and "1 WEEK AGO: 7.18% (Nov 5, 2026)" in out
    assert "LATEST 7.11%: $2,691 a month" in out and "4 WEEKS AGO 7.40%: $2,770 a month (+$79 vs latest)" in out
    assert "Freddie Mac PMMS" in out and "NOTE: could not reach" in out


# ---------------- the cards, in every look ----------------

@pytest.fixture(scope="module")
def series():
    return news.parse_rates((FIX / "rates-fred.csv").read_text(encoding="utf-8"))


HEAD = {"type": "headline", "headline": "Mortgage rates fall for the fourth straight week", "outlet": "Example Wire",
        "date": "Nov 12, 2026", "highlight": "fourth straight week"}
STAT = {"type": "stat", "from": "7.40%", "to": "7.11%", "label": "30-year fixed"}
THIRD = {"type": "lower_third", "name": "Jane Doe", "title": "Loan Officer", "line": "NMLS #000000"}
FACE = (390, 620, 300, 300)            # a face in the middle of the frame, room on both sides and above


def _ink(card):
    """How much of the card is not its plain background: > 0 means something was drawn."""
    a = card.img[card.m:card.m + card.h, card.m:card.m + card.w, :3].astype(int)
    return int((np.abs(a - a[2, 2]).sum(axis=2) > 60).sum())


@pytest.mark.parametrize("lk", LOOKS)
def test_every_graphic_draws_in_every_look(lk, series):
    look = load_look(lk)
    S = G.style(look)
    for g in (dict(HEAD, layout="above"), dict(HEAD, layout="full"), {"type": "chart", "layout": "above"},
              {"type": "chart", "layout": "full"}, STAT, dict(STAT, layout="above"), dict(STAT, layout="full"),
              {"type": "stat", "value": "$79", "label": "less a month"}, THIRD):
        card, x, y, lay, where, problems = G.place(g, S, look, [FACE], series)
        assert problems == [], (lk, g, problems)                       # the text fits and there is room
        assert card.img.shape[2] == 4 and _ink(card) > 400, (lk, g)    # not empty
        assert 40 <= x and x + card.w <= W - 40 and SAFE_TOP <= y and y + card.h <= SAFE_BOTTOM, (lk, g, x, y)
        if g is STAT:
            assert where.endswith("of the head")                       # beside the head when there is room
        if g is THIRD:
            assert (x, y) == (G.LEFT, SAFE_TOP)                        # one spot in every look: top left
        L = G.Layer(g["type"], lay, card, x, y, 1.0, 5.0, S)
        frame = np.full((H, W, 3), 128, np.uint8)
        L.draw(frame, L.landed())
        assert (frame != 128).any()
        if not L.full:                                                 # clear of the face and of the caption band
            assert not any(G._hit(L.rect, r) for r in G.face_rects([FACE]))
            top, bottom = G.cap_band(look)
            assert L.rect[3] <= top or L.rect[1] >= bottom
        first = np.full((H, W, 3), 128, np.uint8)
        L.draw(first, 0)                                               # the first frame is on its way in, not landed
        assert (first != frame).any()
        gone = np.full((H, W, 3), 128, np.uint8)
        L.draw(gone, L.n)                                              # after its last frame it draws nothing
        assert (gone == 128).all()


def test_the_three_looks_give_three_different_cards():
    cards = [G.style(load_look(lk)) for lk in LOOKS]
    assert len({(tuple(c["card"]), c["font"], c["radius"]) for c in cards}) == 3
    assert G._lum(cards[0]["card"]) > 0.8 > 0.1 > G._lum(cards[1]["card"])       # clean is light, bold is dark
    assert cards[2]["font"].startswith("Gelasio") and cards[2]["rule"]


def test_a_look_without_a_graphics_block_and_a_member_accent():
    lk = load_look("clean")
    lk.pop("graphics")
    plain = G.style(lk)
    assert plain["accent"][:3] == [226, 35, 35] and not plain["tab"]                       # the look's own red
    lk["font"] = "Gelasio-VF.ttf"                                                          # the member's own font
    lk["styles"]["accent"] = {"box": [21, 92, 255, 255], "ink": [255, 255, 255, 255]}
    lk["styles"]["accent2"] = {"box": [237, 63, 45, 255], "ink": [255, 255, 255, 255]}
    S = G.style(lk)
    assert S["accent"][:3] == [21, 92, 255] and S["highlight"][:3] == [21, 92, 255] and S["card"][:3] == [255, 255, 255]
    assert S["font"] == "Gelasio-VF.ttf" and S["tab"] and S["eyebrow"][:3] == [237, 63, 45] and S["dot"][:3] == [237, 63, 45]
    card = G.headline_card(HEAD, S, 960, 400)
    x0, y0, x1, y1 = card.rects[-1]
    strip = card.hi[y0:y1, x0:x1, :3].reshape(-1, 3).astype(int)
    wash = S["highlight_fill"][:3]                              # a highlighter: their colour washed over the card
    assert wash[2] > wash[0] and G.contrast(S["ink"], wash) >= 7
    assert (np.abs(strip - wash).sum(axis=1) < 30).mean() > 0.4
    rule = card.img[card.m + 3, card.m + card.w // 2, :3].astype(int)                      # the rule across the top
    assert np.abs(rule - [21, 92, 255]).sum() < 30
    # a navy accent on bold's dark panel cannot be read as type: the "to" value sits in an accent box instead
    dark = load_look("bold")
    dark["styles"]["accent"] = {"box": [10, 20, 80, 255], "ink": [255, 255, 255, 255]}
    assert G.style(dark)["accent_text"] is None
    assert _ink(G.stat_card(STAT, G.style(dark), 900, 400, "row")) > 400


def test_highlight_swipe_and_chart_draw_on():
    S = G.style(load_look("clean"))
    card = G.headline_card(HEAD, S, 960, 400)
    assert G.highlight_words(HEAD["headline"].split(), "Fourth straight WEEK") == {5, 6, 7}
    assert G.highlight_words(HEAD["headline"].split(), "fifth week") is None
    L = G.Layer("headline", "above", card, 60, 300, 0.0, 4.0, S)
    a0, an = L.act
    assert a0 >= L.ein + 3 and 10 <= an <= 12                      # starts after the card lands, takes 10-12 frames
    assert (L.content(a0 - 1) == card.img).all() and (L.content(a0 + an) == card.hi).all()
    mid = L.content(a0 + an // 2)
    assert (mid != card.img).any() and (mid != card.hi).any()
    assert 8 <= L.ein <= 14 and 6 <= L.eout <= 8
    pts = [(f"2026-01-{k + 1:02d}", 6.0 + k * 0.05) for k in range(20)]
    chart = G.chart_card({"type": "chart"}, S, 960, 250, pts)
    half, done = chart.frame(0.5), chart.frame(1.0)
    assert (half != done).any() and (done == chart.img).all()
    C = G.Layer("chart", "above", chart, 60, 300, 0.0, 5.0, S)
    assert 1.0 <= C.act[1] / FPS <= 1.4                             # the line draws in 1.0 to 1.4 seconds


def test_text_that_does_not_fit_is_a_problem_not_a_squeeze():
    look = load_look("clean")
    S = G.style(look)
    long = dict(HEAD, layout="above", highlight="", headline=" ".join(["Mortgage rates and home prices"] * 9))
    card, x, y, lay, where, problems = G.place(long, S, look, [FACE])
    assert any("does not fit" in p and '"layout": "full"' in p for p in problems)
    assert G.check_fields(dict(HEAD, highlight="not in it")) and G.check_fields({"type": "stat", "from": "1"})
    assert "split" in G.check_fields(dict(HEAD, layout="split"))[0]
    assert G.check_fields({"type": "banner"})


# ---------------- a yap with graphics, end to end ----------------

@pytest.fixture(scope="module")
def folder(tmp_path_factory, series):
    """A fake yap: 17 s of test pattern with tone bursts, and its 'transcript'."""
    d = tmp_path_factory.mktemp("yap")
    E = d / "edit"
    E.mkdir()
    expr = "0.5*sin(2*PI*300*t)*(lt(mod(t\\,1)\\,0.6))"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=17",
                    "-f", "lavfi", "-i", f"aevalsrc={expr}:s=48000:d=17", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(d / "talk.mov")], check=True)
    said = ("Hi there, it's Jane here today. Here's the headline. Look at the chart. From 7.40 to 7.11. "
            "Off the record. Call me today.").split()
    words = [{"w": w, "start": k * 0.7 + 0.05, "end": k * 0.7 + 0.5} for k, w in enumerate(said)]
    (E / "words.json").write_text(json.dumps({"clips": [{"clip": "talk.mov", "path": str(d / "talk.mov"),
                                                         "duration": 17.0, "words": words}]}), encoding="utf-8")
    # "Off the record." (words 17-19) is cut
    (E / "keep.json").write_text(json.dumps({"segments": [{"from": 0, "to": 16}, {"from": 20, "to": 22}], "cuts": [
        {"from": 17, "to": 19, "why": "aside"}]}), encoding="utf-8")
    (E / "rates.json").write_text(json.dumps({"fetched": "2026-11-13", "via": "test", "series": series}), encoding="utf-8")
    return d


def _write(folder, graphics):
    (folder / "edit" / "graphics.json").write_text(json.dumps({"graphics": graphics}), encoding="utf-8")


def _frame(video, t, w=540, h=960):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(h, w, 3).astype(int)


YES = {"lower_third": True}                 # a member who said yes to the name card


def test_graphics_check_and_draft(folder, capsys, monkeypatch):
    monkeypatch.setattr(G, "profile", lambda: YES)
    _write(folder, [dict(THIRD, at=0.2, **{"for": 2.5}),
                    dict(HEAD, at="here's the headline", layout="full", **{"for": 2.0}),
                    {"type": "chart", "at": "look at the chart", "layout": "above", "for": 3.0},
                    dict(STAT, at="7.40", **{"for": 1.5})])
    assert yap.main(["graphics", str(folder)]) == 0
    out = capsys.readouterr().out
    assert out.count("  ok ") == 4 and "FIX" not in out and "full screen" in out
    assert (folder / "edit" / "graphics-preview.png").exists()
    assert not yap.main(["draft", str(folder), "--label", "g"])
    assert "graphics: 4 on screen" in capsys.readouterr().out
    video = folder / "edit" / "drafts" / "draft-g.mp4"
    v = video_info(video)
    assert (v["w"], v["h"]) == (540, 960) and v["duration"] > 12
    items = G.build(folder / "edit", load_look("clean"), *_cut_parts(folder))
    full = next(it for it in items if it.kind == "headline")
    mid = _frame(video, (full.start + full.end) / 2)
    assert (mid[900:950, 20:520] > 235).all()                  # the full-screen card covers the test pattern
    after = _frame(video, full.end + 0.3)
    assert not (after[900:950, 20:520] > 235).all()            # and leaves again
    assert not yap.main(["draft", str(folder), "--label", "cut", "--no-captions"])      # the cut-only review copy
    assert "graphics:" not in capsys.readouterr().out


def _cut_parts(folder):
    from gre import words as wordsmod
    E = folder / "edit"
    cuts = json.loads((E / "cuts.json").read_text(encoding="utf-8"))
    d, flat = wordsmod.load(E)
    return cuts, yap._moves(E, cuts), flat, json.loads((E / "keep.json").read_text(encoding="utf-8"))


def test_problems_are_said_in_plain_words_and_never_dropped_quietly(folder, capsys, monkeypatch):
    monkeypatch.setattr(G, "profile", lambda: YES)
    _write(folder, [dict(HEAD, at="off the record", layout="full"),            # the member said it, but it was cut
                    {"type": "chart", "at": "the forecast", "layout": "full"},  # never said
                    dict(STAT, at="7.40", **{"for": 1.5}),                      # fine
                    {"type": "lower_third", "at": 0.2, "name": "Jane Doe", "line": "NMLS #000000", "for": 6},
                    dict(STAT, at=0.5, layout="full", **{"for": 3})])           # covers the lower third's moment
    assert yap.main(["graphics", str(folder)]) == 1
    out = capsys.readouterr().out
    assert 'FIX   1 headline: the words "off the record" were cut from the video' in out
    assert 'FIX   2 chart: the words "the forecast" are not said in the video' in out
    assert "  ok    3 stat" in out and "same place as the lower third (graphic 4)" in out
    assert not yap.main(["draft", str(folder), "--label", "p"])                # the draft still renders
    out = capsys.readouterr().out
    assert "FIX   1 headline" in out and "2 left out" in out
    assert (folder / "edit" / "drafts" / "draft-p.mp4").exists()
    (folder / "edit" / "graphics.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(UserError):
        yap.main(["graphics", str(folder)])


def test_a_graphic_on_the_face_is_a_fix_and_fails_the_final_check(folder, monkeypatch, capsys):
    """A head that fills the frame leaves no room above it or beside it: `above` says so and points to full screen,
    `full` is fine, and the final check fails while a graphic sits on the face."""
    monkeypatch.setattr(T, "face_boxes", lambda frames: [(190, 330, 700, 700)] * len(frames))
    _write(folder, [dict(HEAD, at="here's the headline", layout="above", **{"for": 2.5})])
    E = folder / "edit"
    items = G.build(E, load_look("clean"), *_cut_parts(folder))
    assert items[0].on_face and any("no clear space above the head" in p and '"layout": "full"' in p
                                    for p in items[0].problems)
    assert yap.main(["graphics", str(folder)]) == 1
    assert "FIX   1 headline: there is no clear space above the head" in capsys.readouterr().out
    bad = G.fixes(items)
    draft = folder / "edit" / "drafts" / "draft-g.mp4"
    if not draft.exists():
        yap.main(["draft", str(folder), "--label", "g"])
    capsys.readouterr()
    assert qa(str(draft), yap=False, also=bad) == 1
    assert "FAIL  graphic 1 (headline): there is no clear space above the head" in capsys.readouterr().out
    _write(folder, [dict(HEAD, at="here's the headline", layout="full", **{"for": 2.5}),
                    dict(STAT, at="7.40", layout="left", **{"for": 1.5})])
    items = G.build(E, load_look("clean"), *_cut_parts(folder))
    assert items[0].problems == [] and any("no room left of the head" in p for p in items[1].problems)


def test_captions_over_a_full_screen_card_take_the_cards_ink():
    """White outlined captions on a white card are hard to read: while the card is behind them they are drawn in
    the card's ink, with no outline. They are never hidden."""
    from gre import captions as C
    look = load_look("clean")
    S = G.style(look)
    card, x, y, lay, where, problems = G.place(dict(HEAD, layout="full"), S, look, [FACE])
    L = G.Layer("headline", lay, card, x, y, 2.0, 6.0, S)
    caps = C.images([{"text": "before the card", "start": 0.0, "end": 1.5}, {"text": "on the card", "start": 3.0, "end": 4.0}], look)
    G.captions_on_cards(caps, [L], look)
    assert "on_card" not in caps[0] and "on_card" in caps[1]
    img, cx, cy = G.caption_now(caps[1], [L], round(3.5 * FPS))
    assert img is caps[1]["on_card"][0]
    lit = img[img[..., 3] > 200][:, :3]
    assert len(lit) and lit.max() < 40                              # black type, no white fill
    assert G.caption_now(caps[1], [L], round(1.0 * FPS))[0] is caps[1]["img"]      # the card is not up yet
    assert L.backdrop(0)[0] > 0 and L.backdrop(30) == (0, H) and L.backdrop(L.n) is None


def test_lower_third_text_comes_from_the_profile(tmp_path, monkeypatch):
    from gre import common, cli
    monkeypatch.setattr(common, "HOME", tmp_path)
    assert cli.main(["profile", "--name", "Jane Doe", "--title", "Loan Officer", "--line", "NMLS #123456",
                     "--lower-third", "no"]) == 0
    pr = json.loads((tmp_path / "profile.json").read_text(encoding="utf-8"))
    assert pr["lower_third"] is False and pr["line"] == "NMLS #123456"
    assert G.lower_third_text({"type": "lower_third"}) == {"name": "Jane Doe", "title": "Loan Officer",
                                                           "line": "NMLS #123456"}
    assert G.lower_third_text({"type": "lower_third", "line": "Equal Housing Lender"})["line"] == "Equal Housing Lender"
    assert G.lower_third_off({"type": "lower_third"}) and "not said yes" in G.lower_third_off({"type": "lower_third"})
    assert cli.main(["profile", "--lower-third", "yes"]) == 0
    assert G.lower_third_off({"type": "lower_third"}) is None


def test_the_name_card_is_never_a_default_and_never_holds_a_reel(folder, capsys, monkeypatch):
    """Off unless the member said yes; with a yes but no name it is left out too. Both are notes, not problems: the
    check passes, the draft renders, the final check has nothing to fail on. With no entry, nothing mentions it."""
    stat = dict(STAT, at="7.40", **{"for": 1.5})
    for pr, why in (({}, "has not said yes"), ({"lower_third": False, "name": "Jane Doe"}, "has not said yes"),
                    ({"lower_third": True}, "no name is saved")):
        monkeypatch.setattr(G, "profile", lambda pr=pr: pr)
        _write(folder, [{"type": "lower_third", "at": 0.5}, stat])
        assert yap.main(["graphics", str(folder)]) == 0                    # not a problem
        out = capsys.readouterr().out
        assert "note  1 lower third: left out" in out and why in out and "FIX" not in out and "ok    2 stat" in out
        items = G.build(folder / "edit", load_look("clean"), *_cut_parts(folder))
        assert items[0].layer is None and G.fixes(items) == [] and len(G.layers(items)) == 1
    monkeypatch.setattr(G, "profile", lambda: {"lower_third": True, "name": "Jane Doe", "line": "NMLS #000000"})
    assert yap.main(["graphics", str(folder)]) == 0
    assert "ok    1 lower third" in capsys.readouterr().out               # said yes, has a name: drawn
    monkeypatch.setattr(T, "face_boxes", lambda frames: [(190, 330, 700, 700)] * len(frames))
    _write(folder, [{"type": "lower_third", "at": 0.5}])                   # no room above a head this close
    assert yap.main(["graphics", str(folder)]) == 0
    assert "note  1 lower third: left out: there is no clear space" in capsys.readouterr().out
    monkeypatch.undo()
    _write(folder, [stat])                                                 # no entry: no warning, no nagging
    assert yap.main(["graphics", str(folder)]) == 0
    out = capsys.readouterr().out.lower()
    assert "lower third" not in out and "nmls" not in out and "name card" not in out and "note" not in out


def test_the_sample_sheet_shows_a_name_card_only_after_a_yes(monkeypatch):
    from PIL import Image
    base = Image.new("RGBA", (W, H), (90, 100, 110, 255))
    look = load_look("clean")
    shots = {}
    for key, pr in (("unset", {"name": "Jane Doe"}), ("no", {"name": "Jane Doe", "lower_third": False}),
                    ("yes", {"name": "Jane Doe", "lower_third": True, "line": "NMLS #000000"})):
        monkeypatch.setattr(G, "profile", lambda pr=pr: pr)
        shots[key] = np.array(G.samples(look, base)[0])
    assert (shots["unset"] == shots["no"]).all()
    assert (shots["yes"] != shots["no"]).any()
    spot = (slice(1100, 1400), slice(40, 700))                              # where the sheet puts the name card
    assert (shots["no"][spot][..., :3] == [90, 100, 110]).all()
