"""Cup Shuffle: one command = one finished post.
  python3 -I make.py --account eas|tdl --out DIR [--seed N --level L --episode E --state state/cups_<acct>.json]
Builds plan -> synced audio -> 3D frames (headless Chromium WebGL) -> MP4 (1080x1920, 30 fps, H.264 + AAC) -> verification
-> caption/comment json.  The answer is never rendered anywhere in the video; it only goes into the json and into the NEXT post's caption.
Needs: node + global playwright (preinstalled), ffmpeg, numpy.

2026-11-17 revision: easier + more varied. Slower swaps and at most 2 simultaneous swaps (see LEVELS override below), a level mix that is
mostly warm-up/easy/medium with only an occasional hard one, plus extra palettes, hooks, captions and call-outs so posts feel different."""
import argparse, json, os, random, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import plan as PL, audio as AU

# --- difficulty: level -> (shuffle seconds, first swap dur, last swap dur, max pairs at once). Longer swap durations = easier to track.
PL.LEVELS.update({
    1: (9.4, 0.66, 0.40, 1),    # warm-up: one swap at a time, slow
    2: (10.0, 0.62, 0.34, 1),   # easy
    3: (10.6, 0.58, 0.30, 2),   # medium
    4: (11.0, 0.54, 0.26, 2),   # hard (occasional)
    5: (11.4, 0.52, 0.23, 2),   # expert (rare)
})
# --- variety: extra palettes and hooks (highlight word must be a substring of the line)
PL.PALETTES.update({
    "mint":      dict(cup="#3ddcb4", ball="#ff5d8f", accent="#ff5d8f", table="#0d1f21", wood=("#b58455", "#68401f"), rough=0.20, metal=0.0),
    "tangerine": dict(cup="#ff8a1f", ball="#6a4bff", accent="#9b86ff", table="#1b1226", wood=("#a9774a", "#5c3719"), rough=0.22, metal=0.0),
    "ice":       dict(cup="#8ed8ff", ball="#ff3b6b", accent="#ff6b8e", table="#0e1a2b", wood=("#9c6e45", "#52311a"), rough=0.14, metal=0.0),
})
PL.HOOKS.extend([
    ("EASY ONE. OR IS IT?", "EASY"), ("CAN YOU KEEP UP?", "KEEP"), ("ONLY THE FOCUSED GET THIS", "FOCUSED"),
    ("WARM-UP ROUND", "WARM-UP"), ("FOLLOW THE BALL HOME", "HOME"), ("BET YOU GET THIS ONE", "BET"),
])

# mostly easy: 1 warm-up, 2 easy, 3 medium, with a hard one now and then
LEVEL_SEQ = [1, 2, 2, 3, 1, 2, 3, 2, 3, 4, 2, 1, 3, 2, 3, 4, 2, 3, 1, 3]
LEVEL_NAME = {1: "Warm-up", 2: "Easy", 3: "Medium", 4: "Hard", 5: "Expert"}
HASH_POOL = ["#cupgame", "#shellgame", "#findtheball", "#eyetest", "#focuschallenge", "#brainteaser", "#trackingchallenge",
             "#puzzlechallenge", "#satisfying", "#braintest", "#visualtest", "#focustest", "#guessthecup", "#oddlysatisfying",
             "#challenge", "#guessinggame", "#quickgame"]
# caption structures: each returns (first line, body). {p} = previous answer line (may be empty).
def captions(ep, level, account, prev, rng):
    pa = f"\n\nLast puzzle's answer: cup {prev} ✅" if prev else ""
    nm = LEVEL_NAME.get(level, str(level))
    asks = ["Which cup is it? Drop your number below 👇", "Lock in your number and comment it 👇", "Cup number? Answer in the comments 👇",
            "Where did the ball end up? Number below 👇", "Comment the cup you landed on 👇",
            "Left side or right side? Then give me the exact number 👇", "Got it? Prove it with the cup number 👇",
            "No cheating: type your number before you scroll 👇"]
    heads = {
        1: ["16 cups. 1 ball. Can you follow it? 👀", "Eyes on the ball. No rewind.", "Think you can keep up? 🔴", "Don't blink. Seriously. 👀",
            "One look under the cup, then it's all on you", "Easy one? Let's see 😏", "Bet you get this one"],
        2: ["{n} round. Think you can get it?", "{n} focus test. How many of you will get it?", "{n} mode: watch it, then answer.",
            "Today's puzzle is {n}. Your move."],
    }
    h = rng.choice(heads[1] + [x.format(n=nm) for x in heads[2]])
    body = {
        0: f"One ball, sixteen cups. Puzzle #{ep}, {nm} mode.\n\n{rng.choice(asks)}{pa}",
        1: f"Puzzle #{ep} · {nm}\nWatch the ball, then answer once the numbers appear.\n\n{rng.choice(asks)}{pa}",
        2: f"Watch it go under the cup. Keep track through every swap. Puzzle #{ep} ({nm}).\n\n{rng.choice(asks)}{pa}",
    }[(ep + (0 if account == "eas" else 1)) % 3]
    return h, body

