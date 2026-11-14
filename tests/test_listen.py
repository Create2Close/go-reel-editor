"""Tests for 0.2.1: the editor hears the take (sound decides, not the transcript), listens back to its own cut, and
writes rates, money and the comment word the way a caption should. No transcriber runs here (GRE_LISTEN=0): the
comparison is tested on word lists, the sound side on tones made by ffmpeg.
Run: uv run --group dev pytest -q"""
import json, os, subprocess
from pathlib import Path
import numpy as np
import pytest

os.environ.setdefault("GRE_HOME", str(Path(__file__).parent / ".home"))
os.environ["GRE_LISTEN"] = "0"
from gre import captions, cut, hear, listen, plan, render                      # noqa: E402
from gre.common import UserError, load_look, FPS                                # noqa: E402


@pytest.fixture(scope="module")
def take(tmp_path_factory):
    """A fake take, 8 s: sound at 0-0.6, 1-1.6, 4-4.6, 5-5.6 and 6-6.6 s. From 1.6 to 4.0 s nobody speaks."""
    p = tmp_path_factory.mktemp("listen") / "take.mov"
    on = "+".join(f"between(t\\,{a}\\,{a + 0.6})" for a in (0, 1, 4, 5, 6))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=540x960:r=30:d=8", "-f", "lavfi",
                    "-i", f"aevalsrc=0.5*sin(2*PI*300*t)*({on})+0.0005*sin(2*PI*90*t):s=48000:d=8", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", p], check=True)
    return p


def _word(i, w, a, b):
    return {"w": w, "start": a, "end": b, "ci": 0, "i": i, "clip": "take.mov"}


# ---------------- the sound ----------------

def test_the_waveform_is_cut_into_takes(take):
    env = hear.envelope(hear.load(take))
    isl = hear.islands(env)
    assert len(isl) == 5
    assert [round(a) for a, _ in isl] == [0, 1, 4, 5, 6]
    utt = hear.utterances(isl)                          # 0.4 s apart is one breath; 2.4 s apart is another take
    assert len(utt) == 2 and utt[0][1] < 2.0 and utt[1][0] > 3.5
    sil = hear.silences(env, shortest=0.5)
    assert len(sil) == 2 and sil[0][0] == pytest.approx(1.6, abs=0.05) and sil[0][1] == pytest.approx(4.0, abs=0.05)
    assert hear.sound(env, 0, 8) == pytest.approx(3.0, abs=0.15)


def test_a_take_with_no_silence_is_still_cut_to_what_the_transcriber_can_read():
    rng = np.random.default_rng(1)
    env = -20 + rng.normal(0, 1, 7000)                  # 70 s of sound with no gap in it
    env[4000:4030] = -32                                # one slightly quieter moment at 40 s
    utt = hear.fit(hear.utterances(hear.islands(env)), env)
    assert len(utt) >= 3 and all(b - a <= 28.0 for a, b in utt)
    assert utt[0][0] == 0.0 and utt[-1][1] == pytest.approx(70.0, abs=0.01)
    assert any(abs(b - 40.15) < 0.2 for _, b in utt)    # it was cut at the quiet moment
    assert all(x[1] == y[0] for x, y in zip(utt, utt[1:]))


def test_how_long_a_written_word_takes_to_say():
    assert hear.spoken("payment,") == 1
    assert hear.spoken("$400,000") == 4                 # four hundred thousand dollars
    assert hear.spoken("7.11%") == 5                    # seven point one one percent
    assert hear.spoken("30-year") == 2


# ---------------- the cut is closed on the sound, not on the word times ----------------

def test_a_word_timed_across_a_silence_does_not_leave_dead_air(take):
    # the transcript says "gone" lasts from 1.0 to 4.6 s: it swallowed 2.4 s of silence (and whatever was missed)
    flat = [_word(0, "already", 0.0, 0.6), _word(1, "gone.", 1.0, 4.6), _word(2, "Next.", 5.0, 5.6)]
    notes = []
    segs = cut.build(flat, {"segments": [{"from": 0, "to": 2}]}, [str(take)], log=notes.append)
    total = sum(s["end"] - s["start"] for s in segs)
    assert 3.3 < total < 3.7                            # two pairs of bursts and their room tone, not 5.75 s
    for s in segs:                                      # no piece holds a silence of half a second
        assert not cut.Envelope(take).silences(s["start"], s["end"])
    assert [(s["first_word"], s["last_word"]) for s in segs] == [(0, 1), (2, 2)]     # every word still has a piece
    assert sorted({i for s in segs for i in range(s["first_word"], s["last_word"] + 1)}) == [0, 1, 2]


