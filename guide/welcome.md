# The welcome, the profile and the look

`gre <command>` means `bash "<skill folder>/gre.sh" <command>`. Keep to the reply rules in SKILL.md.

## "Get me started with the GO! Reel Editor."

The goal: their first reel in under five minutes. Ask as little as possible.

1. Run `gre doctor` without showing it. Not READY: `guide/setup.md` first.
2. Reply, in this shape and no longer:

   > Welcome to the GO! Reel Editor. You talk, I edit: X-reels, listicles, b-roll reels and talking videos, right
   > here on your computer.
   >
   > Two quick things and we'll make your first reel:
   > 1. Your name and Instagram @handle, as they show on your profile.
   > 2. Your profile photo. Put it in this folder, or tell me where it is.

3. When they answer: `gre find --kind image` if they didn't say where the photo is (offer the likely ones as
   buttons). A screenshot of their profile works: crop the circle out of it. Then
   `gre profile --name "Jane Doe" --handle @janedoe --avatar <file>`.
   They skipped something? Carry on. Only the X-reel needs the name, handle and photo.
4. **Build the practice X-reel straight away** (`guide/ez-reels.md` § Practice): it shows their own name and photo,
   so the first thing they see is theirs. No photo yet: build the practice listicle.
5. Hand it over with buttons: *Make it my style* · *Try a listicle* · *Edit a talking video* · *Use my own content*.

Do not ask about colours, fonts, audience or caption style here. Each is asked later, once, when it is needed.

## "What can I make?" (any time)

One line and four buttons: *X-reel* (a news story as a post card) · *Listicle* (a list over a clip) · *B-roll*
(two or three lines over a clip) · *Yap* (a talking video, cut and captioned).

## Make it their style (after the first reel, or "change my colours", "my fonts", "match my reels")

Offer it once after their first reel if they haven't asked. One question at a time:

1. **Colours.** "What are your brand colours? Hex codes, or drop your logo or a screenshot of your website in this
   folder and I'll pull them." From an image: `gre colors <file>` prints the main ones; show them and let them pick
   one or two (buttons).
2. **Font.** "Do you know your font's name? If not, I'll pick one that fits." A free Google Font downloads with
   `gre font "Montserrat"` (it prints the file name). A paid font can't be downloaded for them: offer the closest
   free match (Proxima Nova, Gotham → Montserrat · SF Pro, Helvetica, Arial → Inter · Avenir → Nunito Sans · Futura →
   Jost · Canva Sans → Open Sans · Georgia, Times → Gelasio), or they put their own .ttf/.otf files in
   `~/.go-reel-editor/fonts`.
3. **A reel to match (optional).** A screenshot of one of their best reels: read it and pick the closest starter look
   (text in boxes → `clean`, heavy type on a dark panel → `bold`, serif type → `serif`).

Then build it and show the sample sheet:

```
gre look new <first-name> --from <clean|bold|serif> --font <file> --accent <main colour> [--accent2 <second colour>]
             [--caption-size 96-110 for big one-to-three-word captions]
```

It becomes their default and writes a sample sheet (a listicle, a b-roll, an X-reel and a yap title with a caption,
all in their look). Show it and adjust until they like it ("bigger captions", "use the darker blue").

## What the profile holds, and when to ask

| Detail | Ask it | Save it |
|---|---|---|
| Name, @handle, profile photo | In the welcome | `gre profile --name --handle --avatar` |
| Colours, font, look | After the first reel, or when they ask | `gre look new ...` |
| What they do, where, for whom | The first time they ask you to WRITE something | `gre profile --role "loan officer" --market "Tampa FL" --audience "Realtors and first-time buyers"` |
| Caption size for talking videos | Never ask. They say "bigger captions" if they want it | `--caption-size` on their look |

`gre profile` alone prints what is saved. `gre looks` lists the looks; `--look <name>` on any command uses another
look once; `gre profile --look <name>` changes the default. A look is one JSON file (`looks/README.md` explains the
fields); a member's own look lives in `~/.go-reel-editor/looks/`.
