"""gre yap: the yap line, raw takes -> finished reel. Everything lives in <folder>/edit/.

  gre yap start <folder>                  find the clips, transcribe (once), propose the cut (keep.json), write the
                                          numbered transcript (words.md)
  gre yap cut <folder>                    keep.json -> cuts.json (pauses tightened, edges on the waveform)
  gre yap draft <folder> [--label v1]     a review copy: timecode burned in + the numbered transcript (L#/R#)
  gre yap captions <folder> [--redo]      write/check captions.txt -> captions.json + a preview sheet
  gre yap title <folder> "line" ["line"]  fit the title above the head -> title.json + a frame-1 preview
  gre yap final <folder>                  the finished reel + QA
  gre yap status <folder>                 what exists so far
  gre yap plan <folder> --force           propose the cut again (overwrites keep.json)
"""
import argparse, json, re, sys
from pathlib import Path
from .common import UserError, load_look, video_info, W, H, FPS
from . import words as wordsmod

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi"}


def edit_dir(folder):
    d = Path(folder).expanduser().resolve() / "edit"
    d.mkdir(parents=True, exist_ok=True)
    return d


def find_clips(folder):
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise UserError(f"not a folder: {folder}")
    clips = sorted(p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT and not p.name.startswith("."))
    if not clips:
        raise UserError(f"no video files in {folder} (put the raw takes there: .MOV or .MP4)")
    return clips


def _load_json(p, what):
    if not Path(p).exists():
        raise UserError(f"{Path(p).name} is missing: run `gre yap {what}` first")
    return json.loads(Path(p).read_text(encoding="utf-8"))


def cmd_start(a):
    from . import transcribe, plan
    E = edit_dir(a.folder)
    clips = find_clips(a.folder)
    print(f"{len(clips)} clip(s):")
    for c in clips:
        i = video_info(c)
        hdr = " HDR" if i["transfer"] in ("arib-std-b67", "smpte2084") else ""
        print(f"  {c.name}: {i['w']}x{i['h']} {i['fps']:.0f} fps {i['duration']:.1f} s{hdr}"
              + ("" if i["audio"] else "  NO SOUND"))
        if i["w"] > i["h"]:
            print(f"  note: {c.name} is horizontal; it will be cropped to vertical (centre)")
    wj = E / "words.json"
    if wj.exists() and not a.retranscribe:
        d = json.loads(wj.read_text())
        if [c["clip"] for c in d["clips"]] != [c.name for c in clips]:
            raise UserError("the clips changed since the transcript was made: run with --retranscribe")
        print("transcript: reusing edit/words.json (transcribed once)")
    else:
        transcribe.transcribe(clips, wj)
    d, flat = wordsmod.load(E)
    wordsmod.sheet(d, flat, E / "words.md")
    script = plan.find_script(a.folder)
    kp = E / "keep.json"
    if kp.exists() and not a.force:
        print("keep.json exists (your cut so far): kept. `gre yap plan <folder> --force` proposes a fresh one.")
    else:
        p = plan.make_plan(flat, script)
        kp.write_text(json.dumps(p, indent=1, ensure_ascii=False), encoding="utf-8")
        _report_plan(p, flat)
    print(f"next: read {E / 'words.md'} and {kp}, make the judgement cuts, then `gre yap cut`")


def _report_plan(p, flat):
    kept = sum(s["to"] - s["from"] + 1 for s in p["segments"])
    print(f"proposed cut ({p['mode']}): {kept} of {len(flat)} words kept in {len(p['segments'])} ranges")
    for n in p["notes"]:
        print("  - " + n)
    why = {}
    for c in p["cuts"]:
        why[c["why"]] = why.get(c["why"], 0) + 1
    if why:
        print("  removed: " + ", ".join(f"{v} {k}" for k, v in why.items()))


