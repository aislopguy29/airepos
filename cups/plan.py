"""Cup Shuffle planner: deterministic 4x4 shell-game plan from a seed.
Cups only swap with an orthogonal neighbour (they orbit the pair's midpoint, so they never touch),
simultaneous swaps are kept >= 2 cells apart, and the ball cup is never idle too long, so a viewer
who really watches can always follow it. The answer is never shown in the video."""
import json, math, random

COLS = ROWS = 4
FPS = 30
T_SHUFFLE0 = 2.55          # first swap starts (after the camera pull-back and cup drop)
LEVELS = {                 # level -> (shuffle seconds, first swap dur, last swap dur, max pairs at once)
    1: (9.8, 0.52, 0.26, 1),
    2: (10.6, 0.50, 0.22, 2),
    3: (11.4, 0.48, 0.19, 2),
    4: (11.8, 0.46, 0.165, 3),
    5: (12.2, 0.44, 0.15, 3),
}

PALETTES = {   # cup, ball, accent (glow/text highlight), table, tray wood (light, dark), cup rough, cup metal
    "emerald":   dict(cup="#1f9a63", ball="#ffd23f", accent="#ffd23f", table="#10231c", wood=("#b07a46", "#6b3f1f"), rough=0.22, metal=0.0),
    "coral":     dict(cup="#ff5b4f", ball="#2fd4ff", accent="#2fd4ff", table="#1d1520", wood=("#c79a6b", "#7a4e2c"), rough=0.20, metal=0.0),
    "cobalt":    dict(cup="#2d5cf0", ball="#ffb000", accent="#ffb000", table="#0e1424", wood=("#a8774c", "#5e3a1e"), rough=0.18, metal=0.0),
    "sunflower": dict(cup="#f6b500", ball="#7a2cff", accent="#b483ff", table="#1b1630", wood=("#9b6b42", "#553218"), rough=0.24, metal=0.0),
    "plum":      dict(cup="#8f3cd8", ball="#3dff9a", accent="#3dff9a", table="#130f1f", wood=("#b98a5e", "#6e4426"), rough=0.20, metal=0.0),
    "porcelain": dict(cup="#efe8dc", ball="#ff2d55", accent="#ff4d6d", table="#1a1d24", wood=("#7c5536", "#3e2414"), rough=0.12, metal=0.0),
    "chrome":    dict(cup="#c9ced6", ball="#ff6a00", accent="#ff8a2a", table="#121418", wood=("#8e6440", "#4a2d16"), rough=0.16, metal=1.0),
    "cherry":    dict(cup="#d4202f", ball="#f4f1e8", accent="#ffe08a", table="#0f1a2a", wood=("#c08f5f", "#73492a"), rough=0.20, metal=0.0),
}

HOOKS = [  # (line, word to highlight)
    ("EYES ON THE BALL", "BALL"), ("DON'T BLINK", "BLINK"), ("FOLLOW IT TO THE END", "END"),
    ("WHERE DID IT GO?", "GO?"), ("STAY WITH IT", "IT"), ("IT ONLY GETS FASTER", "FASTER"),
    ("TRUST YOUR EYES", "EYES"), ("NO REWIND. NO SECOND LOOK.", "NO REWIND."), ("WATCH CLOSELY", "CLOSELY"),
    ("KEEP YOUR EYE ON IT", "EYE"), ("LOCKED ON?", "LOCKED"), ("ONE BALL. SIXTEEN CUPS.", "ONE BALL."),
]

def cell_xy(cell):
    return cell % COLS, cell // COLS

def neighbours(cell):
    c, r = cell_xy(cell); out = []
    for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        cc, rr = c + dc, r + dr
        if 0 <= cc < COLS and 0 <= rr < ROWS: out.append(rr * COLS + cc)
    return out

def cheb(a, b):
    (ca, ra), (cb, rb) = cell_xy(a), cell_xy(b)
    return max(abs(ca - cb), abs(ra - rb))

