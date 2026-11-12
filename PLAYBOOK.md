# aislop — viral sim Reels playbook (researched 2026-11-12)

## 1. What the 5 reference pages actually do
Public profile grids only (Instagram showed a login wall, so view counts were not visible; likes/comments were visible on individual reels).

| Page | Followers | Format | Hooks / callouts seen | Engagement seen |
|---|---|---|---|---|
| @geoclash.games | 27.1K | Numbered country-conquest episodes ("GeoClash Episode 54"), ~8 posts/day, link to a game site, "thanks supporters" posts | Episode number on the cover card; caption "Craziest episode ending... Episode 54" | Ep 54: 1.8K likes, 120 comments in 1 hour. Comments = people rooting for their country ("YES TAIWAN!!! THATS MY HOME", "Goodbye Japan") |
| @eterniq_visual | 115 | ~3/day physics loops: "Last one inside is OUT" country ring (Day 1, Day 2…), "Bigger eats smaller · arena keeps shrinking", ring-escape speedometer, "Which weight knocks it down?", 2ⁿ vs 1,000,000·n race | HUD counters ("Balls left: 40 · speed ×1.0"), question hooks, "Rooting for a country? Drop its flag 👇" | Day 2: 99 likes / 4 comments; a commenter keeps a running "Countries eliminated" tally |
| @chaos_boop | 29 | Suika-style "Match → merge" with themed tiers (cats, AI logos, real people's faces), territory capture "IS IT OVER? RED 90% / BLUE 10%", "Escape → double", "Will they meet?" | Big rule text at top, live % bars | Low |
| @visualanimationss | 261 | Neon rings: "EVERY BOUNCE = 2×" counter (256, 1,675…), "How many fit inside?", "Will it get out in time? every bounce lays a brick", string-art | "ALMOST..." teasers, "Guess the letter!", **comment-keyword funnel**: "Want to make your own? Comment SIM → DM with the exact prompt" | Low |
| @atc5.builds | 469 | "Math. Physics. Quant." 10,000-run Monte Carlo explainers (index-fund fees, casino, minimum payments, Monty Hall), "100 AIs learning to fly", color elimination rounds | Methodology in caption + pinned comment, "Follow for a new simulation every day", closing question ("Do you know what fee your fund charges?") | Low |

**Read:** only GeoClash shows real scale. Its engine is *identity + serial*: viewers pick a side (their country), episodes are numbered, and the comments become the show. The other four are small accounts posting high volume, so treat their mechanics as ideas, not proof.

## 2. Platform rules that shape the pipeline
- **Specs:** 1080×1920, H.264 + AAC; Reels accept 23–60 fps (30 is the usual default, 60 is supported). We render 60 fps CFR, BT.709, AAC 48 kHz, faststart, ~3 Mbps (6–7 MB per video).
- **Ranking:** Mosseri's top signals are watch time, likes per reach, and **sends per reach**; sends matter most for reaching non-followers. → Every video needs a "send this to…" moment and a reason to rewatch.
- **Skip rate** (leaving in the first 3 s) is now shown in Insights → frame 1 must already be moving with the question on screen.
- **Originality:** accounts that mostly post content copied from others lose recommendations, and Instagram matches near-duplicates on *audio and visual signals*. → Never clone a reference reel or reuse its audio. Our audio is synthesized per video; formats are re-skinned with our own data, look and rules.
- **Text on music-only reels** helped retention in Emplifi's study (+4% 3-s, +9.8% 30-s). That was Facebook Reels data, so treat it as directional for Instagram.
- **Safe zone:** keep title, counters and source inside the centre 3:4 (y 240–1680).

## 3. The addiction checklist (every video must hit ≥6)
1. **Motion + question in frame 1** (no intro, no logo).
2. **Visible rule** that compounds: "EVERY BOUNCE = 2×", "THE GAP GROWS AS STATES ESCAPE".
3. **Live HUD counter** that pulses on change (STILL INSIDE 37, BOUNCE 12, SPEED ×1.4).
4. **Pick-a-side identity hook:** states, regions, your planet → comments ("rooting for…").
5. **Escalation:** speed ramp, heartbeat that accelerates, riser into the reveal.
6. **Near-miss / cliffhanger beat:** "LAST TWO", "ALMOST..." + slow-mo before the outcome.
7. **Reveal card** with one .gov stat, then a **comment prompt** and a **send prompt**.
8. **Seamless loop:** last 0.35 s dissolves into frame 1 (rewatches count as watch time).
9. **Serial memory:** Day N, running tally, "50 return tomorrow" (the next spec is generated automatically).
10. **Event-locked sound:** every note is triggered by something on screen; melody = public-domain tune (Ode to Joy) or a rising arpeggio that modulates up.
11. **Credibility:** .gov source bar on every frame + methodology in the pinned comment (atc5 pattern).
12. **Cadence:** references post 3–8×/day. Start at 2–3/day across rotating styles, so the grid varies and no single format gets too repetitive.

## 4. Styles
| Style | Status | Reference | .gov data hook |
|---|---|---|---|
| `ring_elimination` | **built** | GeoClash / EterniQ | Census state population → circle size; Day N series with tally |
| `neon_doubling` | **built** | visualanimationss | Treasury debt, Census median income, DOL min wage as milestones; star polygon closes on the final bounce |
| `merge_ladder` | next | chaos_boop | NASA planet diameters (already pulled) → Pluto→Jupiter tiers |
| `monte_carlo_grid` | next | atc5.builds | SSA period life table → "10,000 65-year-olds: who's here at 90?" |
| `territory_capture` | next | chaos_boop / GeoClash | Census regions on a state tile-grid, live % bars |

## 5. Pipeline
```
data/build_data.py      .gov values -> CSV/JSON, aborts if sums/subtotals don't match
specs/*.json            one file per video (style, text, data, seed)
python3 make.py SPEC --stills   QA PNGs at key moments
python3 make.py SPEC            60 fps MP4 + cover + quiet-audio copy + post-notes (caption, pinned comment, audio brief)
python3 make.py SPEC --next     next episode spec (adds the eliminated state to the tally)
```
The ring style runs a deterministic physics sim, searches seeds for a photo-finish ending (last two escapes ≤3 s apart), then time-warps it: an ease-in from ×1.0, slow-mo for the last two, and a freeze on the result.

## 6. Ideas to test next
- Comment-keyword funnel ("Comment STATE and I'll DM the .gov data sheet") via a DM automation tool; set up by you, never auto-posted by Claude.
- A daily series slot (State Elimination Day N at the same hour) + 1–2 rotating one-offs.
- Re-pull the Treasury figure before any repost; rebuild Census data when Vintage 2026 lands (Dec 2026).

### Sources
Instagram original content guidelines (creators.instagram.com/original-content-guidelines) · PetaPixel/Tubefilter on the 2026-04-30 unoriginal-content expansion · Buffer, Sprout Social, Social Media Today (via PostEverywhere) on Mosseri's ranking signals · Metricool on Reels skip rate · Emplifi Facebook Reels retention study · Ayrshare/SocialPilot Reels media specs · Census NST-EST2025-ALLDATA · Treasury Debt to the Penny API · Census CB26-151 · DOL WHD minimum wage FAQ · NASA NSSDCA Planetary Fact Sheet.
