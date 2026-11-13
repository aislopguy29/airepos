# LAB: new video types every day (eas.ydata Instagram + YouTube Shorts)

**Instagram eas.ydata, 7 posts/day (ET):**

| Time | Post | Made by |
|---|---|---|
| ~10:30 am | **LAB 1**: brand-new type (also YouTube) | lab task, slot 1 |
| 12:21 pm | State Elimination | series task (daily.py a) |
| ~2:30 pm | **LAB 2**: brand-new type (also YouTube when the gate is on) | lab task, slot 2 |
| 3:43 pm | Country Clash (until day 7) | series task (daily_clash.py) |
| ~5:45 pm | **LAB 3**: brand-new type (also YouTube when the gate is on) | lab task, slot 3 |
| 7:17 pm | Crown Race | series task (daily.py b) |
| ~9:15 pm | **ENCORE**: new episode of the best lab type (2 encores once Country Clash is over) | lab task, slot e |

**YouTube Shorts: 5 a day, every one a brand-new type** (since 2026-11-13): LAB 1, LAB 2, LAB 3 (~10:40 am, ~2:40 pm, ~5:50 pm)
plus 2 YouTube-only builds from the "YouTube LAB" task (slots y1, y2; runs 12:13 pm and 7:13 pm → live ~1:00 pm and ~8:00 pm).
Controlled by `lab/youtube.json`: `extra_types_enabled` (LAB 2/3 to YouTube + y-slots on/off) and `y_slots_per_day`.
Metricool's free plan publishes only 20 posts a month; past that, scheduled posts don't publish until the 1st.

## Files
- `lab/styles/<style_id>.py`: one file per video type. `build(out_mp4, seed, race_no/ep, log, stills=None)` returns a dict
  with `duration`, `title`, `description`, `tags` (+ result fields). CLI: `python3 -I lab/styles/<id>.py <out.mp4> <seed> [episode]`.
- `lab/<date>/<slot>.mp4` + `.json`: slot is 1, 2, 3, e (e2 for a second encore), y1..yN (YouTube-only). The json holds caption, comment, thumb_offset_ms,
  youtube{title,description,tags} (slot 1), and later `media_id` (Instagram) and `youtube_post` (Metricool id/uuid).
- Registry = every `lab/<date>/<slot>.json` (no shared file, so parallel runs never conflict). `python3 -I lab/lablib.py styles` lists all types made;
  `python3 -I lab/lablib.py check <mp4>` is the ffprobe gate; `shrink <mp4>` re-encodes lighter. (`lab/registry.json` is a frozen legacy list.)
- Reference implementation: `lab/styles/flag_drop.py` (marble race). Copy its structure, not its look.

## What counts as a NEW type
A new mechanic AND a new visual layout, not a re-skin. Never repeat a `style_id` or a near-identical format from the registry,
and the three new types of one day must differ from each other. Mix genres across the day (e.g. one race, one battle, one satisfying loop).
Idea bank (genres the watchlist accounts post): territory paint war, "ball grows every bounce", balls escaping rotating shapes,
last-one-standing battle royale, tug of war, king of the hill, Galton/plinko boards, domino chain, gravity well orbit duel,
pendulum wave, rhythm bounce that plays a melody, cellular-automata color war, sorting race, maze solver race, snake/arena survival,
1 vs 100 swarm, chain reaction pops, fractal zoom loop, sand/liquid fill, Newton's cradle chaos, "which shape survives", duplication
explosion. Countries/flags and US states fit the brand (country battles do well), but mechanics should vary.

## House rules (every lab video)
- 1080x1920, exactly 60 fps, H.264 + AAC via `engine.py` (`E.render`, `E.Mix`), 15–35 s, **at most 15 MB** (an 18 MB file failed
  Instagram ingest once; run `lablib.py shrink`). Must pass `lablib.py check`.
- Hook in the first second: big text stating the stakes ("8 FLAGS · 1 DROP · FIRST TO THE BOTTOM WINS"), then a "pick one" prompt.
  Rising tension, a slow-mo or highlighted climax, a payoff card that asks a comment question, and a 0.35 s loop blend back to frame 0.
- Text inside x 60–1020, y 240–1680 (centre safe zone), stroked and readable on a phone. Dark band behind HUDs; no overlaps.
- Seed-search the simulation for drama (close finish, lead changes, comeback) like `flag_drop.pick`.
- Original synthesized audio only (engine instruments or numpy). No commercial music, no samples from the web.
- No copyrighted characters, logos, mascots, brands or real people. No AI-imitation of other creators' signature looks.
- No real-world statistics. If a type uses data, it may only use the Census file in `data/` and must cite it on screen.
- Captions: hook line, one line on what happens (don't spoil the winner), a comment question, 5–6 hashtags. No "like/follow" bait.
- Always render preview stills first (`stills=[...]`), make a contact sheet, LOOK at it, fix problems, then render the full video.