def test_a_dropped_stretch_never_plays(take):
    flat = [_word(0, "one", 4.0, 4.6), _word(1, "two", 5.0, 5.6), _word(2, "three", 6.0, 6.6)]
    keep = {"segments": [{"from": 0, "to": 2}], "drop": [{"from": 4.8, "to": 5.8, "why": "a retake the words missed"}]}
    segs = cut.build(flat, keep, [str(take)], log=lambda *_: None)
    assert all(s["end"] <= 4.8 or s["start"] >= 5.8 for s in segs)
    assert [(s["first_word"], s["last_word"]) for s in segs] == [(0, 0), (2, 2)]
    with pytest.raises(UserError, match="after"):
        cut.build(flat, {"segments": [{"from": 0, "to": 2}], "drop": [{"from": 5, "to": 4}]}, [str(take)])
    with pytest.raises(UserError, match="clip"):
        cut.build(flat, {"segments": [{"from": 0, "to": 2}], "drop": [{"clip": "x.mov", "from": 4, "to": 5}]},
                  [str(take)])


def test_where_a_moment_of_the_cut_sits_in_the_take():
    segs = [{"clip": "a.mov", "start": 10.0, "end": 12.0}, {"clip": "a.mov", "start": 30.0, "end": 33.0}]
    assert cut.source_time(segs, 1.0) == ("a.mov", 11.0)
    assert cut.source_time(segs, 2.5) == ("a.mov", 30.5)
    assert cut.source_time(segs, 99) == ("a.mov", 33.0)


# ---------------- listening back ----------------

def _expected(text, gap=0.4):
    return [{"i": k, "w": w, "heard": w, "start": round(k * gap, 3), "end": round(k * gap + 0.3, 3)}
            for k, w in enumerate(text.split())]


def _heard(text, gap=0.4, shift=0.0):
    return [{"w": w, "start": round(k * gap + shift, 3), "end": round(k * gap + 0.3 + shift, 3)}
            for k, w in enumerate(text.split())]


def test_a_cut_that_plays_what_it_should_passes_and_takes_the_heard_times():
    exp = _expected("On a $400,000 loan, that's $79 a month.")
    times, fixes, notes = listen.compare(exp, _heard("on a 400,000 loan that's 79 a month", shift=0.1))
    assert not fixes and not notes
    assert times[0] == [0.1, 0.4] and len(times) == len(exp)        # $ and punctuation never break the match


def test_a_retake_left_in_the_cut_is_caught():
    exp = _expected("Four weeks ago, the average 30-year rate was 7.4%. The highest in a year.")
    got = _heard("Four weeks ago, the average 30-year rate. Four weeks ago, the average 30-year rate was 7.4%. "
                 "The highest in a year.")
    segs = [{"clip": "take.mov", "ci": 0, "start": 58.0, "end": 70.0, "first_word": 0, "last_word": len(exp) - 1}]
    times, fixes, notes = listen.compare(exp, got, segs)
    text = "\n".join(fixes)
    assert "not in the cut" in text and "Four weeks ago" in text
    assert '"drop"' in text and "take.mov" in text                   # it says where, and how to cut it
    assert "later than the cut expects" in text                      # and that everything after it has slipped


def test_words_that_are_not_heard_are_caught():
    exp = _expected("And as of November 12th, it's 7.11%. On a $400,000 loan, that's $79 a month.")
    times, fixes, notes = listen.compare(exp, _heard("And as of November 12th, it's 7.11%."))
    assert any("not heard there" in f and "$79" in f for f in fixes)


def test_one_word_heard_another_way_is_a_note_not_a_fix():
    exp = _expected("yes, the buy downs are still pretty high")
    times, fixes, notes = listen.compare(exp, _heard("yes, the buydowns are still petty high"))
    assert not fixes and len(notes) == 1 and "petty" in notes[0]     # "buy downs" / "buydowns" is the same words
    assert 2 in times and 6 in times                                 # and every word still gets its time