def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode: raise SystemExit(f"FAILED: {' '.join(map(str, cmd))[:200]}")
    return r

def verify_plan(p):
    """Independent replay of the events -> where the ball ends up. Must equal plan['answer'] (guards the renderer/answer link)."""
    cell = list(range(16))
    for e in p["events"]:
        for a, b, _ in e["pairs"]: cell[a], cell[b] = cell[b], cell[a]
    ans = cell[p["ball_cup"]] + 1
    assert ans == p["answer"], (ans, p["answer"])
    # every swap pair must be orthogonal neighbours and simultaneous pairs must be disjoint + not adjacent
    pos = list(range(16))
    for e in p["events"]:
        cells = []
        for a, b, _ in e["pairs"]:
            ca, cb = pos[a], pos[b]; assert PL.cheb(ca, cb) == 1 and (ca % 4 == cb % 4 or ca // 4 == cb // 4); cells += [ca, cb]
        for i in range(0, len(cells), 2):
            for j in range(i + 2, len(cells)): assert PL.cheb(cells[i], cells[j]) >= 2, "simultaneous swaps too close"
        for a, b, _ in e["pairs"]: pos[a], pos[b] = pos[b], pos[a]
    return ans

def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,avg_frame_rate,pix_fmt:format=duration,size",
                                   "-of", "json", path]); j = json.loads(out)
    v = next(s for s in j["streams"] if s["codec_type"] == "video"); a = [s for s in j["streams"] if s["codec_type"] == "audio"]
    num, den = map(int, v["avg_frame_rate"].split("/")); fps = num / den
    assert (v["width"], v["height"]) == (1080, 1920), "size"; assert abs(fps - 30) < 0.5, f"fps {fps}"; assert a and a[0]["codec_name"] == "aac", "audio"
    d = float(j["format"]["duration"]); sz = int(j["format"]["size"]); assert 12 <= d <= 30, f"duration {d}"; assert sz < 40e6, f"size {sz}"
    vol = subprocess.run(["ffmpeg", "-i", path, "-af", "volumedetect", "-vn", "-f", "null", "-"], capture_output=True, text=True).stderr
    mean = float(vol.split("mean_volume:")[1].split("dB")[0]); assert mean > -40, f"silent audio {mean}"
    return dict(duration=round(d, 2), size_mb=round(sz / 1e6, 1), fps=round(fps, 2), mean_db=mean)