def cmd_plan(a):
    from . import plan
    E = edit_dir(a.folder)
    kp = E / "keep.json"
    if kp.exists() and not a.force:
        raise UserError("keep.json exists (it may hold your edits): pass --force to replace it")
    _, flat = wordsmod.load(E) or (None, None)
    if flat is None:
        raise UserError("no transcript yet: run `gre yap start` first")
    p = plan.make_plan(flat, plan.find_script(a.folder))
    kp.write_text(json.dumps(p, indent=1, ensure_ascii=False), encoding="utf-8")
    _report_plan(p, flat)


def _cut(E, folder):
    from . import cut
    loaded = wordsmod.load(E)
    if not loaded:
        raise UserError("no transcript yet: run `gre yap start` first")
    d, flat = loaded
    keep = _load_json(E / "keep.json", "start")
    clips = [str(Path(folder).expanduser().resolve() / c["clip"]) for c in d["clips"]]
    segs = cut.build(flat, keep, clips)
    p = cut.write(E, segs, clips)
    sm = cut.summary(segs, flat)
    return p, sm, segs, flat, keep


def cmd_cut(a):
    E = edit_dir(a.folder)
    p, sm, segs, flat, keep = _cut(E, a.folder)
    print(f"cut: {sm['seconds']:.1f} s, {sm['segments']} pieces, {sm['words']} words -> {p}")
    if sm["seconds"] > 90:
        print("  note: over 90 s. Short yaps land at 45-60 s: look for asides, examples and post-CTA sign-offs to cut.")


def _moves(E, cuts):
    from .render import auto_moves, frame_plan
    mp = E / "moves.json"
    if mp.exists():
        m = json.loads(mp.read_text())
        if not m.get("auto") and len(m["clips"]) == len(cuts["segments"]):
            return m
    m = auto_moves(cuts["segments"], frame_plan(cuts["segments"]))
    mp.write_text(json.dumps(m, indent=1))
    return m


def _captions(E, lk, cuts, flat, keep, required=False):
    from . import captions as C
    cj = E / "captions.json"
    if not cj.exists():
        if required:
            raise UserError("no captions yet: run `gre yap captions`")
        return []
    caps = json.loads(cj.read_text(encoding="utf-8"))
    return C.images(caps, lk)


def _title(E, lk):
    from . import title as T
    tj = E / "title.json"
    if not tj.exists():
        return None
    return T.layer(json.loads(tj.read_text(encoding="utf-8")), lk)


def transcript_sheet(flat, cuts, keep, out_md, label):
    from .captions import played_words
    played = played_words(flat, cuts, keep)
    kept = {p["i"] for p in played}
    lines, cur = [], []
    for p in played:
        cur.append(p)
        if wordsmod.ends_sentence(p["w"]):
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    why = {}
    for c in keep.get("cuts", []):
        for i in range(c["from"], c["to"] + 1):
            why[i] = c["why"]
    removed, run = [], []
    for w in flat:
        if w["i"] in kept:
            if run:
                removed.append(run)
                run = []
        else:
            run.append(w)
    if run:
        removed.append(run)
    fmt = lambda t: f"{int(t // 60)}:{t % 60:04.1f}"
    md = [f"# Draft {label}: numbered transcript", "",
          "Give notes against THIS draft's clock (top-left of the video): `cut 0:12.4-0:14.0`, `drop L7`, "
          "`put back R2`, `start on L5`. Say **locked** when the cut is right.", "", "## Kept (draft time)", ""]
    md += [f"- **L{i}** {fmt(l[0]['start'])} {' '.join(p['w'] for p in l if p['w'])}" for i, l in enumerate(lines, 1)]
    md += ["", "## Removed (clip, time in the clip, why)", ""]
    for i, r in enumerate(removed, 1):
        reason = why.get(r[0]["i"]) or ("filler" if all(wordsmod.norm(x["w"]) in wordsmod.FILLERS for x in r) else "cut")
        md.append(f"- **R{i}** {r[0]['clip']} {fmt(r[0]['start'])} · {reason} · W{r[0]['i']}-W{r[-1]['i']}: "
                  f"{' '.join(x['w'] for x in r)}")
    Path(out_md).write_text("\n".join(md) + "\n", encoding="utf-8")