def test_dead_air_is_measured_without_a_transcriber(take, tmp_path):
    flat = [_word(0, "one", 1.0, 1.6), _word(1, "two", 4.0, 4.6)]
    cuts = {"clips": [str(take)], "segments": [{"clip": "take.mov", "ci": 0, "start": 0.9, "end": 4.7,
                                                "first_word": 0, "last_word": 1, "group": 0}]}
    res = listen.run(tmp_path, cuts, flat, {"segments": [{"from": 0, "to": 1}]})
    assert res["listened"] is False
    assert len(res["fix"]) == 1 and "dead air" in res["fix"][0] and "2.4 s" in res["fix"][0]
    # the same words through the real cut: nothing to fix
    segs = cut.build(flat, {"segments": [{"from": 0, "to": 1}]}, [str(take)], log=lambda *_: None)
    assert not listen.run(tmp_path, {"clips": [str(take)], "segments": segs}, flat, {})["fix"]


def test_the_listen_back_is_kept_with_the_cut_it_heard(take, tmp_path):
    flat = [_word(0, "one", 1.0, 1.6), _word(1, "two", 4.0, 4.6)]
    segs = cut.build(flat, {"segments": [{"from": 0, "to": 1}]}, [str(take)], log=lambda *_: None)
    p = cut.write(tmp_path, segs, [str(take)])
    res = listen.ensure(tmp_path, p, flat, {})
    assert (tmp_path / "heard.json").exists() and res["cut"] == listen.cut_id(json.loads(p.read_text()))
    (tmp_path / "heard.json").write_text(json.dumps(dict(res, marker=1)))
    assert listen.ensure(tmp_path, p, flat, {}).get("marker") == 1   # the same cut is not heard twice
    segs[0]["end"] += 0.2
    p = cut.write(tmp_path, segs, [str(take)])
    assert "marker" not in listen.ensure(tmp_path, p, flat, {})      # a different cut is


def test_a_checked_word_can_be_accepted_without_listening_again(take, tmp_path):
    flat = [_word(0, "It's", 1.0, 1.3), _word(1, "7.11%.", 1.3, 1.6)]
    segs = cut.build(flat, {"segments": [{"from": 0, "to": 1}]}, [str(take)], log=lambda *_: None)
    p = cut.write(tmp_path, segs, [str(take)])
    cuts = json.loads(p.read_text())
    heard = [{"w": "It's", "start": 0.1, "end": 0.3}, {"w": "7.1.", "start": 0.3, "end": 0.6}]
    (tmp_path / "heard.json").write_text(json.dumps({"cut": listen.cut_id(cuts), "listened": True, "silences": [],
                                                     "words": heard}))
    res = listen.ensure(tmp_path, p, flat, {})
    assert len(res["fix"]) == 1 and "number" in res["fix"][0] and "heard_ok" in res["fix"][0]
    res = listen.ensure(tmp_path, p, flat, {"heard_ok": ["7.11%"]})
    assert not res["fix"] and res["notes"]


def test_the_cut_is_read_back_in_its_own_pieces():
    ch = listen.chunks([2.0, 0.4, 3.5, 0.3, 0.3, 9.0, 1.0, 4.0, 1.3])
    assert ch[0][0] == 0.0 and ch[-1][1] == pytest.approx(21.8)
    assert all(x[1] == y[0] for x, y in zip(ch, ch[1:]))            # no sound is skipped, none is read twice
    assert all(b - a >= 3.0 for a, b in ch)                          # no piece too short to hear right, the last too
    ch = listen.chunks([5.0, 7.5, 7.9, 1.3])                         # a short last piece after one that was full
    assert ch == [[0.0, 5.0], [5.0, 12.5], [12.5, 21.7]]


def test_a_clipped_word_and_a_clipped_number_are_fixes():
    exp = _expected("I'm not telling you it's cheap. The rate was 7.4%. The highest in a year.")
    times, fixes, notes = listen.compare(exp, _heard("I'm not telling you it's The rate was 7. The highest in a year."))
    text = "\n".join(fixes)
    assert len(fixes) == 2 and '"cheap."' in text and "7.4%" in text and "number" in text


