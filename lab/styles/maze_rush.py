"""LAB STYLE maze_rush: a 17x17 maze carves itself outward from a glowing core, then 8 flag explorers start on the rim
and search for the core at the same speed (random depth-first explorers with a slight pull toward the centre).
Live trails (bright = current route, dim = abandoned dead ends) form a transit-map ribbon; top HUD = 8 vertical
"closeness" meters; slow-mo zoom on the core for the final steps; winner's route traced in gold; result card.
Pure simulation + chance: no data."""
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import engine as E
from engine import W, H, FPS

EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
POOL = [("PORTUGAL", "🇵🇹"), ("GREECE", "🇬🇷"), ("VIETNAM", "🇻🇳"), ("COLOMBIA", "🇨🇴"), ("CHILE", "🇨🇱"), ("PERU", "🇵🇪"),
        ("KOREA", "🇰🇷"), ("IRELAND", "🇮🇪"), ("THAILAND", "🇹🇭"), ("BRAZIL", "🇧🇷"), ("MEXICO", "🇲🇽"), ("JAPAN", "🇯🇵"),
        ("INDIA", "🇮🇳"), ("EGYPT", "🇪🇬"), ("SWEDEN", "🇸🇪"), ("CANADA", "🇨🇦"), ("GERMANY", "🇩🇪"), ("NIGERIA", "🇳🇬"),
        ("ARGENTINA", "🇦🇷"), ("AUSTRALIA", "🇦🇺")]