def cmd_draft(a):
    from .render import render
    E = edit_dir(a.folder)
    lk = load_look(a.look)
    p, sm, segs, flat, keep = _cut(E, a.folder)
    cuts = json.loads(p.read_text())
    moves = _moves(E, cuts)
    caps = [] if a.no_captions else _captions(E, lk, cuts, flat, keep)
    title = None if a.no_captions else _title(E, lk)
    label = a.label or _next_label(E)
    out = E / "drafts" / f"draft-{label}.mp4"
    render(cuts, out, moves=moves, captions=caps, title=title, label=label)
    transcript_sheet(flat, cuts, keep, out.with_suffix(".md"), label)
    print(f"draft: {out}\nnumbered transcript: {out.with_suffix('.md')}")


def _next_label(E):
    n = len(list((E / "drafts").glob("draft-v*.mp4"))) if (E / "drafts").exists() else 0
    return f"v{n + 1}"


def cmd_captions(a):
    from . import captions as C
    from .render import frame_plan
    E = edit_dir(a.folder)
    lk = load_look(a.look)
    if not (E / "cuts.json").exists():
        raise UserError("no cut yet: run `gre yap cut` first")
    d, flat = wordsmod.load(E)
    cuts = json.loads((E / "cuts.json").read_text())
    keep = json.loads((E / "keep.json").read_text(encoding="utf-8"))
    played = C.played_words(flat, cuts, keep)
    ct = E / "captions.txt"
    if not ct.exists() or a.redo:
        lines = C.draft(played, lk)
        ct.write_text("# One caption per line, in order. **word** = bold. Fix mishears in the text; never re-time.\n"
                      + "\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote a first chunking: {ct} ({len(lines)} captions). Read it, fix it, run this again.")
    caps, problems, hard = C.build(C.parse(ct), played, lk)
    (E / "captions.json").write_text(json.dumps(caps, indent=1, ensure_ascii=False), encoding="utf-8")
    for pr in problems:
        print(("  FIX   " if pr in hard else "  note  ") + pr)
    print(f"{len(caps)} captions -> {E / 'captions.json'}" + ("" if not hard else f"  ({len(hard)} to fix)"))
    _caption_sheet(E, lk, cuts, caps)
    return 1 if hard else 0