def test_a_word_is_not_called_clipped_where_nothing_was_cut():
    exp = _expected("On a $400,000 loan, that's $79 a month. Same house.")
    got = _heard("On a $400,000. That's $79 a month. Same house.")
    one = [{"clip": "t.mov", "ci": 0, "start": 105.3, "end": 109.3, "first_word": 0, "last_word": 7},
           {"clip": "t.mov", "ci": 0, "start": 126.0, "end": 127.0, "first_word": 8, "last_word": 9}]
    times, fixes, notes = listen.compare(exp, got, one)
    assert not fixes and any("loan" in n and "nothing was cut" in n for n in notes)
    two = [dict(one[0], end=106.6, last_word=3), dict(one[0], start=107.0, first_word=4), one[1]]
    assert any("loan" in f for f in listen.compare(exp, got, two)[1])          # a cut right after it: check it
    touching = [dict(one[0], end=106.6, last_word=3), dict(one[0], start=106.6, first_word=4), one[1]]
    assert not listen.compare(exp, got, touching)[1]                           # two pieces that play straight through


def test_drift_needs_a_run_of_words_not_one_small_word():
    exp = _expected("the number you walked away from is already gone")
    got = _heard("the number you walked away from is already gone")
    got[0]["start"] -= 0.5                                           # one small word placed early by the aligner
    assert not listen.compare(exp, got)[1]
    for w in got[3:]:
        w["start"] += 1.0                                            # everything from "walked" on plays a second late
    assert any("later than the cut expects" in f for f in listen.compare(exp, got)[1])


def test_a_pause_inside_a_number_does_not_cost_its_second_half(take):
    # "7.4%" is one written word: said "seven ... point four percent", with the pause the take has from 1.6 to 4.0 s
    flat = [_word(0, "was", 0.0, 0.6), _word(1, "7.4%.", 1.0, 4.6), _word(2, "Next.", 6.0, 6.6)]
    segs = cut.build(flat, {"segments": [{"from": 0, "to": 1}]}, [str(take)], log=lambda *_: None)
    assert len(segs) == 2 and segs[1].get("more") and segs[1]["start"] > 3.8 and segs[1]["end"] > 4.6
    played = captions.played_words(flat, {"segments": segs}, {})
    assert [p["i"] for p in played] == [0, 1]                        # the word is still shown once
    assert cut.summary(segs, flat)["words"] == 2


def test_an_edge_goes_to_the_end_of_the_sound_not_of_the_word_time(take):
    # the transcript ends "gone." at 5.2 s; the sound it sits in runs to 5.6 s
    flat = [_word(0, "already", 4.0, 4.6), _word(1, "gone.", 5.0, 5.2)]
    segs = cut.build(flat, {"segments": [{"from": 0, "to": 1}]}, [str(take)], log=lambda *_: None)
    assert segs[-1]["end"] == pytest.approx(5.75, abs=0.05)
    # ... but never into the next word, when there is one
    flat.append(_word(2, "Next.", 5.3, 5.6))
    segs = cut.build(flat, {"segments": [{"from": 0, "to": 1}]}, [str(take)], log=lambda *_: None)
    assert segs[-1]["end"] <= 5.3


# ---------------- a rate takes %, money takes $ ----------------

@pytest.mark.parametrize("said,shown", [
    ("Rates? It's seven point one one today", "Rates? It's 7.11% today"),
    ("the rate was seven point four zero percent.", "the rate was 7.40%."),
    ("at six point eight seven five percent", "at 6.875%"),
    ("the rate was 7.4 percent", "the rate was 7.4%"),
    ("rates: yes, 7.11 is still pretty high", "rates: yes, 7.11% is still pretty high"),
    ("or about 940 dollars a year.", "or about $940 a year."),
    ("On a 400 thousand dollar loan, that's 79 dollars a month.", "On a $400,000 loan, that's $79 a month."),
    ("On a $400,000 loan, that's 79 a month.", "On a $400,000 loan, that's $79 a month."),
    ("four hundred thousand dollars", "$400,000"),
    ("they put 20 grand down", "they put $20,000 down"),
    ("it cost 1.2 million dollars.", "it cost $1.2 million."),
    ("seven percent", "7%"),
])
def test_rates_get_a_percent_sign_and_money_a_dollar_sign(said, shown):
    assert " ".join(t for t in captions.shown(said.split()) if t) == shown