N, GN, CS = 8, 17, 56
MX0, MY0 = (W - GN * CS) // 2, 580                      # maze top-left (px); maze spans x 64..1016, y 580..1532
PAD = 8; RX0, RY0, RS = MX0 - PAD, MY0 - PAD, GN * CS + 2 * PAD   # maze layer rect
CORE = (GN // 2, GN // 2)
STARTS = [(0, 0), (8, 0), (16, 0), (16, 8), (16, 16), (8, 16), (0, 16), (0, 8)]   # clockwise from top-left
COLS = [(255, 84, 84), (255, 160, 50), (250, 228, 70), (80, 230, 120), (70, 215, 255), (105, 135, 255), (190, 112, 255), (255, 110, 205)]
T_GO, T_GEN, RACE_TARGET = 2.6, 2.05, 13.0
GOLD = (255, 212, 90)

def cxy(c, k=None):                                     # cell centre in maze-layer coords (+ lane offset per agent)
    o = 0 if k is None else (k - 3.5) * 2.7
    return (PAD + (c[0] + .5) * CS + o, PAD + (c[1] + .5) * CS + o)

def gen_maze(rng, loops=10, p_new=.75):
    """Growing-tree maze carved outward from the core. Returns adjacency, carve order, loop edges."""
    adj = {(x, y): set() for x in range(GN) for y in range(GN)}; seen = {CORE}; act = [CORE]; order = []
    while act:
        i = len(act) - 1 if rng.random() < p_new else int(rng.integers(0, len(act))); c = act[i]
        nb = [(c[0] + dx, c[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        nb = [n for n in nb if n in adj and n not in seen]
        if not nb: act.pop(i); continue
        n = nb[int(rng.integers(0, len(nb)))]; adj[c].add(n); adj[n].add(c); seen.add(n); act.append(n); order.append((c, n))
    extra = []; cand = [((x, y), (x + 1, y)) for x in range(GN - 1) for y in range(GN)] + [((x, y), (x, y + 1)) for x in range(GN) for y in range(GN - 1)]
    rng.shuffle(cand)
    for a, b in cand:
        if len(extra) >= loops: break
        if b in adj[a] or CORE in (a, b): continue
        adj[a].add(b); adj[b].add(a); extra.append((a, b))
    return adj, order, extra

def bfs(adj, src):
    d = {src: 0}; q = [src]
    for c in q:
        for n in adj[c]:
            if n not in d: d[n] = d[c] + 1; q.append(n)
    return d

def simulate(seed, beta=.25, max_steps=400):
    rng = np.random.default_rng(seed); adj, order, extra = gen_maze(rng); dist = bfs(adj, CORE)
    stacks = [[s] for s in STARTS]; vis = [{s} for s in STARTS]; cells = [[s] for s in STARTS]; edges = [[] for _ in range(N)]
    open_e = [dict() for _ in range(N)]; win = None
    for s in range(max_steps):
        for k in range(N):
            cur = stacks[k][-1]; opts = [n for n in adj[cur] if n not in vis[k]]
            if opts:
                dc = math.hypot(cur[0] - CORE[0], cur[1] - CORE[1])
                w = np.array([math.exp(-beta * (math.hypot(n[0] - CORE[0], n[1] - CORE[1]) - dc)) for n in opts]); w /= w.sum()
                n = opts[int(rng.choice(len(opts), p=w))]; stacks[k].append(n); vis[k].add(n)
                edges[k].append([cur, n, s, None]); open_e[k][(cur, n)] = len(edges[k]) - 1
            else:
                stacks[k].pop(); n = stacks[k][-1]; edges[k][open_e[k][(n, cur)]][3] = s
            cells[k].append(n)
            if n == CORE and win is None: win = k
        if win is not None:
            return dict(adj=adj, order=order, extra=extra, dist=dist, cells=cells, edges=edges, win=win, S=s + 1, path=list(stacks[win]))
    return None

def analyse(sim):
    cells, dist, S, win = sim["cells"], sim["dist"], sim["S"], sim["win"]
    D = np.array([[dist[c] for c in cells[k]] for k in range(N)])            # (N, S+1)
    lead = []; cur = int(np.argmin(D[:, 0]))
    for s in range(S + 1):
        m = D[:, s].min()
        if D[cur, s] > m: cur = int(np.argmin(D[:, s]))
        lead.append(cur)
    changes = sum(1 for a, b in zip(lead, lead[1:]) if a != b)
    fin = D[:, S].copy(); fin[win] = -1; order = [win] + [int(k) for k in np.argsort(fin, kind="stable") if k != win]
    mid = D[:, S // 2]; mid_rank = int((mid < mid[win]).sum())
    dead = []                                                                 # back-runs per agent
    for k in range(N):
        e = sim["edges"][k]; backs = sorted(x[3] for x in e if x[3] is not None); runs = []; st = None; ln = 0; prev = -9
        for b in backs:
            if b == prev + 1: ln += 1
            else:
                if st is not None: runs.append((st, ln))
                st, ln = b, 1
            prev = b
        if st is not None: runs.append((st, ln))
        dead.append(runs)
    return dict(D=D, lead=lead, changes=changes, order=order, mid_rank=mid_rank, dead=dead, d2=int(D[order[1], S]))

def pick(seed0, tries=300, log=print):
    best = None
    for seed in range(seed0, seed0 + tries):
        sim = simulate(seed)
        if not sim or not 44 <= sim["S"] <= 110: continue
        a = analyse(sim); wd = len([r for r in a["dead"][sim["win"]] if r[1] >= 2])
        score = min(a["changes"], 9) * .45 - (a["d2"] - 2) * .8 + (1.2 if a["mid_rank"] >= 2 else 0) + min(wd, 3) * .3 - abs(sim["S"] - 75) / 40
        if 2 <= a["d2"] <= 4 and wd >= 1 and (best is None or score > best[0]): best = (score, seed, sim, a)
    assert best, "no good seed"
    s, sd, sim, a = best
    log(f"[maze_rush] seed {sd}: winner agent {sim['win']} in {sim['S']} steps, lead changes {a['changes']}, runner-up {a['d2']} away, mid rank {a['mid_rank']}")
    return sd, sim, a

_ec = {}
def flag_ball(flag, r, ring=(255, 255, 255), rw=3):
    key = (flag, r, ring, rw)
    if key in _ec: return _ec[key]
    f = ImageFont.truetype(EMOJI, 109); im = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((90, 90), flag, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox()); h = min(im.size); cx, cy = im.size[0] // 2, im.size[1] // 2
    R2 = r + rw + 1
    im = im.crop((cx - h // 2 + 6, cy - h // 2 + 6, cx + h // 2 - 6, cy + h // 2 - 6)).resize((2 * r, 2 * r), Image.LANCZOS)
    a = np.zeros((2 * R2, 2 * R2, 4), np.uint8); a[R2 - r:R2 + r, R2 - r:R2 + r] = np.array(im)
    m = np.zeros((2 * R2, 2 * R2), np.uint8); cv2.circle(m, (R2, R2), r - 1, 255, -1, cv2.LINE_AA)
    a[..., 3] = (a[..., 3].astype(np.uint16) * m // 255).astype(np.uint8)
    cv2.circle(a, (R2, R2), r + rw // 2, (*ring, 255), rw + 1, cv2.LINE_AA)
    hl = np.zeros((2 * R2, 2 * R2), np.float32); cv2.ellipse(hl, (int(R2 - r * .3), int(R2 - r * .45)), (int(r * .42), int(r * .25)), -30, 0, 360, 1, -1)
    hl = cv2.GaussianBlur(hl, (0, 0), r * .12) * .35
    a[..., :3] = np.clip(a[..., :3] + hl[..., None] * 255 * (a[..., 3:4] > 0), 0, 255).astype(np.uint8)
    _ec[key] = a; return a

def fit(txt, size, maxw, color, kind="black", stroke=5, sc=(0, 0, 0), spacing=0):
    while True:
        s = E.text_sprite(txt, size, color, kind, stroke=stroke, stroke_color=sc, spacing=spacing)
        if s.shape[1] <= maxw or size <= 14: return s
        size -= 2

def make_bg():
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    bg = np.array((5, 18, 34), np.float32) * (1 - y) + np.array((8, 26, 46), np.float32) * y
    bg = np.broadcast_to(bg, (H, W, 3)).copy()
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :, None]; bg *= (1 - .3 * xx ** 2)
    bg = np.clip(bg, 0, 255).astype(np.uint8)
    for x in range(0, W, 28): cv2.line(bg, (x, 0), (x, H), (12, 32, 54), 1)
    for yy in range(0, H, 28): cv2.line(bg, (0, yy), (W, yy), (12, 32, 54), 1)
    return bg

FLOOR, UNCARVED, WALL = (13, 38, 66), (6, 16, 30), (214, 234, 255)

def wall_lines(adj_open):
    """List of wall segments (layer coords) for every internal wall that is NOT open in adj_open + outer border."""
    L = []
    for x in range(GN):
        for y in range(GN):
            if x < GN - 1 and (x + 1, y) not in adj_open[(x, y)]:
                X = PAD + (x + 1) * CS; L.append(((X, PAD + y * CS), (X, PAD + (y + 1) * CS)))
            if y < GN - 1 and (x, y + 1) not in adj_open[(x, y)]:
                Y = PAD + (y + 1) * CS; L.append(((PAD + x * CS, Y), (PAD + (x + 1) * CS, Y)))
    return L

def draw_walls(img, lines, color=WALL, th=6):
    for a, b in lines: cv2.line(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), color, th, cv2.LINE_AA)
    e = GN * CS + PAD
    cv2.rectangle(img, (PAD, PAD), (e, e), color, th + 2, cv2.LINE_AA)

def build(out_mp4, seed=1, run_no=1, log=print, stills=None):
    rng = np.random.default_rng(seed * 11 + 5); sel = rng.choice(len(POOL), N, replace=False)
    names = [POOL[k][0] for k in sel]; flags = [POOL[k][1] for k in sel]
    seed, sim, an = pick(seed, log=log)
    adj, order_c, extra, dist, cells, edges, win, S = (sim[k] for k in ("adj", "order", "extra", "dist", "cells", "edges", "win", "S"))
    D, lead, rank_order = an["D"], an["lead"], an["order"]
    d0 = D[:, 0].astype(float)
    # ---- step timing: synchronous steps that accelerate (0.8 -> 1.25 x), scaled so the race lasts ~RACE_TARGET s
    race_len = float(np.clip(S / 6.0, 9.5, 14.5))
    rel = 1.0 / (0.8 + 0.45 * np.arange(S) / max(1, S - 1)); v0 = rel.sum() / race_len
    tau = T_GO + np.concatenate([[0], np.cumsum(rel / v0)])                  # tau[s] = sim time of step boundary s
    t_fin = float(tau[S]); s0 = float(tau[max(0, S - 3)]); s1 = t_fin; SL = .3
    v1 = s0 + (s1 - s0) / SL
    def sim_t(v): return v if v < s0 else s0 + (v - s0) * SL if v < v1 else s1
    def vid_t(t): return t if t < s0 else s0 + (t - s0) / SL if t < s1 else v1 + (t - s1)
    FIN, CARD, LOOP = 1.9, 4.0, .35
    v_card = v1 + FIN; total = v_card + CARD; n = int(round(total * FPS))
    def sigma(t):
        if t <= T_GO: return 0.0
        if t >= t_fin: return float(S)
        s = int(np.searchsorted(tau, t, "right") - 1); return s + (t - tau[s]) / (tau[s + 1] - tau[s])
    log(f"[maze_rush] video {total:.1f}s, race {t_fin - T_GO:.1f}s sim, winner {names[win]}")
    # ---- precomputed layers
    bg = make_bg()
    carve_t = {CORE: 0.0}; wall_t = {}
    for j, (a, b) in enumerate(order_c):
        tt = .08 + (T_GEN - .25) * (j / len(order_c)) ** .85; carve_t[b] = tt; wall_t[frozenset((a, b))] = tt
    for j, (a, b) in enumerate(extra): wall_t[frozenset((a, b))] = T_GEN - .2 + .2 * j / len(extra)
    all_walls = []
    for x in range(GN):
        for y in range(GN):
            for nb in ((x + 1, y), (x, y + 1)):
                if nb[0] < GN and nb[1] < GN:
                    seg = (((PAD + (x + 1) * CS, PAD + y * CS), (PAD + (x + 1) * CS, PAD + (y + 1) * CS)) if nb[0] > x else
                           ((PAD + x * CS, PAD + (y + 1) * CS), (PAD + (x + 1) * CS, PAD + (y + 1) * CS)))
                    all_walls.append((wall_t.get(frozenset(((x, y), nb)), 1e9), seg))
    maze = np.zeros((RS, RS, 3), np.uint8); maze[:] = FLOOR
    wl = wall_lines(adj); glow = np.zeros((RS, RS, 3), np.uint8); draw_walls(glow, wl, (90, 170, 255), 10)
    g = cv2.GaussianBlur(glow, (0, 0), 6); cv2.addWeighted(maze, 1, g, .55, 0, maze); draw_walls(maze, wl)
    balls = [flag_ball(f, 21, COLS[k], 4) for k, f in enumerate(flags)]
    minis = [flag_ball(f, 24, COLS[k], 3) for k, f in enumerate(flags)]
    names_spr = [fit(nm, 23, 112, (225, 232, 245), "bold", 3) for nm in names]
    tag = E.text_sprite(f"MAZE RUSH  ·  RUN #{run_no}", 30, (140, 255, 210), "black", spacing=5)
    hook1 = E.text_sprite("8 FLAGS · 1 MAZE", 70, (255, 255, 255), "black", stroke=6, stroke_color=(0, 0, 0))
    hook2 = E.text_sprite("FIRST TO THE CORE WINS", 52, GOLD, "black", stroke=6, stroke_color=(0, 0, 0))
    colx = [540 + (k - 3.5) * 118 for k in range(N)]
    # pops: dead ends + so close (precomputed in step space)
    pops = []; last_pop = -9.0; last_agent = {}
    for k in range(N):
        for (st, ln) in an["dead"][k]:
            if ln >= 3 and st < S - 1:
                pops.append(["DEAD END", k, st, cells[k][st], COLS[k]])
        Dk = D[k]; shown = False
        for s in range(1, S):
            if not shown and Dk[s - 1] <= 3 and Dk[s] > Dk[s - 1] and Dk[min(S, s + 3)] >= Dk[s - 1] + 3:
                pops.append(["SO CLOSE!", k, s, cells[k][s - 1], (255, 120, 120)]); shown = True
    pops.sort(key=lambda p: p[2]); keep = []
    for p in pops:
        tv = vid_t(float(tau[p[2]]))
        if p[0] == "DEAD END" and (tv - last_pop < .55 or tv - last_agent.get(p[1], -9) < 2.5): continue
        p.append(tv); keep.append(p); last_pop = tv; last_agent[p[1]] = tv
    pops = keep
    win_path = sim["path"]; wpts = [cxy(c, win) for c in win_path]
    rng_p = np.random.default_rng(seed + 77); sparks = [(rng_p.uniform(0, 2 * np.pi), rng_p.uniform(180, 520), rng_p.uniform(3, 7), (GOLD if j % 2 else COLS[win])) for j in range(46)]
    dead_ends_w = len(an["dead"][win]); steps_w = S

    def gen_layer(v):
        m = np.zeros((RS, RS, 3), np.uint8); m[:] = UNCARVED
        for c, tt in carve_t.items():
            if tt <= v:
                x0, y0 = PAD + c[0] * CS, PAD + c[1] * CS; age = v - tt
                col = FLOOR if age > .25 else tuple(int(E.lerp(a_, b_, age / .25)) for a_, b_ in zip((60, 200, 255), FLOOR))
                cv2.rectangle(m, (x0, y0), (x0 + CS, y0 + CS), col, -1)
        lines = [seg for (tt, seg) in all_walls if tt > v]
        wc = WALL if v < T_GEN else WALL
        draw_walls(m, lines, wc)
        if v >= T_GEN - .2:                                        # cross-fade into the cached (glowing) maze
            a_ = E.smooth((v - (T_GEN - .2)) / .45); m = cv2.addWeighted(m, 1 - a_, maze, a_, 0)
        return m

    def draw(i, final=True):
        v = i / FPS; t = sim_t(v); sg = sigma(t); s_i = min(S - 1, int(sg)); u = sg - s_i if sg < S else 1.0
        if sg >= S: s_i, u = S - 1, 1.0
        f = bg.copy()
        m = gen_layer(v) if v < T_GEN + .3 else maze.copy()
        fin_age = v - v1                                            # >0 after the winner reached the core
        # trails
        dim_k = .35 if fin_age > .2 else 1.0
        gl = np.zeros((RS // 2, RS // 2, 3), np.uint8)
        for k in range(N):
            col = COLS[k]; dcol = E.mulc(col, .38)
            for (a, b, sf, sb) in edges[k]:
                if sf >= sg: break
                pa, pb = cxy(a, k), cxy(b, k)
                if sb is not None and sg > sb:
                    cv2.line(m, (int(pa[0]), int(pa[1])), (int(pb[0]), int(pb[1])), dcol, 3, cv2.LINE_AA)
                    q = min(1.0, sg - sb)
                    if q < 1: e_ = (E.lerp(pb[0], pa[0], q), E.lerp(pb[1], pa[1], q))
                    else: continue
                else:
                    q = min(1.0, sg - sf); e_ = (E.lerp(pa[0], pb[0], q), E.lerp(pa[1], pb[1], q))
                c_ = E.mulc(col, dim_k) if k != win or fin_age <= .2 else col
                cv2.line(m, (int(pa[0]), int(pa[1])), (int(e_[0]), int(e_[1])), c_, 6, cv2.LINE_AA)
                cv2.line(gl, (int(pa[0] / 2), int(pa[1] / 2)), (int(e_[0] / 2), int(e_[1] / 2)), c_, 5, cv2.LINE_AA)
        # gold route trace after the finish
        if fin_age > .35:
            q = E.smooth((fin_age - .35) / 1.0) * (len(wpts) - 1); kk = int(q)
            pts = wpts[:kk + 1] + ([(E.lerp(wpts[kk][0], wpts[kk + 1][0], q - kk), E.lerp(wpts[kk][1], wpts[kk + 1][1], q - kk))] if kk + 1 < len(wpts) else [])
            pts = np.array(pts, np.int32)
            cv2.polylines(gl, [pts // 2], False, GOLD, 9, cv2.LINE_AA); cv2.polylines(m, [pts], False, GOLD, 11, cv2.LINE_AA)
            cv2.polylines(m, [pts], False, (255, 248, 220), 4, cv2.LINE_AA)
        gg = cv2.resize(cv2.GaussianBlur(gl, (0, 0), 5), (RS, RS)); cv2.addWeighted(m, 1, gg, 1.1, 0, m)
        # core gem
        cc = cxy(CORE); pulse = .5 + .5 * math.sin(v * 5.0); rr = 17 + 3 * pulse
        cgl = np.zeros((RS // 4, RS // 4, 3), np.uint8); cv2.circle(cgl, (int(cc[0] / 4), int(cc[1] / 4)), int(9 + 4 * pulse), GOLD, -1, cv2.LINE_AA)
        m = cv2.add(m, cv2.resize(cv2.GaussianBlur(cgl, (0, 0), 4), (RS, RS)))
        ang = v * 1.6; pts = np.array([(cc[0] + rr * math.cos(ang + j * math.pi / 2), cc[1] + rr * math.sin(ang + j * math.pi / 2)) for j in range(4)], np.int32)
        cv2.fillPoly(m, [pts], GOLD, cv2.LINE_AA); cv2.polylines(m, [pts], True, (255, 250, 225), 2, cv2.LINE_AA)
        # balls
        P = []
        for k in range(N):
            a = cells[k][s_i]; b = cells[k][s_i + 1]; pa, pb = cxy(a, k), cxy(b, k)
            P.append((E.lerp(pa[0], pb[0], u), E.lerp(pa[1], pb[1], u)))
        Dn = D[:, s_i] * (1 - u) + D[:, s_i + 1] * u
        ld = lead[min(S, int(round(sg)))] if v >= T_GO else None
        for k in sorted(range(N), key=lambda k: (k == win, k == ld)):
            x, y = P[k]
            if k == ld and v >= T_GO and fin_age < 0:
                cv2.circle(m, (int(x), int(y)), int(29 + 3 * math.sin(v * 9)), (255, 255, 255), 2, cv2.LINE_AA)
            sc = 1.0 if v > .0 else 1.0
            if fin_age > 0 and k == win: sc = 1 + .5 * E.smooth(fin_age / .3) - .2 * E.smooth((fin_age - .3) / .4)
            E.blit(m, balls[k], x, y, scale=sc, alpha=1.0 if (fin_age < .2 or k == win) else .55)
        # pops
        for (txt, k, st, c, col, tv) in pops:
            age = v - tv
            if 0 <= age < 1.0 and fin_age < 0:
                p = cxy(c, k); y = max(44, p[1] - 44 - 26 * age)
                spr = E.text_sprite(txt, 32 if txt == "DEAD END" else 36, col, "black", stroke=5, stroke_color=(0, 0, 0)); al = 1 - E.smooth((age - .7) / .3)
                sc_ = max(.05, E.out_back(age / .18)); hw = spr.shape[1] * sc_ / 2 + 14; x = min(RS - hw - 6, max(hw + 6, p[0]))
                E.pill(m, x - hw, y - 26 * sc_, x + hw, y + 26 * sc_, (0, 0, 0), .55 * al)
                E.blit(m, spr, x, y, alpha=al, scale=sc_)
        # finish burst
        if 0 <= fin_age < 1.3:
            for j in range(3):
                q = (fin_age - j * .12) / .9
                if 0 < q < 1: cv2.circle(m, (int(cc[0]), int(cc[1])), int(20 + 520 * E.smooth(q)), GOLD if j != 1 else COLS[win], max(1, int(10 * (1 - q))), cv2.LINE_AA)
            for (an_, sp, sz, col) in sparks:
                q = fin_age / 1.1
                if q < 1:
                    d_ = sp * fin_age * (1 - .45 * q); cv2.circle(m, (int(cc[0] + d_ * math.cos(an_)), int(cc[1] + d_ * math.sin(an_))), max(1, int(sz * (1 - q))), col, -1, cv2.LINE_AA)
            if fin_age < .14: m = cv2.addWeighted(m, 1, np.full_like(m, 255), .35 * (1 - fin_age / .14), 0)
        # zoom on the core for the final steps
        z = 1 + .42 * E.smooth((v - (vid_t(s0) - .3)) / .5) - .42 * E.smooth((v - (v1 + .35)) / .6)
        if z > 1.001:
            half = RS / 2 / z; cx_, cy_ = cc
            cx_ = min(RS - half, max(half, cx_)); cy_ = min(RS - half, max(half, cy_))
            M = np.float32([[z, 0, RS / 2 - z * cx_], [0, z, RS / 2 - z * cy_]]); m = cv2.warpAffine(m, M, (RS, RS), flags=cv2.INTER_LINEAR)
        f[RY0:RY0 + RS, RX0:RX0 + RS] = m
        # ---- top HUD
        if v < T_GO + .25:
            a_ = 1 - E.smooth((v - (T_GO - .15)) / .3)
            E.blit(f, hook1, W / 2, 330, alpha=a_); E.blit(f, hook2, W / 2, 420, alpha=a_)
        if v > T_GO - .15 and v < v1:
            a_ = E.smooth((v - (T_GO - .15)) / .35) * (1 - E.smooth((v - (v1 - .4)) / .4))
            hud = f[240:540].copy()
            E.blit(hud, tag, W / 2, 270 - 240)
            for k in range(N):
                x = colx[k]; prog = float(np.clip(1 - Dn[k] / max(1, d0[k]), 0, 1)) if v >= T_GO else 0.0
                E.pill(hud, x - 17, 316 - 240, x + 17, 436 - 240, (0, 0, 0), .6)
                hgt = int(24 + 88 * prog)
                E.pill(hud, x - 12, 432 - 240 - hgt, x + 12, 432 - 240, COLS[k], .95)
                if k == ld:
                    tri = np.array([[x - 11, 300 - 240], [x + 11, 300 - 240], [x, 314 - 240]], np.int32); cv2.fillPoly(hud, [tri], (255, 255, 255), cv2.LINE_AA)
                E.blit(hud, minis[k], x, 470 - 240, scale=1.12 if k == ld else 1.0)
                E.blit(hud, names_spr[k], x, 514 - 240)
            f[240:540] = cv2.addWeighted(f[240:540], 1 - a_, hud, a_, 0)
        if fin_age >= 0 and v < v_card + .3:
            a_ = E.smooth(fin_age / .25) * (1 - E.smooth((v - v_card) / .3))
            E.blit(f, E.text_sprite("CORE REACHED!", 70, GOLD, "black", stroke=6, stroke_color=(0, 0, 0)), W / 2, 335, alpha=a_, scale=max(.01, E.out_back(fin_age / .35)))
            E.blit(f, fit(f"{names[win]} FOUND THE WAY IN", 46, 940, (255, 255, 255), "black", 5), W / 2, 425, alpha=a_)
        # ---- bottom line
        txt, col = None, (255, 255, 255)
        if v < T_GO: txt, col = ("PICK YOUR FLAG BEFORE THE MAZE OPENS", (255, 230, 140)) if v > .5 else (None, None)
        elif v < T_GO + .7: txt = None
        elif fin_age < 0:
            k = ld; dd = int(round(Dn[k]))
            if v >= vid_t(s0) - .3: txt, col = ("FINAL STEPS...", (255, 120, 120))
            elif dd <= 4: txt, col = (f"{names[k]} IS {dd} STEP{'S' if dd != 1 else ''} AWAY!", (255, 150, 120))
            else: txt, col = (f"CLOSEST: {names[k]} · {dd} STEPS TO THE CORE", (255, 255, 255))
        if txt:
            spr = fit(txt, 34, 900, col, "bold", 4)
            E.pill(f, W / 2 - spr.shape[1] / 2 - 34, 1556, W / 2 + spr.shape[1] / 2 + 34, 1620, (0, 0, 0), .6); E.blit(f, spr, W / 2, 1588)
        if T_GO <= v < T_GO + .7:
            q = (v - T_GO) / .7
            E.blit(f, E.text_sprite("GO!", 160, (140, 255, 210), "black", stroke=9, stroke_color=(0, 0, 0)), W / 2, 1056, alpha=1 - E.smooth((q - .5) / .5), scale=E.out_back(q / .3))
        # ---- result card
        if v >= v_card:
            uu = v - v_card; a_ = E.smooth(uu / .35)
            f[:] = cv2.convertScaleAbs(f, alpha=1 - .8 * a_)
            E.blit(f, E.text_sprite(f"MAZE RUSH · RUN #{run_no} RESULT", 28, (140, 255, 210), "bold", spacing=4), W / 2, 470, alpha=a_)
            E.blit(f, flag_ball(flags[win], 96, GOLD, 8), W / 2, 650, scale=E.out_back((uu - .1) / .4), alpha=a_)
            E.blit(f, fit(names[win], 90, 920, GOLD, "black", 6), W / 2, 820, alpha=E.smooth((uu - .25) / .3))
            E.blit(f, E.text_sprite("REACHED THE CORE FIRST", 42, (255, 255, 255), "black", stroke=4, stroke_color=(0, 0, 0)), W / 2, 905, alpha=E.smooth((uu - .35) / .3))
            E.blit(f, E.text_sprite(f"{steps_w} STEPS  ·  {dead_ends_w} DEAD END{'S' if dead_ends_w != 1 else ''} ON THE WAY", 31, (190, 225, 255), "bold"), W / 2, 965, alpha=E.smooth((uu - .5) / .3))
            for j in range(3):
                k = rank_order[j + 1]; y = 1070 + j * 84; g_ = E.smooth((uu - .7 - .15 * j) / .3)
                if g_ <= 0: continue
                E.pill(f, 150, y - 34, W - 150, y + 34, (10, 30, 56), .85 * g_)
                E.blit(f, E.text_sprite(["2ND", "3RD", "4TH"][j], 32, [(215, 222, 235), (230, 155, 85), (170, 180, 200)][j], "black"), 225, y, alpha=g_)
                E.blit(f, minis[k], 310, y, alpha=g_)
                E.blit(f, fit(names[k], 34, 330, (255, 255, 255), "bold", 0), 355, y, alpha=g_, anchor="l")
                dk = int(D[k, S]); E.blit(f, E.text_sprite(f"{dk} STEP{'S' if dk != 1 else ''} SHORT", 28, COLS[k], "bold"), W - 185, y, alpha=g_, anchor="r")
            E.blit(f, fit("WHICH START WOULD YOU PICK NEXT RUN?", 40, 920, (190, 230, 255), "bold", 4), W / 2, 1365, alpha=E.smooth((uu - 1.3) / .3))
            E.blit(f, E.text_sprite("DROP YOUR PICK BELOW", 34, (255, 230, 140), "bold", stroke=4, stroke_color=(0, 0, 0)), W / 2, 1430, alpha=E.smooth((uu - 1.6) / .3))
        if final and v > total - LOOP:
            bb = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - bb, draw(0, False), bb, 0)
        return f

    # ---- audio: lo-fi chill bed (swung beat, soft e-piano, vinyl) + maze sounds
    mix = E.Mix(total, mood="lofi", bpm=86, root=50, scale="dorian", timbre="epiano"); hz = lambda m_: float(E.midi_hz(m_))
    vs0 = vid_t(s0)
    mix.bed(0.0, total, gain=.34, seed=seed, intensity=lambda tt: .3 + .65 * E.smooth((tt - T_GO) / max(1, vs0 - T_GO)),
            drums_off=[(vs0 - .05, v1 + .1)])
    for j, (a, b) in enumerate(order_c):                                     # carving shimmer
        if j % 16 == 0: mix.add(carve_t[b], E.pluck(hz(mix.scale_note(j // 16, 2)), .5), .13, ((b[0] - 8) / 8) * .6)
    mix.add(T_GEN - .2, E.chord([74, 78, 81, 86], 1.6, E.bell), .22)
    mix.add(T_GO, E.chord(mix.chord_notes(0, 4, 2), 1.6, E.epiano), .45); mix.add(T_GO - .25, E.whoosh(.4), .4); mix.add(T_GO, E.thump(.5, 130, 40), .6)
    for s in range(S):                                                       # synchronous step ticks
        tv = vid_t(float(tau[s]))
        if tv < vs0: mix.add(tv, E.tick(2600 if s % 2 else 2300, .03), .035 + .04 * s / S, .3 if s % 2 else -.3)
    for s in range(1, S + 1):                                                # leader changes
        if lead[s] != lead[s - 1]: mix.add(vid_t(float(tau[s])), E.epiano(hz(mix.scale_note(lead[s] + 3, 2)), .8), .2)
    for (txt, k, st, c, col, tv) in pops:
        pan = ((c[0] - 8) / 8) * .6
        if txt == "DEAD END": mix.add(tv, E.thump(.14, 320, 120), .22, pan); mix.add(tv, E.pluck(hz(mix.scale_note(0, 0)), .4), .2, pan)
        else: mix.add(tv, E.slide_down(.6, 760, 320), .22, pan)
    mix.add(max(0, vs0 - 1.4), E.riser(1.4 + (v1 - vs0) * .7, 200, 2200), .26)
    for j in range(3): mix.add(vs0 + j * (v1 - vs0) / 3, E.epiano(hz(mix.scale_note(4 + 2 * j, 2)), 1.0), .25)
    mix.add(v1, E.thump(.9, 110, 30), .85); mix.add(v1, E.chord(mix.chord_notes(0, 4, 2) + [mix.scale_note(7, 2)], 2.2, E.bell), .45)
    for j in range(6): mix.add(v1 + .35 + j * .1, E.epiano(hz(mix.scale_note(j * 2, 2)), 1.2), .28)
    mix.add(v_card + .1, E.chord(mix.chord_notes(3, 4, 1), 2.6, E.epiano), .4)
    for j, m_ in enumerate(mix.chord_notes(0, 4, 2)): mix.add(v_card + .9 + j * .13, E.pluck(hz(m_), 1.0), .25)
    wav = out_mp4[:-4] + ".wav"; mix.write(wav, peak=.8)
    if stills:
        for t_ in stills: E.save_png(out_mp4[:-4] + f"_still_{t_:05.2f}.png", draw(min(n - 1, int(t_ * FPS)), False))
        return dict(total=total, v1=v1, v_card=v_card, s0=vs0, winner=names[win])
    E.render(out_mp4, wav, n, draw); os.remove(wav)
    title = f"8 Flags Race Through a Maze to the Core | Maze Rush #{run_no}"
    desc = (f"A maze carves itself from a glowing core, then 8 flags search for the way in at the same speed. "
            f"Bright trail = current route, dim trail = dead end. Today {names[win]} gets there first.\n\nWhich start would you pick? 👇\n\n"
            "#shorts #maze #flags #satisfying #simulation")
    return dict(duration=total, title=title, description=desc, tags=["maze", "maze solver", "flags", "countries", "satisfying", "simulation"],
                winner=names[win], ranking=[names[k] for k in rank_order], countries=names, seed=seed,
                steps=steps_w, dead_ends=dead_ends_w, runner_up_short=int(D[rank_order[1], S]), thumb_ms=2400)

if __name__ == "__main__":                     # python3 -I lab/styles/maze_rush.py <out.mp4> <seed> [episode]
    import json
    out = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1; ep = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    res = build(out, seed, run_no=ep, log=lambda *a: print(*a, file=sys.stderr)); print("RESULT=" + json.dumps(res, default=float))
