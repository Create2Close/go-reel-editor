# Graphics on a yap: a headline, the rate chart, a number

`gre <command>` means `bash "<skill folder>/gre.sh" <command>`. Graphics sit on a talking video, land on the words
the member says, and are drawn in their look. Keep to the reply rules in SKILL.md: the member never sees a command
or the file.

## Which graphic

| They say | Graphic |
|---|---|
| "Put this article on screen" + a link · "show the headline" | **Headline card**: the headline, the outlet and the date, with a highlighter swipe across one key phrase |
| "Show the rate chart" · "show where rates are" | **Rate chart**: the weekly 30-year fixed average, last 52 weeks, with its source |
| "Show 7.40 to 7.11" · "put the $79 on screen" | **Stat card**: one number and a short label, or from → to |
| "Add my name" · "add my NMLS number" (only ever when THEY ask, or have said yes) | **Lower third**: name, title and one line, top left, after the title has gone |

Graphics they ask for up front are part of the one-stop first version. Otherwise offer them once, as a button after
the draft (*Add a graphic*), when the video quotes a number or talks about a news story. At most three or four in a
60-second yap: each one must make a sentence land harder.

## The hard rules

- **Never invent a headline, an outlet, a date or a number.** Every word and digit on a card comes from the page,
  from `gre rates`, or from the member. Never shorten or reword a headline: if it does not fit, use the full-screen
  layout or ask for a different article.
- **A chart only from `gre rates`.** Never draw, estimate or "update" one yourself.
- **A stat only from what the member says in the video, or from `gre rates`.** If the number on the card and the
  number they say differ, stop and ask which is right.
- **The name card (lower third) is never the default and never required.** See "The name card" below: it is only
  drawn for a member who said yes, you never add one on your own judgement, and no reel ever waits for it.
- Rates and payments are trigger terms (`formats/yap.md` § Compliance): a graphic that shows one gets the same
  one-line flag for their compliance check as a caption would. A payment is principal and interest only: say so.

## Steps

1. **Get the facts.**
   - Article: `gre headline <link>` prints `HEADLINE:`, `OUTLET:`, `DATE:`. It asks for the page once, from the
     member's own computer, the way their browser would. A missing outlet or date is left off the card, never guessed.
   - **If it prints `COULD NOT READ`** (some news sites refuse, or want a login): do not try the site another way.
     Ask the member, in one line: "That site won't let me read the page. Send me a screenshot of the article with the
     headline, the outlet and the date showing, here in the chat or in this folder." Read the three from the
     screenshot exactly as written. Anything not visible in it is left off. They can also just paste the headline.
   - Rates: `gre rates` prints the latest weekly average and its date, one week, four weeks and a year ago, and the
     52-week high and low. `gre rates --payment 400000` adds the monthly payment on that loan at each rate and the
     difference: the numbers members talk about. Offline, it uses the last saved numbers and says how old they are.
2. **Write `edit/graphics.json`** in the yap's folder (after the cut, the captions and the title):

   ```json
   {"graphics": [
     {"type": "headline", "at": "here's the headline", "for": 4.0, "layout": "above",
      "headline": "Mortgage rates fall for the fourth straight week", "outlet": "HousingWire",
      "date": "Nov 12, 2026", "highlight": "fourth straight week", "url": "https://..."},
     {"type": "chart", "at": "look at the chart", "for": 5.0, "layout": "full"},
     {"type": "stat", "at": "7.40", "for": 3.0, "from": "7.40%", "to": "7.11%", "label": "30-year fixed"},
     {"type": "stat", "at": "79 dollars", "value": "$79", "label": "less a month on $400,000"}
   ]}
   ```

   Write only the graphics this video needs. A `lower_third` entry is not in this example on purpose: it goes in
   only for a member who has said yes (below).

   - `at`: two to five words they say, copied from the captions (the graphic lands as they say them, and stays on
     them when the cut changes), or a number of seconds. `"nth": 2` picks the second time they say it; `"delay": 0.5`
     shifts it half a second later.
   - `for`: seconds on screen. Long enough to read twice: about 4 for a headline, 5 for the chart, 3 for a stat.
   - `layout`: `above` sits in the space above the head. `full` takes the whole frame for a beat while they keep
     talking (the captions stay on, in the card's own ink). A stat picks its own spot (beside the head if there is
     room, else above).
   - `highlight`: the two to four words of the headline that carry the news, exactly as they appear in it.
   - `weeks` on a chart (default 52). The chart keeps the numbers it was first built with (`edit/rates.json`), so
     the finished reel matches what they said. For newer numbers: `gre rates --refresh`, delete that file, run step 3.
