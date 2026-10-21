# Looks

A look is one JSON file: the fonts, sizes and colours for every format. Three ship with the editor:

| Look | Feel |
|---|---|
| `clean` (default) | DM Sans, Instagram-style tight boxes (black on white, white on black), white outlined list type, yellow punchline, mid-size captions |
| `bold` | DM Sans ExtraBold on one dark see-through panel, red punchline, big 1-3 word captions with a heavy shadow |
| `serif` | A book serif (Gelasio) in tight boxes, Instrument Serif with a hard black edge for outline text and one-line captions |

A member's own look lives in `~/.go-reel-editor/looks/<name>.json` (copy the closest one and edit it); their own
font files go in `~/.go-reel-editor/fonts/`. `gre profile --look <name>` makes it their default; `--look` on any
command overrides it once.

## The fields

- `font`, `weight`, `size`: the default type (variable fonts take any weight 100-1000).
- `max_width`, `pad_x`, `pad_y`, `line_gap`, `block_gap`, `center_y`: b-roll block layout (pixels on a 1080x1920
  frame; `center_y` 0-1).
- `styles`: named text styles. A **boxed** style has `box` and `ink` (RGBA). An **outline** style has
  `"outline": true`, `ink`, `edge`, `edge_w` (edge thickness as a share of the font size; 0 = none), optional
  `bold` (faux-bold), `shadow` (`color`, `dy`, `blur`, `spread`), `font`, `size_scale`, `weight`, `leading`.
- `stagger_s`, `duration_s`: b-roll reveal spacing, default length.
- `listicle`: `title` / `item` / `header` / `small` / `punchline` (each `size`, `weight`, `style`), `header_styles`
  (column header colours), `list_top`, `max_width`, `column_width`, optional `panel` (`width`, `pad`, `radius`,
  `fill`) drawn under the whole card.
- `xreel`: layout numbers measured from a real X-reel (avatar 134 px at x108, text 53 px, image 864 px wide).
  Leave them unless the card looks wrong.
- `captions` (yaps): `font`, `size`, `weight`, `bold_weight`, `fill`, `edge`, `edge_w`, `shadow`, `center_y`
  (pixel line the captions are centred on; keep it 1350-1500), `max_width`, `max_words`.
- `title` (yaps): `style` (one of `styles`), `size`, `max_size`, `min_size`, `weight`, `top`, `hold`
  (seconds at full opacity), `fade_out`.

Matching a member's style from a screenshot of their reel: pick the closest font class (sans / serif / heavy),
measure the text height against the 1920 px frame for `size`, copy the box and text colours, and note whether
lines sit in boxes or are outlined. Render a preview and compare side by side.

Fonts bundled (all SIL Open Font License, see the OFL files in `fonts/`): DM Sans, Gelasio, Instrument Serif,
Inter, Noto Color Emoji.