def make_plan(seed, level=3, palette=None, hook=None, episode=1):
    rng = random.Random(seed)
    shuffle_len, d0, d1, max_pairs = LEVELS[level]
    pal_name = palette or rng.choice(sorted(PALETTES))
    hook_i = hook if hook is not None else rng.randrange(len(HOOKS))
    ball_cup = rng.choice([5, 6, 9, 10])            # start near the middle so the close-up opener is centred
    cell_of = list(range(16)); cup_at = list(range(16))
    events, t, idle, last_pairs = [], T_SHUFFLE0, 0, []
    t_end = T_SHUFFLE0 + shuffle_len
    while True:
        u = (t - T_SHUFFLE0) / shuffle_len
        dur = d0 + (d1 - d0) * (u ** 0.8)
        if t + dur > t_end: break
        n_pairs = 1
        if max_pairs >= 2 and u > 0.28: n_pairs = 2 if rng.random() < 0.65 else 1
        if max_pairs >= 3 and u > 0.62: n_pairs = rng.choice((2, 3, 3))
        ball_cell = cell_of[ball_cup]
        want_ball = idle >= 2 or rng.random() < 0.42
        pairs, used = [], []
        def ok(a, b):
            if any(cheb(a, x) < 2 or cheb(b, x) < 2 for x in used): return False
            # don't repeat exactly the same pair back-to-back (it looks like a stall)
            return not any({a, b} == set(p) for p in last_pairs)
        if want_ball:
            opts = [n for n in neighbours(ball_cell) if ok(ball_cell, n)]
            if opts:
                b = rng.choice(opts); pairs.append((ball_cell, b)); used += [ball_cell, b]
        tries = 0
        while len(pairs) < n_pairs and tries < 200:
            tries += 1
            a = rng.randrange(16)
            if a == ball_cell and not want_ball: continue
            nb = [n for n in neighbours(a) if ok(a, n) and (want_ball or n != ball_cell)]
            if not nb or any(cheb(a, x) < 2 for x in used): continue
            b = rng.choice(nb); pairs.append((a, b)); used += [a, b]
        if not pairs: t += 0.02; continue
        ev_pairs = []
        for a, b in pairs:
            ca, cb = cup_at[a], cup_at[b]
            side = rng.choice((-1, 1))
            ev_pairs.append([ca, cb, side])
            cup_at[a], cup_at[b] = cb, ca; cell_of[ca], cell_of[cb] = b, a
        involved = any(ball_cup in p[:2] for p in ev_pairs)
        idle = 0 if involved else idle + 1
        events.append(dict(t0=round(t, 4), dur=round(dur, 4), pairs=ev_pairs, ball=involved))
        last_pairs = [tuple(p) for p in pairs]
        gap = 0.05 * (1 - u) ** 2
        t += dur + gap
    shuffle_end = events[-1]["t0"] + events[-1]["dur"]
    badge_t = shuffle_end + 0.35
    end_t = badge_t + 16 * 0.035 + 1.55
    answer_cell = cell_of[ball_cup]
    return dict(
        version=1, seed=seed, level=level, episode=episode, palette=pal_name, colors=PALETTES[pal_name],
        hook=HOOKS[hook_i][0], hook_hi=HOOKS[hook_i][1], hook_index=hook_i,
        ball_cup=ball_cup, events=events, n_swaps=sum(len(e["pairs"]) for e in events),
        ball_swaps=sum(1 for e in events if e["ball"]),
        t_lower=(1.55, 2.15), t_shuffle=(T_SHUFFLE0, round(shuffle_end, 3)), t_badges=round(badge_t, 3),
        duration=round(end_t, 3), fps=FPS, frames=int(math.ceil(end_t * FPS)),
        answer=answer_cell + 1,       # numbers run 1-16, left to right, back row first
    )

if __name__ == "__main__":
    import sys
    p = make_plan(int(sys.argv[1]) if len(sys.argv) > 1 else 7, int(sys.argv[2]) if len(sys.argv) > 2 else 3)
    print(json.dumps({k: v for k, v in p.items() if k != "events"}, indent=1))
    print("events", len(p["events"]))
