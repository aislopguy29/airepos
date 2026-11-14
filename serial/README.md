# @thatdatalover — interactive serial (replaces the political data posts)

Format (inspired by audience-vote serials, but an original story): a nightly ~30 s vertical episode of
original fiction. Each part ends on a binary choice; viewers comment one of two words; the majority
decides what happens in the next part. The account also posts versus/duel sim shorts (slot a).

## Files
- `page.html` — canvas renderer. Reads a script JSON (injected as `__SCRIPT__`). Scenes: `window`,
  `corridor`, `door`, `dark`. Add new scene functions as the story needs them; never break old scripts.
- `render.js` — Playwright + ffmpeg. `node serial/render.js <script.json> <out.mp4> [audio.wav]`,
  or previews: `node serial/render.js pv <script.json> 2,8,15,22,28` (writes pv_<t>.jpg, prints DUR).
  Needs `NODE_PATH=$(npm root -g)`.
- `music.py` — original synthesized score. `python3 -I serial/music.py <mood> <seconds> out.wav`.
  Moods: dark_ambient, tense_pulse, lofi_noir, piano_minimal, synth_chase, cinematic_strings.
  Normalize to about -18 LUFS with ffmpeg loudnorm before muxing. Rotate the mood every post.
- `scripts/day<N>.json` — one per part: title, day, tag, recap, beats[{scene,dur,lines[]}], choice{q,a,b}.
- `state.json` — current story, day, the last episode's media_id and the last vote tally.

## House rules
- Original fiction only: no real people, brands, trademarked characters, no real-world statistics.
  Keep the "Original fiction" bar on screen for the whole video. PG-13, tense but not gory.
- Each part: a hook in the first 1.5 s, 4 beats, a cliffhanger, then the choice card.
- The choice words change every part and are single words that are easy to type.
- Vote tally comes from the previous post's comments (Windsor get_data) and is shown in `recap`.
- An arc runs about 7 parts, then a new premise starts at day 1.
- 1080x1920, exactly 60 fps, H.264 yuv420p crf 20, AAC, under 50 MB, 25-45 s.
- Captions and music follow VARIETY_RULES.md (new structure and new mood every post).