@pytest.mark.parametrize("said", [
    "I close 12 a month",                               # loans, not dollars: no money in the sentence
    "at one point two people called",                   # not 1.2
    "the house is 2.5 miles away and rates are up",     # a decimal with a unit is not a rate
    "we looked at 3 homes in 2026",
    "it was 7.11 out of ten",                           # nothing here talks rates
])
def test_numbers_that_are_neither_stay_as_they_are(said):
    assert " ".join(t for t in captions.shown(said.split()) if t) == said


def test_a_number_can_be_left_alone_on_request(tmp_path):
    ct = tmp_path / "captions.txt"
    ct.write_text("# One caption per line\n#ok 7.11 questions\nrates: version 7.11 is out\n")
    ok = captions.parse_ok(ct)
    assert captions.shown("rates: version 7.11 is out".split(), ok)[2] == "7.11"
    assert not captions.figure_problems(captions.parse(ct), ok)


# ---------------- the word a call to action asks for ----------------

@pytest.mark.parametrize("said,word", [
    ("Just comment rates and I'll send you yours.", "rates"),
    ("Comment RATES below", "RATES"),
    ("DM me the word rates", "rates"),
    ("DM me rates and I'll send it", "rates"),
    ("comment the word buydown, and I'll send the guide", "buydown,"),
    ("type rates in the comments", "rates"),
    ("drop the word guide below", "guide"),
    ("Comment yes if you want it", "yes"),
])
def test_the_comment_word_is_found(said, word):
    toks = said.split()
    assert [toks[i] for i in captions.keyword(toks)] == [word]


@pytest.mark.parametrize("said", [
    "comment below and tell me",
    "leave a comment and follow",
    "DM me anytime",
    "DM me your questions",
    "if rates drop again and you wait",
    "read the comment section",
    "I'll comment more on that later",
    "send me a message today",
])
def test_ordinary_sentences_have_no_comment_word(said):
    assert not captions.keyword(said.split())


def test_captions_write_the_comment_word_in_bold_capitals_and_check_it():
    lk = load_look("clean")
    played = [{"i": k, "w": w, "heard": w, "start": k * 0.4, "end": k * 0.4 + 0.3}
              for k, w in enumerate("Yes, 7.11 is high. Just comment rates and I'll send you yours.".split())]
    lines = captions.draft(played, lk)
    text = " | ".join(lines)
    assert "**RATES**" in text and "7.11%" in text
    caps, problems, hard = captions.build(lines, played, lk)
    assert not hard and len(caps) == len(lines)                      # what the editor writes passes its own check
    caps, problems, hard = captions.build(["Yes, 7.11 is high", "Just comment rates", "and I’ll send you yours"],
                                          played, lk)
    text = "\n".join(hard)
    assert "7.11%" in text and "**RATES**" in text and len(hard) == 2
    caps, problems, hard = captions.build(["Yes, 7.11% is high", "Just comment **RATES**", "and I’ll send you yours"],
                                          played, lk)
    assert not hard
    assert caps[0]["start"] == pytest.approx(0.0, abs=0.05)          # % and ** never move a caption off its words


# ---------------- the first cut ----------------

def _flat(text, gap=0.35):
    return [{"w": w, "start": round(i * gap, 3), "end": round(i * gap + 0.3, 3), "ci": 0, "i": i, "clip": "a.mov"}
            for i, w in enumerate(text.split())]


@pytest.mark.parametrize("text,expect", [
    ("And that, and that's the national average.", "and that's the national average."),
    ("See the spike? That's October. That's October. That's when you stopped.",
     "See the spike? That's October. That's when you stopped."),
    ("That's it. That's the whole pitch.", "That's it. That's the whole pitch."),
    ("Mortgage rate, mortgage rates just dropped for the fourth week in a row. Mortgage rates, mortgage rates just "
     "dropped four weeks in a row.", "mortgage rates just dropped four weeks in a row."),
    ("And as of November 12th, it's only seven. And as of, and as of November 12th, it's 7.1%.",
     "and as of November 12th, it's 7.1%."),
])
def test_the_first_cut_knows_more_kinds_of_repeat(text, expect):
    f = _flat(text)
    keep, cuts = plan.plan_unscripted(f)
    assert " ".join(f[i]["w"] for i in keep) == expect