def prune_posted_videos(keep_dir):
    """Storage hygiene: delete (git rm, staged) the video of every cups post that already has a media_id, so the repo holds only the video
    currently being posted. Code, post.json and state files are kept. Never fatal: any problem just skips pruning."""
    try:
        root = subprocess.check_output(["git", "-C", HERE, "rev-parse", "--show-toplevel"], text=True).strip()
        tracked = subprocess.check_output(["git", "-C", root, "ls-files", "cups/posts"], text=True).split("\n")
        keep = os.path.relpath(os.path.abspath(keep_dir), root)
        gone = []
        for f in tracked:
            if not f.endswith("/video.mp4") or os.path.dirname(f) == keep: continue
            pj = os.path.join(root, os.path.dirname(f), "post.json")
            try: posted = bool(json.load(open(pj)).get("media_id"))
            except Exception: posted = False
            if posted: gone.append(f)
        for i in range(0, len(gone), 50):
            subprocess.run(["git", "-C", root, "rm", "-q", "--"] + gone[i:i + 50], check=False)
        print(f"pruned {len(gone)} posted videos", file=sys.stderr)
    except Exception as e:
        print(f"prune skipped: {e}", file=sys.stderr)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--account", default="eas", choices=["eas", "tdl"]); ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int); ap.add_argument("--level", type=int); ap.add_argument("--episode", type=int); ap.add_argument("--state")
    ap.add_argument("--palette"); ap.add_argument("--keep-frames", action="store_true"); a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    prune_posted_videos(a.out)
    st = json.load(open(a.state)) if a.state and os.path.exists(a.state) else {"episode": 0, "answers": {}, "palettes": [], "hooks": []}
    ep = a.episode or st["episode"] + 1
    seed = a.seed or random.SystemRandom().randrange(10000, 99999)
    level = a.level or LEVEL_SEQ[(ep - 1) % len(LEVEL_SEQ)]
    rng = random.Random(seed * 7 + ep)
    # variety: avoid the last 4 palettes / 5 hooks used on this account
    pals = [p for p in sorted(PL.PALETTES) if p not in st["palettes"][-4:]] or sorted(PL.PALETTES)
    hooks = [i for i in range(len(PL.HOOKS)) if i not in st["hooks"][-5:]] or list(range(len(PL.HOOKS)))
    plan = PL.make_plan(seed, level, palette=a.palette or rng.choice(pals), hook=rng.choice(hooks), episode=ep)
    answer = verify_plan(plan)
    pj, wav, frames, mp4 = [os.path.join(a.out, n) for n in ("plan.json", "audio.wav", "frames", "video.mp4")]
    json.dump(plan, open(pj, "w"))
    mood = AU.build(plan, wav)
    env = dict(os.environ); env["NODE_PATH"] = subprocess.check_output(["npm", "root", "-g"], text=True).strip()
    t0 = time.time(); run(["node", os.path.join(HERE, "render.js"), pj, frames, "0", str(plan["frames"]), "1"], env=env)
    print(f"rendered {plan['frames']} frames in {time.time() - t0:.0f}s", file=sys.stderr)
    run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(plan["fps"]), "-i", os.path.join(frames, "%05d.jpg"), "-i", wav,
         "-vf", "scale=in_range=pc:out_range=tv:out_color_matrix=bt709,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-profile:v", "high", "-level", "4.2", "-g", str(plan["fps"] * 2), "-bf", "2", "-colorspace", "bt709", "-color_primaries", "bt709",
         "-color_trc", "bt709", "-r", str(plan["fps"]), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest",
         "-movflags", "+faststart", mp4 + ".part.mp4"]); os.replace(mp4 + ".part.mp4", mp4)
    meta = probe(mp4)
    if not a.keep_frames:
        import shutil; shutil.rmtree(frames, ignore_errors=True)
    prev = st["answers"].get(str(ep - 1))
    h, body = captions(ep, level, a.account, prev, rng)
    tags = rng.sample(HASH_POOL, 4)
    caption = f"{h}\n\n{body}\n\n{' '.join(tags)}"
    comment = rng.choice(["Answer drops in the next post. Drop your number before then 👇", "Reveal comes with the next puzzle. Number below 👇",
                          "Lock your answer in now. The next post shows the result 👇"])
    post = dict(id=f"cups_{a.account}_{ep:03d}", account=a.account, episode=ep, level=level, seed=seed, palette=plan["palette"], hook=plan["hook"],
                music=mood, caption=caption, comment=comment, thumb_offset_ms=1800, video=mp4, answer=answer, **meta)
    json.dump(post, open(os.path.join(a.out, "post.json"), "w"), indent=1)
    if a.state:
        st["episode"] = ep; st["answers"][str(ep)] = answer; st["palettes"] = (st["palettes"] + [plan["palette"]])[-8:]; st["hooks"] = (st["hooks"] + [plan["hook_index"]])[-8:]
        os.makedirs(os.path.dirname(a.state) or ".", exist_ok=True); json.dump(st, open(a.state, "w"), indent=1)
    print("POST_JSON=" + json.dumps({k: v for k, v in post.items() if k != "answer"}))   # answer stays out of stdout logs on purpose
    print("OK", file=sys.stderr)

if __name__ == "__main__": main()