3. **`gre yap graphics <folder>`** times and places every graphic and prints one line each: `ok`, or `FIX` with
   what is wrong in plain words (the words are not in the video, no room above the head, it covers the face, it
   sits on the title or the captions, two graphics collide, the text does not fit). Fix the file and run it again
   until no `FIX` is left. (A `note` line is not a problem: it says a name card was left out, and why.)
4. **Look at `edit/graphics-preview.png` yourself**: every graphic on the real frame of its moment. Check it like a
   designer: readable on a phone, nothing on the face, the highlight on the right words, the right number.
5. **`gre yap draft <folder>`** shows them moving. In the one-stop reply, add one line: "I put the HousingWire
   headline on screen when you mention it, and the rate chart after."

`gre yap draft` and `gre yap final` draw whatever is in `graphics.json`. A `FIX` that is still open is printed again,
and the final check fails on it: never hand over a reel with an open `FIX`.

## Notes that change one graphic

A note changes only that graphic. Edit its entry, run `gre yap graphics`, then `gre yap draft`.

| They say | Do |
|---|---|
| "Move the headline later" · "it comes in too early" | Change `at` to the words where it should land, or add `"delay": 0.5` |
| "Leave it up longer" · "it's gone too fast" | Raise `for` |
| "Make the chart full screen" · "it's covering my head" | `"layout": "full"` |
| "Smaller, keep me on screen" | `"layout": "above"` |
| "Highlight the other part" | Change `highlight` to those words of the headline |
| "Take the stat card off" | Delete that entry |
| "Different colours" · "match my brand" | That is the look, not the graphic: `guide/welcome.md` § Make it their style |

## The name card (lower third): only if they say yes

It shows their name, title and one line (an NMLS number or a disclosure) for a few seconds. It is **off** for every
member until they say yes, and **no is a complete answer**.

- **Never add one on your own judgement**, and never put a `lower_third` entry in a file because a video "should"
  have one. The engine backs this up: an entry is only drawn when the profile says yes.
- **They ask for it** ("add my name", "put my NMLS number on screen"): that is a yes. Save it
  (`gre profile --lower-third yes`) and add the entry.
- **Otherwise ask once, ever**, and only if `gre profile` shows no `lower_third` answer yet: after you hand over
  their first finished reel with graphics, as its own short message with two buttons, in this order:
  *No, leave it off* · *Yes, add it*. ("Want your name and NMLS number on screen for a few seconds in videos like
  this? Most loan officers put the NMLS number in the post's caption instead.")
  - *No*, no answer, or they move on to something else: it stays off. Save `gre profile --lower-third no` and never
    ask again. They can still ask for it themselves any time.
  - Nothing waits on this question: never ask it before a draft or a final, and never hold a reel for the answer.
- **They said yes but the text is missing**: ask for just that text, once ("What should it say under your name?
  For example: Loan Officer, NMLS #123456."), and save it:
  `gre profile --name "Jane Doe" --title "Loan Officer" --line "NMLS #123456"`. Until they answer, make the reel
  without the card: a missing name, title or NMLS number never blocks or delays a reel.
- The entry, for a member who said yes: `{"type": "lower_third", "at": 4.0, "for": 4.0}`. It sits top left, where
  the title sat, so start it once the title has gone (about 4 seconds in) and not at the same moment as an `above`
  card. If the check prints a `note` that it was left out (no yes saved, no name, no room above the head), the reel
  is still good to go.

## When there is no room

Close-up videos leave little space around the head, and none low down where the captions run. The check tells you:
"no clear space above the head" means use `"layout": "full"`; a name card with no room is left out by itself (say
so in one line, and put the NMLS number in the post's caption). Never push a card onto the face to make it fit.

## Their look decides the design

Every card uses the look's font, card and colours (`looks/README.md` § graphics). A member's own look puts their
main colour on the highlighter, the chart line, the "to" number and a rule across the top of each card, and their
second colour on the small labels. They approve it once on the sample sheet (`gre look sheet`).