def _caption_sheet(E, lk, cuts, caps):
    """Five frames of the cut with their captions (the widest line among them), for a look before rendering."""
    from . import captions as C
    from .title import grab
    from .render import blend
    from PIL import Image
    if not caps:
        return
    moves = _moves(E, cuts)
    pick = sorted(range(len(caps)), key=lambda k: -len(caps[k]["text"]))[:1]
    step = max(1, len(caps) // 4)
    pick = sorted(set(pick + list(range(0, len(caps), step))[:4]))
    tiles = []
    for k in pick:
        c = caps[k]
        img = grab(cuts, moves, (c["start"] + c["end"]) / 2)
        if img is None:
            continue
        arr, x, y = C.draw(c["text"], lk["captions"])
        blend(img, arr, x, y)
        tiles.append(Image.fromarray(img).resize((W // 3, H // 3)))
    if tiles:
        sheet = Image.new("RGB", (W // 3 * len(tiles), H // 3))
        for i, t in enumerate(tiles):
            sheet.paste(t, (i * W // 3, 0))
        sheet.save(E / "captions-preview.png")
        print(f"preview: {E / 'captions-preview.png'}")


def cmd_title(a):
    from . import title as T
    from .render import blend
    from PIL import Image
    import numpy as np
    E = edit_dir(a.folder)
    lk = load_look(a.look)
    cuts = _load_json(E / "cuts.json", "cut")
    moves = _moves(E, cuts)
    frames = [f for f in (T.grab(cuts, moves, t) for t in (0.0, 1.0, 2.0, 3.0)) if f is not None]
    head, face, chin = T.head_box(frames)
    lines = [l for l in a.lines if l.strip()]
    if not lines or len(" ".join(lines).split()) > 10:
        raise UserError("a title is 3-8 words on 1-2 lines")
    C = lk["captions"]
    cap_top = int(C["center_y"] - C["size"] * 0.75)
    size, top, img, where = T.fit(lines, lk, head, chin, cap_top, face)
    spec = {"lines": lines, "size": size, "top": top, "head_top": head, "face_top": face, "chin": chin, "where": where}
    (E / "title.json").write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
    note = (f"head y{head}-{chin}, placed {where}" if head else "no face found (title placed by the default)")
    f0 = frames[0] if frames else np.zeros((H, W, 3), np.uint8)
    blend(f0, np.array(img), 0, top)
    capsj = E / "captions.json"
    if capsj.exists():
        from . import captions as C
        caps = json.loads(capsj.read_text(encoding="utf-8"))
        if caps:
            arr, x, y = C.draw(caps[0]["text"], lk["captions"])
            blend(f0, arr, x, y)
    Image.fromarray(f0).save(E / "title-preview.png")
    print(f"title: size {size}, y{top}-{top + img.height} ({note}) -> {E / 'title.json'}\nframe 1: {E / 'title-preview.png'}")


def cmd_final(a):
    from .render import render
    from .qa import qa
    E = edit_dir(a.folder)
    lk = load_look(a.look)
    p, sm, segs, flat, keep = _cut(E, a.folder)
    cuts = json.loads(p.read_text())
    moves = _moves(E, cuts)
    caps = _captions(E, lk, cuts, flat, keep)
    title = _title(E, lk)
    if not caps:
        print("note: no captions (run `gre yap captions` first if you want them)")
    name = Path(a.folder).expanduser().resolve().name
    out = Path(a.out) if a.out else E / f"{re.sub(r'[^A-Za-z0-9_-]+', '-', name).strip('-') or 'yap'}-final.mp4"
    render(cuts, out, moves=moves, captions=caps, title=title, label=None)
    print(f"final: {out}")
    return qa(str(out), yap=True)


def cmd_status(a):
    E = edit_dir(a.folder)
    for f, what in (("words.json", "transcript"), ("keep.json", "proposed/edited cut"), ("cuts.json", "cut"),
                    ("moves.json", "camera moves"), ("captions.txt", "caption text"), ("captions.json", "timed captions"),
                    ("title.json", "title")):
        print(f"  {'yes' if (E / f).exists() else ' - '}  {what:22s} edit/{f}")
    for dft in sorted((E / "drafts").glob("*.mp4")) if (E / "drafts").exists() else []:
        print(f"  draft  {dft.name}")


def main(argv):
    ap = argparse.ArgumentParser(prog="gre yap", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start"); p.add_argument("folder"); p.add_argument("--retranscribe", action="store_true")
    p.add_argument("--force", action="store_true")
    p = sub.add_parser("plan"); p.add_argument("folder"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("cut"); p.add_argument("folder")
    p = sub.add_parser("draft"); p.add_argument("folder"); p.add_argument("--label"); p.add_argument("--look")
    p.add_argument("--no-captions", action="store_true")
    p = sub.add_parser("captions"); p.add_argument("folder"); p.add_argument("--redo", action="store_true")
    p.add_argument("--look")
    p = sub.add_parser("title"); p.add_argument("folder"); p.add_argument("lines", nargs="+"); p.add_argument("--look")
    p = sub.add_parser("final"); p.add_argument("folder"); p.add_argument("--look"); p.add_argument("--out")
    p = sub.add_parser("status"); p.add_argument("folder")
    a = ap.parse_args(argv)
    return {"start": cmd_start, "plan": cmd_plan, "cut": cmd_cut, "draft": cmd_draft, "captions": cmd_captions,
            "title": cmd_title, "final": cmd_final, "status": cmd_status}[a.cmd](a)
