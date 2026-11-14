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

## Format rules
- Light cream/pastel theme, bold outlined text, constant motion, sunburst background.
- Per round: prompt at top, grid, countdown bar; tension ramps (vignette closes, rays speed up,
  shake, red strobe in the last second); then flash, zoom-punch onto the answer, confetti, "FOUND IT!".
- Retention: "DO NOT SCROLL" and "99% FAIL ROUND N" on the intro, "ROUND N IS HARDER" in the clear
  top band during reveals, "FINAL!" on the last round, "TOMORROW: 5 ROUNDS" at the end.
- Bottom: "new puzzle every day" chip with a smaller "follow + like for more" chip under it.
- Captions follow VARIETY_RULES.md: rotate structure and hashtags, keep similarity to the last 20
  captions under 50%, max 5 hashtags including #thatdatalover, no engagement bait beyond the score ask.