def test_a_script_is_matched_however_the_numbers_are_written():
    rec = ("And as of November 12th, it's only seven. And as of November 12th, it's 7.11%. "
           "On a $400,000 loan, that's $79 a month.")
    script = "As of November 12th, it's seven point one one. On a 400 thousand dollar loan, that's 79 dollars a month."
    f = _flat(rec)
    chosen, display, notes = plan.plan_scripted(f, plan.script_sentences(script))
    kept = sorted({i for _, k in chosen for i in k})
    assert " ".join(f[i]["w"] for i in kept) == "as of November 12th, it's 7.11%. On a $400,000 loan, that's $79 a month."
    assert not any("no complete take" in n for n in notes)
    shown = " ".join(display[i] for i in kept)
    assert "$400,000 loan," in shown and "$79 a month." in shown and "7.11" in shown
    # the last word of a line heard another way is still that line's last word
    f = _flat("As of November 12th, it's 7.1%. On a $400,000 loan, that's $79 a month.")
    chosen, display, notes = plan.plan_scripted(f, plan.script_sentences(script))
    assert [f[i]["w"] for i in chosen[0][1]][-1] == "7.1%." and display[chosen[0][1][-1]] == "7.11."


def test_a_second_go_inside_a_scripted_line_replaces_the_first():
    rec = ("If you stopped in October because of the payment, the number you walked away from. Let me do that again. "
           "The number you walked away from is already gone.")
    script = "If you stopped in October because of the payment, the number you walked away from is already gone."
    f = _flat(rec)
    chosen, display, notes = plan.plan_scripted(f, plan.script_sentences(script))
    kept = [i for _, k in chosen for i in k]
    said = " ".join(f[i]["w"] for i in kept)
    assert said == "If you stopped in October because of the payment, The number you walked away from is already gone."
    assert kept == sorted(kept) and "again" not in said


def test_a_script_number_written_out_is_shown_as_a_figure():
    assert captions.shown(["was", "at seven point four zero percent."]) == ["was", "at 7.40%."]


# ---------------- the tail of a cut word ----------------

@pytest.fixture(scope="module")
def restart(tmp_path_factory):
    """"Mortgage rates, | mortgage rates just dropped": the first go ends at 1.0 s, its last sound (an s) trails to
    1.12 s, then half a second of nothing, then the second go from 1.7 s."""
    p = tmp_path_factory.mktemp("restart") / "restart.mov"
    on = "between(t\\,0.2\\,1.0)+0.3*between(t\\,1.0\\,1.12)+between(t\\,1.7\\,3.0)"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=540x960:r=30:d=4", "-f", "lavfi",
                    "-i", f"aevalsrc=0.5*sin(2*PI*300*t)*({on})+0.0005*sin(2*PI*90*t):s=48000:d=4", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", p], check=True)
    return p


def _w(i, w, a, b):
    return {"w": w, "start": a, "end": b, "ci": 0, "i": i, "clip": "restart.mov"}


def test_the_tail_of_a_cut_word_is_caught_at_the_joint(restart, tmp_path):
    # as the aligner times it: "mortgage" starts the moment "rates," ends, so its span opens with the s
    flat = [_w(0, "Mortgage", 0.2, 0.6), _w(1, "rates,", 0.6, 1.0), _w(2, "mortgage", 1.0, 2.2), _w(3, "rates", 2.2, 3.0)]
    keep = {"segments": [{"from": 2, "to": 3}]}
    segs = cut.build(flat, keep, [str(restart)], log=lambda *_: None)
    res = listen.run(tmp_path, {"clips": [str(restart)], "segments": segs}, flat, keep)
    assert len(res["fix"]) == 1 and "stray sound" in res["fix"][0] and '"rates,"' in res["fix"][0]
    assert not listen.judge(res, {"clips": [str(restart)], "segments": segs}, flat, dict(keep, heard_ok=["mortgage"]))["fix"]
    # with the boundary where the sound puts it (what the transcriber now writes), the tail is not in the cut at all
    flat[1]["end"], flat[2]["start"] = 1.12, 1.7
    segs = cut.build(flat, keep, [str(restart)], log=lambda *_: None)
    assert len(segs) == 1 and segs[0]["start"] == pytest.approx(1.64, abs=0.03)
    assert not listen.run(tmp_path, {"clips": [str(restart)], "segments": segs}, flat, keep)["fix"]


