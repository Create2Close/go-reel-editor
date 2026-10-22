# Yap

One person talking straight into their phone, vertical, no b-roll. It looks off-the-cuff and is engineered:
the cut, the camera moves, the words on screen and the first frame do the work. Editing is subtraction:
throw away every false start, close every gap, add nothing (no transitions, no whooshes, no stock).

Shape of a yap (from the yap skill): **1 claim → 2 hooks (spoken + on-screen) → up to 3 pillars → land it.**
Default length under 60 s; a 45 s cut usually beats a 70 s one.

## Cut (the judgement layer; the engine already did fillers, restarts and repeated sentences)

**The test for every line: does the video lose impact or clarity without it?** Relevant is not necessary.

Always
- **Last take wins.** A line said twice keeps only its last complete take.
- **Start on the first word of the script.** Cut warm-ups ("okay", "all right", "is it recording"), chatter
  with whoever's behind the camera, and the slate.
- **Tighten every pause of 0.5 s or more** (automatic). Never protect a "beat" on your own judgement.
- **Remove stumbles inside a sentence**: a doubled phrase keeps one.
- **Never cut a word without a clean edit point**: words said as one sound ("So here's") stay together.

Brevity
- **Asides go**, even good ones: jokes and tangents beside the argument.
- **Connective padding goes** before a line that already lands ("but you know what?", "And for me,"),
  unless it's the creator's deliberate rhetorical set-up for the next line (judge by whether removing it
  weakens that line).
- **Meta-signposts go** ("Stick with me here for one second", "Let me explain").
- **An example can go** once the claim and their personal proof stand (short cuts especially).

Impact
- **End on the call to action's concrete promise.** A sign-off, tagline or motivational line AFTER the CTA
  is cut ("Takes less than 60 seconds." ends it, not "Don't let this market shrink your business.").
- **The hook is the claim only**: never a promise the video doesn't pay off.
- **Open on the strongest hook.** Usually their first line. If a later line grabs faster (a sharper number,
  the payoff stated as a claim), offer a cold open: that line plays first and is removed from its later spot.
  Name the runner-up so they can say "original opening".
- **Keep a payoff's set-up**: never cut half of a contrast ("Great talkers get heard. / Great askers get chosen.").
- **Keep their own evidence** (their market, their numbers, their story), even when it sits inside a
  signpost: trim only the wrapper.

Show your work: every judgement cut has a reason in `keep.json` → `cuts`, so the member can overrule it in two
words ("put back R4").

**Scripted yaps** (a word-for-word `script.txt`): the cut follows the script; the creator's rhetoric stays.
Flag (don't silently cut) a post-CTA sign-off and meta lines: they usually go at the lock.

## Notes after a draft (lock-and-patch)

A note changes only its spot. "Put back R3" adds that range back; "cut 0:12-0:14" removes the words playing
then (find them in the draft's numbered transcript: `edit/drafts/draft-vN.md` has the W numbers; L lines carry draft times); "start on L5" moves L5 to the front. Never
re-decide the rest of the cut while fixing one note: a simple video must not take seven drafts.

## Camera moves (automatic)

Every cut changes the framing by at least 10 % (a same-take jump cut that changes less reads as a glitch):
wide 100 → 103 % slow drift, tight 113 → 116 %, alternating. Pieces under 0.8 s hold still.

## Captions

- One line each, natural phrases, every spoken word exactly once and in order.
- **Never across a sentence end** ("the end | However", never "the end However").
- **Never end a line on a small word** (a, an, the, of, in, to, for, with, and, but, or, so, my, your, that...):
  carry it to the next line. A particle that belongs to its verb stays ("all in", "figure it out").
- No periods; "?" and "!" stay; no comma at a line end; commas and colons are fine for lists and lead-ins.
- Numbers over 10 as numerals (2009, 34, 31st, $10,000); ten and under as words.
- "Realtor" always with a capital R. Brand names as the brand spells them.
- Quoted or paraphrased speech in “curly quotes”.
- **Bold** about one word every 5 seconds: the stressed word.
- With a script, the caption text IS the script; the recording only times it. A mishear is fixed in the text,
  never by re-timing.

## Title (the visual hook)

- On screen from frame 1 at full opacity (the first frame is the thumbnail), held 3.5 s, quick fade.
- 3-8 words, never a transcript of the first sentence; it completes it: the stake, the cost, the twist.
  (If the first spoken line already IS the claim in 8 words or fewer, repeating it is fine.)
- Mute test: the text alone must stop the scroll.
- Sits above the head when there is room, over hair or a hat if needed, never on the face.
- Give 5-6 options, three flavours (contrast, curiosity, direct-to-viewer), recommend one with a reason; flag
  any option that claims more than they say.

## Sound

One static chain, every yap: crossfaded joints, 80 Hz high-pass (phone rooms rumble), the kept speech raised or
lowered to -17 LUFS, a -6 dBFS limiter. Never "auto-loudness" that pumps. QA checks it.

## Compliance (mortgage)

Never promise or predict rates, approvals, savings or refinance opportunities. Rates, payments, down payment
and term are trigger terms: flag a caption or title that states one for the member's compliance check.
