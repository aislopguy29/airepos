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

## Subject variety: entrants do NOT have to be countries or states
- For every NEW lab type, YouTube LAB short and encore, pick the contestants/theme creatively and rotate it; do not use countries/states/flags two posts in a row, and avoid them unless the type needs them. Check the last 10 posts' `theme` in lab/*/*.json first.
- Theme ideas: animals (duck vs penguin vs sloth), foods (pizza vs taco vs sushi), planets and moons, fruits, colors/paint blobs, emoji faces, fantasy creatures (dragons, slimes, robots), vehicles, sports balls, musical instruments, weather, candy, board-game pieces, dinosaurs, dice/cards, pixel heroes, shapes with personalities, mythical gods, ocean creatures, fonts, letters/numbers, cartoon-style original mascots.
- Original/generic characters only (no trademarked characters, logos, brands or real people). No real-world statistics.
- Mix up the framing too: tournament bracket, survival, race, tug of war, sorting, maze, territory grab, rhythm, satisfying fill. Record `theme` in the post json.
- State Elimination, Crown Race and Country Clash keep their fixed premise; Country Clash ends after day 7.

## Viral-only themes (overrides the open theme list above)
Only pick a theme with a real reason to expect strong reach. Choose it this way, in order:
1. Trend evidence: read the Project doc aislop/research/latest.md (weekly trend learning) and use the hooks/formats/themes it lists as winning right now.
2. Own results: Windsor get_data (instagram, eas.ydata account, last_30dT: media_views, likes, comments, shares/saves if available) -> rank past posts by (views + 20*likes + 50*comments) per hour; reuse the winning `theme` families (and drop the ones that flopped; two flops in a row = retire that theme for 30 days).
3. Proven evergreen viral categories as the fallback: cute/funny animals, food showdowns (pizza vs burgers etc.), "which one would you pick" matchups, nostalgic items (retro games, snacks, toys, cartoons-in-spirit), satisfying fills/sorting/ASMR-style loops, underdog-vs-giant, "last survivor" with relatable characters, rhythm/melody loops, size/scale comparisons, glow-ups.
Each post must carry: a relatable theme anyone gets in under 1 second, a hook in the first 1.5 s (clear stakes or question on screen), an obvious favorite/underdog to root for, a payoff or twist in the last third, a comment-driving question (pick your side) without begging for engagement, and a loop-friendly ending. Skip niche, abstract or confusing themes.
Record `theme` and `viral_reason` (which rule above chose it) in the post json. Nobody can guarantee virality; the rotation just keeps betting on what the data shows works.
