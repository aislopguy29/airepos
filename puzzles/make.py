# usage: python3 -I puzzles/make.py <out_dir> <slot> [seed]
# Generates a fresh daily "spot the odd one" puzzle: script json + caption json.
# Anti-repeat: reads past puzzle jsons in the repo and avoids recent themes/diff sets.
import sys, json, os, glob, random, hashlib, datetime
out_dir, slot = sys.argv[1], sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else int(hashlib.sha1((out_dir+slot).encode()).hexdigest()[:8], 16)
R = random.Random(seed)
os.makedirs(out_dir, exist_ok=True)
PAL = {
 "candy":   ["#ff6fa5","#2fd9ab","#ffc233","#4fb6ff","#9b7bff","#ff7f4d"],
 "sorbet":  ["#ff9ec4","#8ee6c8","#ffd98a","#9fd4ff","#c6b3ff","#ffb08a"],
 "pop":     ["#ff5470","#00d0a3","#ffd000","#2ea8ff","#a855f7","#ff7a00"],
 "mellow":  ["#f49ac1","#7fd8bd","#f6cf7a","#8cc6f0","#b3a4e8","#f0a080"],
}
SHAPES = ["circle","square","star","blob"]
DIFFS = [
 ("tilt",  {"tilt": True},  "ONE IS UPSIDE DOWN"),
 ("frown", {"frown": True}, "ONE IS NOT SMILING"),
 ("eye",   {"eye": True},   "ONE HAS A TINY EYE"),
 ("wink",  {"wink": True},  "ONE IS WINKING"),
 ("size",  {"size": True},  "ONE IS SMALLER"),
 ("flat",  {"flat": True},  "ONE HAS A STRAIGHT MOUTH"),
 ("extra", {"extra": True}, "ONE HAS A NOSE"),
 ("rot",   {"rot": 0.42},   "ONE IS TILTED"),
 ("col",   None,            "ONE IS A DIFFERENT COLOUR"),
]
TITLES = ["SPOT THE ODD ONE","FIND THE ODD ONE","ONLY 1% CAN SPOT IT","SPOT THE DIFFERENT ONE","CAN YOU FIND IT?"]
SUBS   = ["{n} rounds · gets harder","{n} rounds · harder each time","{n} levels · speed test","{n} rounds · don't blink"]
# anti-repeat from past puzzles
past = []
for f in sorted(glob.glob("puzzles/*/*.json"))[-14:]:
    try: past.append(json.load(open(f)))
    except Exception: pass
recent_diffs = [set(p.get("diff_ids", [])) for p in past[-3:]]
recent_shapes = [p.get("shape") for p in past[-3:]]
recent_pals = [p.get("palette") for p in past[-3:]]
recent_titles = [p.get("title") for p in past[-5:]]
shape = R.choice([s for s in SHAPES if s not in recent_shapes] or SHAPES)
palname = R.choice([k for k in PAL if k not in recent_pals] or list(PAL))
pal = PAL[palname]
title = R.choice([t for t in TITLES if t not in recent_titles] or TITLES)
nrounds = R.choice([4,4,5])
for _ in range(40):
    picked = R.sample(DIFFS, nrounds)
    ids = set(d[0] for d in picked)
    if not any(len(ids & r) >= nrounds-1 for r in recent_diffs): break
# hard ones last
order = {"col":0,"tilt":1,"frown":2,"rot":3,"size":4,"flat":5,"wink":6,"extra":7,"eye":8}
picked.sort(key=lambda d: order.get(d[0], 5))
rounds = []
for i, (did, diff, prompt) in enumerate(picked):
    cols = 4 + i; rows = cols + 2
    col = pal[i % len(pal)]
    if did == "col":
        alt = R.choice([c for c in pal if c != col])
        diff = {"col": alt}
    rounds.append({"cols": cols, "rows": rows,
                   "odd": [R.randrange(cols), R.randrange(rows)],
                   "prompt": prompt, "diff": diff, "col": col, "shape": shape})
search = round(R.choice([2.7, 2.9, 3.1]), 1)
script = {"title": title, "title2": f"IN {int(search)} SECONDS", "shape": shape,
          "sub": R.choice(SUBS).format(n=nrounds), "footer": "new puzzle every day",
          "search": search, "rounds": rounds}
json.dump(script, open(os.path.join(out_dir, f"{slot}_script.json"), "w"), indent=1)
HOOKS = [
 "Only 1 in 10 people get all {n}.",
 "{n} rounds. Most people miss the last one.",
 "Your eyes have {s} seconds per round.",
 "Round {n} breaks everyone.",
 "Think you're fast? Prove it.",
]
CLOSERS = [
 "Drop your score below.",
 "Comment how many you spotted.",
 "How many did you get?",
 "Tell me your score — be honest.",
]
TAGSETS = [
 ["#spotthedifference","#puzzle","#brainteaser","#visualpuzzle","#thatdatalover"],
 ["#findtheodd","#eyetest","#puzzletime","#brainrot","#thatdatalover"],
 ["#spotit","#attentiontest","#quiz","#focus","#thatdatalover"],
 ["#oddoneout","#braingame","#reactiontest","#challenge","#thatdatalover"],
]
recent_caps = [p.get("caption","") for p in past[-5:]]
hook = R.choice(HOOKS).format(n=nrounds, s=search)
closer = R.choice(CLOSERS)
tags = R.choice([t for t in TAGSETS if " ".join(t) not in " ".join(recent_caps)] or TAGSETS)
caption = f"{hook}\n\n{title.title()} — {nrounds} rounds, {search}s each, harder every time.\n\n{closer}\n\n" + " ".join(tags)
meta = {"slot": slot, "title": title, "shape": shape, "palette": palname,
        "diff_ids": [d[0] for d in picked], "rounds": nrounds, "search": search,
        "seed": seed, "caption": caption, "caption_style": "hook+format+score CTA",
        "music_style": "slop_brainrot", "theme": f"{shape} faces / {palname}",
        "viral_reason": "timed spot-the-difference with retention hooks",
        "thumb_offset_ms": 900, "created": datetime.date.today().isoformat()}
json.dump(meta, open(os.path.join(out_dir, f"{slot}.json"), "w"), indent=1)
print("SCRIPT=" + os.path.join(out_dir, f"{slot}_script.json"))
print("META=" + os.path.join(out_dir, f"{slot}.json"))
