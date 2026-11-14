# Posting setup — 6 unique videos a day, cross-posted

Every slot in `distribution.json` produces ONE video and sends it to that slot's `targets`.
A video is never posted twice to the same platform. Facebook mirrors whatever Instagram gets.

| Slot | ET | Producer | Goes to |
|---|---|---|---|
| p1 | 09:12 | puzzles (spot the odd one) | IG @thatdatalover, FB, **YouTube**, TikTok |
| s1 | 11:41 | lab (sim video) | IG eas.ydata, FB, TikTok |
| p2 | 13:23 | puzzles (eye-jump drill) | IG @thatdatalover, FB, TikTok |
| s2 | 15:47 | lab (sim video) | IG eas.ydata, FB |
| p3 | 18:14 | puzzles (spot the odd one) | IG @thatdatalover, FB, TikTok |
| s3 | 20:36 | lab (sim video) | IG eas.ydata, FB, TikTok |

Daily: 3 + 3 on the two Instagram accounts, 6 on Facebook, **1 YouTube** (p1 only), 5 TikTok.
p1 is the single YouTube post of the day, so it should be the strongest build.

## Which tool posts where
- **Instagram** — Windsor `execute_action` / `create_video_post`. Windsor is the only tool here
  that can reply to Instagram comments.
- **Facebook, YouTube, TikTok** — Metricool `createScheduledPost`, brand `8071801`.
  Windsor CANNOT post video to Facebook (photos and text only) and has no YouTube or TikTok
  write actions at all, so Metricool is the only path for those three.

## Connections still needed
- Windsor Instagram: accounts must be selected at onboard.windsor.ai (currently unconfigured —
  every write fails with "No instagram accounts are configured").
- Metricool brand 8071801: has TikTok + YouTube. Facebook page is NOT connected yet.
Until a target is connected, its post is recorded as pending (see below) rather than lost.

## Pending queue
If a target cannot be posted, the slot writes `pending/<date>_<slot>_<target>.json`
({video, caption, target, reason, created}) and carries on with the other targets.
The catch-up task retries the queue and deletes each file once it posts.

## Rules for every output
- No watermarks: no persistent footer, handle or branding chip on any video or image.
- Per-platform copy: each target gets its own caption/title written for that platform.
  Never post byte-identical text to two platforms.
- Follow VARIETY_RULES.md: new music style, new caption structure, unique content per post.
