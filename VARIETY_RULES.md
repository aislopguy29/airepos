# Variety & anti-repeat rules (ALL accounts: eas.ydata, @thatdatalover, YouTube)
Goal: every post looks, sounds and reads different, so nothing is flagged as repeated/unoriginal content.

## Music: new style every post
- Pick a music mood that differs from the last 10 posts (check `music_style` in posts/*.json, lab/*/*.json, political/*/*.json). Record `music_style` in the post json.
- Rotate: ambient pads; lo-fi chill (swung beat, soft e-piano); minimal piano arpeggio; synthwave; cinematic strings + drone; marimba/pizzicato; downtempo electronic; jazzy walking bass + brushes; gentle glitch/IDM; soft chiptune; upbeat funk-pop; dark pulse (for tense races).
- Also vary key/scale, tempo (60-130 bpm) and timbres. Original synthesized audio only, never commercial or downloaded music.
- If the engine's E.Mix has no mood/scale/bpm/timbre parameters, add them (defaults must keep old episodes reproducible) and rotate them by day-of-year/episode.

## Caption style: new structure every post
- Rotate the structure (not used in the last 5 posts' `caption_style`): question-first; number-first hook; myth vs data; one-sentence story; then vs now; minimal two-liner; what it shows / what it doesn't; fact trio; cliffhanger ("who survives tomorrow?"); host voice.
- Vary line breaks, length (2-6 lines), closing-question wording, and hashtags (at least 3 of 5 differ from the previous 5 posts; max 5 hashtags). Do not open with the same first 3 words as any of the last 15 captions. Record `caption_style` in the json.
- Series captions may be re-worded freely in a new structure, but facts, names and results must stay exactly as in the json; no new numbers or real-world statistics unless sourced as the account's rules allow.

## Content uniqueness / shadowban safety
- No near-duplicate posts: new topic/matchup/seed, different layout or palette variant than the previous post of that series, new audio.
- Caption text similarity under 50% (difflib.SequenceMatcher) vs each of the last 20 captions; rewrite if higher.
- No engagement bait (no "like/follow/comment to win", no "tag a friend"), no links in captions, no spammy/irrelevant/banned hashtags, no other platforms' watermarks or logos.
- Replies to comments: never the same wording twice. One post per slot per day.