def test_a_cut_does_not_reach_back_into_a_cut_word_that_runs_straight_on(restart):
    # no gap at all between the cut word and the kept one (0.2-1.0 is one sound): the start stays at the word
    flat = [_w(0, "the", 0.2, 0.6), _w(1, "the", 0.6, 1.0)]
    segs = cut.build(flat, {"segments": [{"from": 1, "to": 1}]}, [str(restart)], log=lambda *_: None)
    assert segs[0]["start"] >= 0.55


def test_figures_are_spelled_the_way_they_are_said():
    said = {"$400,000": "four hundred thousand dollars", "7.11%.": "seven point one one percent",
            "30-year": "thirty year", "12th,": "twelve", "$79": "seventy nine dollars", "2026": "twenty twenty six",
            "6.875%": "six point eight seven five percent", "payment,": "payment,"}
    for written, spoken in said.items():
        assert hear.spell(written) == spoken


def test_a_word_boundary_moves_to_where_the_sound_puts_it(restart):
    env = hear.envelope(hear.load(restart))
    thr = hear.threshold(env)
    # the aligner's version: "mortgage" starts the moment "rates," ends (1.0 s), and the s trails to 1.12 s
    words = [{"w": "Mortgage", "start": 0.2, "end": 0.6}, {"w": "rates,", "start": 0.6, "end": 1.0},
             {"w": "mortgage", "start": 1.0, "end": 2.2}, {"w": "rates", "start": 2.2, "end": 3.0}]
    hear.settle(words, env, thr)
    assert words[1]["end"] == pytest.approx(1.12, abs=0.03)          # the s belongs to the word it ends
    assert words[2]["start"] == pytest.approx(1.7, abs=0.03)         # and the next word starts after the gap
    assert words[3] == {"w": "rates", "start": 2.2, "end": 3.0}      # nothing else moves
    # a figure is left alone: a pause inside "7.4%" (seven ... point four percent) is its own
    words = [{"w": "was", "start": 0.2, "end": 1.0}, {"w": "7.4%.", "start": 1.0, "end": 3.0}]
    hear.settle(words, env, thr)
    assert words[1]["start"] == 1.0


def test_a_wrong_word_then_a_long_stop_then_the_line_again_is_a_retake():
    f = _flat("Lenders look at three things. Credit has the most ways. Cash has the most ways around it. A gift.")
    for w in f[10:]:
        w["start"] += 3.4; w["end"] += 3.4                           # the stop after "ways."
    keep, cuts = plan.plan_unscripted(f)
    assert " ".join(f[i]["w"] for i in keep) == "Lenders look at three things. Cash has the most ways around it. A gift."
    f = _flat("Credit takes the most time. Income takes the most work too.")     # no stop: two lines, both stay
    keep, cuts = plan.plan_unscripted(f)
    assert len(keep) == len(f)


def test_a_comment_word_of_two_words_is_found_when_the_video_writes_it_as_one():
    said = "Structured as a buy-down, it buys more. Drop the word buy down in the comments below, and I'll send it."
    toks = said.split()
    assert [toks[i] for i in sorted(captions.keyword(toks))] == ["buy", "down"]
    lines = captions.draft([{"i": k, "w": w, "heard": w, "start": k * 0.4, "end": k * 0.4 + 0.3}
                            for k, w in enumerate(toks)], load_look("clean"))
    assert "**BUY** **DOWN**" in " ".join(lines)


def test_the_last_word_of_a_take_is_not_pushed_into_the_silence_after_it():
    # the clip ends 0.25 s after the last word: "yet?" is the sound up to 3.0 s, and its timed end runs to the end
    env = np.full(325, -20.0)
    env[300:] = -70.0
    words = [{"w": "lender", "start": 2.0, "end": 2.6}, {"w": "yet?", "start": 2.6, "end": 3.25}]
    hear.settle(words, env, -50.0)
    assert words == [{"w": "lender", "start": 2.0, "end": 2.6}, {"w": "yet?", "start": 2.6, "end": 3.25}]
    # the same shape in the MIDDLE of a take, with the word's real sound after the gap, does move
    env = np.concatenate([np.full(300, -20.0), np.full(40, -70.0), np.full(100, -20.0)])
    words = [{"w": "rates,", "start": 2.0, "end": 2.8}, {"w": "mortgage", "start": 2.8, "end": 3.9}]
    hear.settle(words, env, -50.0)
    assert words[0]["end"] == 3.0 and words[1]["start"] == 3.4


