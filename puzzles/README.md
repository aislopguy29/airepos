# @thatdatalover — daily "spot the odd one" puzzle Reels

This account posts timed visual puzzles. No political or statistics content.

## One command builds a day's video
`python3 -I puzzles/run.py <YYYY-MM-DD> <slot> [seed]`
- writes `puzzles/<date>/<slot>_script.json` (the puzzle), `puzzles/<date>/<slot>.json` (meta + caption)
  and `puzzles/<date>/<slot>.mp4` (1080x1920, 60fps, H.264 + AAC, crf 23, under 50 MB)
- verifies resolution, fps, audio, duration and size; exits non-zero with `CHECK FAILED` if anything is off
- prints `OK` then `POST_JSON={...}` (the meta, including `caption` and `thumb_offset_ms`)
- omit the seed so each day differs; pass one only to reproduce a specific build

## Pieces
- `make.py` — picks the day's puzzle: shape (circle/square/star/blob), palette, 4-5 difference
  types, grid sizes, odd-one positions, timer, title, caption and hashtags. Reads the last 14
  `puzzles/*/*.json` and avoids recent shapes, palettes, titles, hashtag sets and difference sets.
- `page.html` + `render.js` — canvas renderer (Playwright + ffmpeg). Previews:
  `NODE_PATH=$(npm root -g) node puzzles/render.js pv <script.json> 2,8,15,22`
- `memeaudio.py` — the audio bed: catchy marimba hook, soft kit, tonal risers/ticks/impacts,
  gentle sidechain, synced to the round timeline. Listenable, not harsh. No narrator.
- `narrate.py` — unused for this format (kept for other series).

## Round types
- **odd** (default): one cell differs; reveal zoom-punches onto it.
- **count**: several cells share a trait and the answer is a number ("HOW MANY ARE WINKING?").
  The reveal rings every target in sequence and shows "IT WAS N" instead of zooming.
  `make.py` makes roughly one round in four a count round, never the first or last.
Add a new type by giving a round a `mode` in the script json and handling it in `grid()`.

## Format rules
- Light cream/pastel theme, bold outlined text, constant motion, sunburst background.
- Per round: prompt at top, grid, countdown bar; tension ramps (vignette closes, rays speed up,
  shake, red strobe in the last second); then flash, zoom-punch onto the answer, confetti, "FOUND IT!".
- Retention: "DO NOT SCROLL" and "99% FAIL ROUND N" on the intro, "ROUND N IS HARDER" in the clear
  top band during reveals, "FINAL!" on the last round, "TOMORROW: 5 ROUNDS" at the end.
- Bottom: "new puzzle every day" chip with a smaller "follow + like for more" chip under it.
- Captions follow VARIETY_RULES.md: rotate structure and hashtags, keep similarity to the last 20
  captions under 50%, max 5 hashtags including #thatdatalover, no engagement bait beyond the score ask.

## Caption tooling (vendored from instagram-agent-skill, MIT)
`make.py` runs three tools from `vendor/ig-agent-skill/` on every caption:
- `hookscore.py` scores 5 candidate opening lines on length, specificity, stakes, frontload and
  address; the highest scorer becomes the hook. All candidates and scores are kept in the meta.
- `humanize.py` strips em dashes, slop vocabulary and invisible watermark characters.
- `caption.py` reports exactly what shows in the feed before "... more" (saved as `caption_first_125`).
They are vendored, not installed as skills, because scheduled runs start from a fresh session with
no plugins. If a tool is missing the pipeline falls back to the plain template, it never fails.

## Second format: eye-jump drill
`eyejump.html` + `eyeaudio.py`, same renderer. A dot teleports between positions and the viewer
tracks it with their eyes only; each level is faster than the last.

Build by hand:
```
python3 -I puzzles/eyeaudio.py puzzles/scripts/<script>.json /tmp/ej.wav
ffmpeg -y -i /tmp/ej.wav -af loudnorm=I=-14:TP=-1.2:LRA=10 -ar 44100 -ac 2 /tmp/ejn.wav
PAGE=eyejump.html NODE_PATH=$(npm root -g) node puzzles/render.js <script>.json out.mp4 /tmp/ejn.wav
ffmpeg -y -i out.mp4 -c:v libx264 -crf 23 -preset fast -tune animation -pix_fmt yuv420p -c:a copy -movflags +faststart final.mp4
```
Script shape: `{title, title2, sub, footer, levels:[{bpm, jumps, pattern, label}]}`.
Patterns: `lr`, `ud`, `diag`, `circle`, `random`. Keep bpm between 60 and ~300; above that the dot
moves faster than a saccade can land and the drill stops meaning anything.
Each level gets a label beat (a ready dot plus countdown), then its jumps; a blip lands on every move.
`render.js` picks the page with the `PAGE` env var, so both formats share one renderer.

## Third format: Facebook/Instagram carousel
`carousel.html` + `carousel.js`. Turns any puzzle script into swipeable 1080x1350 (4:5) slides:
cover → one slide per puzzle → an answers slide with every solution ringed.
```
python3 -I puzzles/make.py <out_dir> <slot> [seed]      # writes <slot>_script.json
NODE_PATH=$(npm root -g) node puzzles/carousel.js <script.json> <out_dir>
```
Prints `SLIDES=[...]` with the jpg paths, in order. 4:5 is the tallest ratio Facebook and
Instagram both show in full, so the same set works on either.

## No watermarks
Nothing carries a persistent footer, handle or branding chip — not the videos, not the carousels.
Only per-slide CTAs ("COMMENT YOUR ANSWER", "HOW MANY DID YOU GET?") and the video end cards remain.
Do not add a standing watermark back to any format.
