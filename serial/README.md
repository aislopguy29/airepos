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

## Narrator (every episode)
- `narrate.py` — offline narrator via ffmpeg's flite filter. Usage:
  `python3 -I serial/narrate.py scripts/day<N>.json /tmp/voice.wav /tmp/day<N>_adj.json [voice] [pitch]`
  It reads each beat's lines + the choice card, stretches beat durations so the voice fits,
  writes the voice on the full timeline and an ADJUSTED script json — always render the video
  from the adjusted json so timing matches.
- Voices: rms (default narrator, pitch 0.92 = deadpan noir), kal16, slt (female), awb.
  Keep one voice per story arc for continuity; a new arc may switch voice/pitch.
- Mix: `python3 -I serial/music.py <mood> <DUR> /tmp/mus.wav` then
  `ffmpeg -i /tmp/mus.wav -i /tmp/voice.wav -filter_complex "[0:a]volume=0.5[m];[1:a][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=9,aresample=44100" -ac 2 /tmp/final_audio.wav`
  and render with `node serial/render.js /tmp/day<N>_adj.json <out.mp4> /tmp/final_audio.wav`.
- The voice is synthetic by design (no external TTS available in the sandbox); the pitched-down,
  echoed read is the narrator character. Verify with ffprobe + volumedetect that audio is non-silent.