@pytest.mark.parametrize("text,expect", [
    # a list that opens the same way each time is not a retake
    ("You don't know your margin so you underprice. You don't know your cash runway, so one slow month hurts.",
     "You don't know your margin so you underprice. You don't know your cash runway, so one slow month hurts."),
    # a go that breaks off, then the whole line
    ("You don't know your cash runway. So one crisis. You don't know your cash runway, so one slow month hurts.",
     "You don't know your cash runway, so one slow month hurts."),
    ("Four weeks ago, the average 30-year wait Four weeks ago, the average 30-year rate was 7.4%.",
     "Four weeks ago, the average 30-year rate was 7.4%."),
    # the same line, reworded
    ("Yours depends on your down payment and credit score. Yours depends on your credit and your down payment.",
     "Yours depends on your credit and your down payment."),
])
def test_a_list_is_not_a_retake(text, expect):
    f = _flat(text)
    keep, cuts = plan.plan_unscripted(f)
    assert " ".join(f[i]["w"] for i in keep) == expect


@pytest.mark.parametrize("text,expect", [
    ("They know how to raise funds, how to find a problem, or how to create a solution.",
     "They know how to raise funds, how to find a problem, or how to create a solution."),
    ("Someone giving you the shortcut or giving you the advice is better.",
     "Someone giving you the shortcut or giving you the advice is better."),
    ("So on a four, so on a $400,000 loan, that is less.", "so on a $400,000 loan, that is less."),
    ("And here's the, and here's the most, and here's the part that most people miss.",
     "and here's the part that most people miss."),
    ("I'm not telling you it, I'm not telling you it's cheap.", "I'm not telling you it's cheap."),
])
def test_a_list_inside_a_sentence_is_not_a_restart(text, expect):
    f = _flat(text)
    keep, cuts = plan.plan_unscripted(f)
    assert " ".join(f[i]["w"] for i in keep) == expect


def test_speech_that_no_word_covers_is_found(take):
    env = hear.envelope(hear.load(take))
    level = hear.speech_level(env)
    # the take has sound at 4-4.6, 5-5.6 and 6-6.6 s; the transcript stops after the second ("...time to hire")
    words = [{"w": "to", "start": 4.0, "end": 4.6}, {"w": "hire", "start": 5.0, "end": 5.6}]
    bare = hear.uncovered(env, level, 3.9, 6.8, words)
    assert len(bare) == 1 and bare[0][0] == pytest.approx(6.0, abs=0.05) and bare[0][1] == pytest.approx(6.6, abs=0.05)
    words.append({"w": "accountant.", "start": 6.0, "end": 6.6})
    assert not hear.uncovered(env, level, 3.9, 6.8, words)
    assert not hear.uncovered(env, level, 1.7, 3.9, [])              # silence is not speech


def test_a_quiet_word_is_not_dead_air(take, tmp_path):
    # the cut holds 0.9-4.7 s of the take: 2.4 s of it is silent. With no word meant to be there it is dead air ...
    flat = [_word(0, "one", 1.0, 1.6), _word(1, "two", 4.0, 4.6)]
    cuts = {"clips": [str(take)], "segments": [{"clip": "take.mov", "ci": 0, "start": 0.9, "end": 4.7,
                                                "first_word": 0, "last_word": 1, "group": 0}]}
    assert any("dead air" in f for f in listen.run(tmp_path, cuts, flat, {})["fix"])
    # ... and with words meant to be there (said too softly to measure) it is not: whether they ARE there is the
    # word-for-word comparison's question
    flat = [_word(0, "one", 1.0, 1.6), _word(1, "of", 1.7, 2.4), _word(2, "your", 2.5, 3.2), _word(3, "business", 3.3, 3.9),
            _word(4, "two", 4.0, 4.6)]
    cuts["segments"][0]["last_word"] = 4
    assert not any("dead air" in f for f in listen.run(tmp_path, cuts, flat, {})["fix"])
