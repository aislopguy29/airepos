# aislop daily auto-posting

## How it works (each scheduled run is a fresh cloud session)
1. Attach the public GitHub repo `OWNER/REPO` with push access (add_repo), clone it, cd into it.
2. `python3 -I daily.py <slot>` renders today's episode (60 fps, ~15-25 s) into `posts/YYYY-MM-DD_<slot>.mp4` + `.json`
   and advances `state/series_<slot>.json`. It is idempotent: a re-run on the same day re-prints the same post.
3. Commit `posts/` + `state/` and push to `main`.
4. Video URL = `https://raw.githubusercontent.com/OWNER/REPO/main/<video path>`.
5. Windsor.ai `instagram` → `create_video_post` on account `ACCOUNT_ID` with `video_url`, `caption`, `thumb_offset` (ms), `share_to_feed: true`.
6. Windsor `create_comment` on the returned media id with the `comment` text (the API can't pin it, so pin it in the app if you want).
7. Record the media id in `posts/YYYY-MM-DD_<slot>.json` (`"media_id"`), commit and push. If a json already has a media_id, the slot was already posted today: do nothing.

| Slot | Time (ET) | Series | Rule |
|---|---|---|---|
| a | ~12:21 pm | STATE ELIMINATION | last state inside is OUT, the rest return tomorrow |
| b | ~7:17 pm | CROWN RACE | last state inside WINS and leaves the race |

A season ends when fewer than 3 states remain (≈49 days), and then Season 2 starts with all 51.
When new styles are built, slot b can rotate them in.

## One-time setup (user)
- Connect GitHub to claude.ai and create a **public** repo (raw.githubusercontent.com only serves public repos).
- Connect the target Instagram Business/Creator account in Windsor.ai.
- Storage: each post is ~6-7 MB, so ~13 MB/day. Old videos can be deleted from `posts/` after they're published, but git history still grows. Move to a bucket later if the repo nears 1 GB.

## Scheduled-task prompt (fill OWNER/REPO/ACCOUNT_ID)
```
Post today's aislop Reel for slot <a|b>. Steps:
1) add_repo OWNER/REPO with access "push", clone it, cd into it.
2) Run: python3 -I daily.py <slot>  (stderr is progress). Parse the line starting with POST_JSON=.
   If that json already has "media_id", stop: it's already posted.
3) Check the render: ffprobe shows 1080x1920, 60 fps, an AAC stream, and a duration of 8-40 s. If not, stop and report.
4) git add posts state; commit "post <date> slot <slot>"; push to main.
5) video_url = https://raw.githubusercontent.com/OWNER/REPO/main/<video>. Wait ~30 s after the push.
6) Windsor.ai create_video_post: connector instagram, account ACCOUNT_ID,
   params {video_url, caption, thumb_offset: thumb_offset_ms, share_to_feed: true}.
   If it fails with a fetch/format error, retry once after 60 s; then stop and report the error.
7) Windsor.ai create_comment on the new media id with the json's "comment".
8) Write "media_id" into posts/<date>_<slot>.json, commit, push.
9) Send the user a 2-line summary (series, day, result state, media id) plus the MP4 via SendUserFile.
Never change captions to add numbers that aren't in the json. Every number comes from the Census data in data/.
```
