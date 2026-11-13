"""LAB STYLE sumo_island: 8 flag balls on a top-down hex-tile island floating over lava. Every ball keeps dashing at
its rivals (billiard knockbacks) while the island crumbles from the edge inward: tiles glow red, then drop into the lava.
Centre over a hole = OUT. Static top-down camera, roster scoreboard with X-outs + places, ALIVE/ISLAND % meter,
slow-mo final clash, winner card with knockout order. Pure physics + chance: no data."""
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import engine as E
from engine import W, H, FPS

EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
POOL = [("PORTUGAL", "🇵🇹"), ("NIGERIA", "🇳🇬"), ("GREECE", "🇬🇷"), ("NORWAY", "🇳🇴"), ("JAMAICA", "🇯🇲"),
        ("COLOMBIA", "🇨🇴"), ("UKRAINE", "🇺🇦"), ("KENYA", "🇰🇪"), ("POLAND", "🇵🇱"),
        ("FINLAND", "🇫🇮"), ("THAILAND", "🇹🇭"), ("CROATIA", "🇭🇷"), ("BRAZIL", "🇧🇷"), ("GHANA", "🇬🇭")]
N, R = 8, 41                       # balls, ball radius
S = 46                             # hex size (centre to corner), pointy-top
SQ3 = math.sqrt(3)
CX, CY, ISL_R = 540, 1020, 430     # island centre / radius
DEPTH = 20                         # pseudo-3D slab thickness
T_FIGHT = 1.8                      # intro (tiles rise, flags land), then FIGHT
BEAT = 0.5                         # 120 bpm: crumble waves land on the beat
T_C0, T_C1, CRACK = 3.5, 20.0, 1.0
DAMP, REST = 2.4, 0.92
HX = np.array([[math.cos(math.radians(60 * k - 30)), math.sin(math.radians(60 * k - 30))] for k in range(6)]) * (S - 2.0)


def hex_round(q, r):
    x, z = q, r; y = -x - z; rx, ry, rz = round(x), round(y), round(z)
    dx, dy, dz = abs(rx - x), abs(ry - y), abs(rz - z)
    if dx > dy and dx > dz: rx = -ry - rz
    elif dy > dz: ry = -rx - rz
    else: rz = -rx - ry
    return int(rx), int(rz)


def axial(x, y):
    x -= CX; y -= CY
    return hex_round((SQ3 / 3 * x - y / 3) / S, (2 / 3 * y) / S)


def island(seed):
    rng = np.random.default_rng(seed + 517); qs, xs = [], []
    for r in range(-10, 11):
        for q in range(-10, 11):
            x = S * SQ3 * (q + r / 2); y = S * 1.5 * r
            if math.hypot(x, y) <= ISL_R - S * .25: qs.append((q, r)); xs.append((CX + x, CY + y))
    Q = np.array(qs); X = np.array(xs, float); n = len(Q)
    d = np.hypot(X[:, 0] - CX, X[:, 1] - CY); th = np.arctan2(X[:, 1] - CY, X[:, 0] - CX)
    core = (np.abs(Q[:, 0]) + np.abs(Q[:, 1]) + np.abs(Q[:, 0] + Q[:, 1])) // 2 <= 1          # 7 tiles never fall
    key = d * (1 + .17 * np.sin(3 * th + rng.uniform(0, 6.28))) + rng.uniform(0, 1.6 * S, n); key[core] = -1e9
    order = np.argsort(-key); nf = int((~core).sum()); crack = np.full(n, np.inf)
    for k, idx in enumerate(order[:nf]):
        tc = T_C0 + (k / max(1, nf - 1)) ** 1.1 * (T_C1 - T_C0)
        crack[idx] = T_C0 + round((tc - T_C0) / BEAT) * BEAT
    lines = []                                                                     # crack lines (visual only)
    for k in range(n):
        a = rng.uniform(0, 6.28); pts = [(0.0, 0.0)]
        for j in range(3): a += rng.uniform(-.9, .9); rr = (j + 1) * S * .28; pts.append((rr * math.cos(a), rr * math.sin(a)))
        b = a + rng.uniform(2, 3.5); pts2 = [(0.0, 0.0), (S * .3 * math.cos(b), S * .3 * math.sin(b)), (S * .6 * math.cos(b + .4), S * .6 * math.sin(b + .4))]
        lines.append((np.array(pts), np.array(pts2)))
    return dict(Q=Q, X=X, n=n, core=core, crack=crack, drop=crack + CRACK, look={tuple(a): k for k, a in enumerate(qs)},
                appear=d / ISL_R * .55, lines=lines, shade=(Q[:, 0] - Q[:, 1]) % 3)


def simulate(seed, max_t=40.0, dt=1 / 240):
    rng = np.random.default_rng(seed); isl = island(seed); look, crack, drop = isl["look"], isl["crack"], isl["drop"]
    def tile(x, y): return look.get(axial(x, y))
    def ground(x, y, t):
        k = look.get(axial(x, y)); return k is not None and drop[k] > t
    a0 = rng.uniform(0, 6.28); ang = a0 + np.arange(N) * 2 * np.pi / N
    P = np.stack([CX + 250 * np.cos(ang), CY + 250 * np.sin(ang)], 1); V = np.zeros((N, 2))
    out = np.full(N, -1.0); nxt = T_FIGHT + rng.uniform(0, .45, N); by = [-1] * N; last_hit = np.full((N, N), -9.0)
    ev, frames = [], []; step = int(round(1 / (FPS * dt))); t_win = None
    teeter = np.zeros(N); was = np.zeros(N, bool); dirs = [(math.cos(a), math.sin(a)) for a in np.arange(8) * math.pi / 4]
    for s in range(int(max_t / dt)):
        t = s * dt
        if s % step == 0:
            frames.append((t, P.copy(), out.copy()))
            for i in np.nonzero(out < 0)[0]:                                       # close calls (edge teeter)
                tt = any(not ground(P[i, 0] + .8 * R * c, P[i, 1] + .8 * R * sn, t) for c, sn in dirs)
                if tt and not was[i]: teeter[i] += 1
                was[i] = tt
        if t < T_FIGHT: continue
        alive = np.nonzero(out < 0)[0]
        for i in alive:                                                            # AI: dash at a rival, or flee danger
            if t < nxt[i] or len(alive) < 2: continue
            nxt[i] = t + rng.uniform(.65, 1.35); x, y = P[i]; k = tile(x, y)
            danger = k is None or crack[k] <= t + .2
            voids = sum(not ground(x + 1.7 * R * c, y + 1.7 * R * sn, t + .3) for c, sn in dirs)
            if (danger or voids >= 3) and rng.random() < .72:
                dv = np.array([CX, CY]) - P[i] + rng.normal(0, 25, 2); sp = rng.uniform(380, 560); kind = "flee"
            else:
                oth = alive[alive != i]; dd = P[oth] - P[i]; dist = np.hypot(dd[:, 0], dd[:, 1]) + 1
                w = 1 / dist ** 2; j = int(rng.choice(oth, p=w / w.sum()))
                dv = P[j] + V[j] * .12 - P[i]; sp = rng.uniform(600, 880); kind = "dash"
                u = dv / (math.hypot(*dv) + 1e-6); end = P[i] + u * sp / DAMP
                if not ground(end[0], end[1], t + .6) and rng.random() < .55: sp *= .5
            u = dv / (math.hypot(*dv) + 1e-6); V[i] = V[i] * .25 + u * sp; ev.append((kind, t, int(i), float(x), float(sp)))
        V *= math.exp(-DAMP * dt); V[out >= 0] *= math.exp(-3 * dt); P += V * dt
        for a in range(len(alive)):                                                # ball-ball (equal mass)
            for b in range(a + 1, len(alive)):
                i, j = alive[a], alive[b]; dx = P[j, 0] - P[i, 0]; dy = P[j, 1] - P[i, 1]; d2 = dx * dx + dy * dy
                if 0 < d2 < 4 * R * R:
                    d = math.sqrt(d2); nx, ny = dx / d, dy / d; o = (2 * R - d) / 2
                    P[i, 0] -= nx * o; P[i, 1] -= ny * o; P[j, 0] += nx * o; P[j, 1] += ny * o
                    rel = (V[j, 0] - V[i, 0]) * nx + (V[j, 1] - V[i, 1]) * ny
                    if rel < 0:
                        im = -(1 + REST) * rel / 2
                        V[i, 0] -= im * nx; V[i, 1] -= im * ny; V[j, 0] += im * nx; V[j, 1] += im * ny
                        if -rel > 200:
                            ev.append(("hit", t, int(i), int(j), (P[i, 0] + P[j, 0]) / 2, (P[i, 1] + P[j, 1]) / 2, -rel)); last_hit[i, j] = last_hit[j, i] = t
        for i in alive:
            if not ground(P[i, 0], P[i, 1], t):
                out[i] = t; place = int((out < 0).sum()) + 1; hb = int(np.argmax(last_hit[i])); by[i] = hb if t - last_hit[i, hb] < 1.2 else -1
                ev.append(("out", t, int(i), float(P[i, 0]), float(P[i, 1]), place, by[i]))
        na = int((out < 0).sum())
        if na == 0: return None
        if na == 1 and t_win is None: t_win = t
        if t_win is not None and t > t_win + 1.3:
            frames.append((t, P.copy(), out.copy()))
            return dict(frames=frames, ev=ev, out=out, by=by, T=t, isl=isl, teeter=teeter)
    return None


def pick(seed0, tries=60, log=print):
    best = None
    for seed in range(seed0, seed0 + tries):
        sim = simulate(seed)
        if not sim: continue
        o = sim["out"]; outs = np.sort(o[o >= 0]); win = int(np.nonzero(o < 0)[0][0])
        first, last = outs[0], outs[-1]; duel = outs[-1] - outs[-2]; gap = np.diff(np.r_[T_FIGHT, outs]).max()
        hits = sum(1 for e in sim["ev"] if e[0] == "hit"); pushed = sum(1 for b in sim["by"] if b >= 0); close = sim["teeter"][win]
        same = np.min(np.diff(outs)) if len(outs) > 1 else 9
        ok = 13 <= last <= 22 and first >= 3.6 and 1.5 <= duel <= 5.0 and gap <= 5.5 and same > .25
        bunch = int((np.diff(outs) < .9).sum())
        score = -abs(last - 17.5) / 4 - bunch * .3 + min(duel, 4.5) * .35 + min(close, 4) * .35 - gap * .2 + min(hits, 80) * .01 + pushed * .12
        log(f"  seed {seed}: last {last:.1f} first {first:.1f} duel {duel:.1f} gap {gap:.1f} bunch {bunch} hits {hits} pushed {pushed} close {close:.0f} {'OK %.2f' % score if ok else '--'}")
        if ok and (best is None or score > best[0]): best = (score, seed, sim)
    assert best, "no good seed"; log(f"[sumo_island] seed {best[1]} score {best[0]:.2f}")
    return best[1], best[2]




_ec = {}
def flag_ball(flag, r):
    if (flag, r) in _ec: return _ec[(flag, r)]
    f = ImageFont.truetype(EMOJI, 109); im = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((90, 90), flag, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox()); h = min(im.size); cx, cy = im.size[0] // 2, im.size[1] // 2
    im = im.crop((cx - h // 2 + 6, cy - h // 2 + 6, cx + h // 2 - 6, cy + h // 2 - 6)).resize((2 * r, 2 * r), Image.LANCZOS)
    a = np.array(im); m = np.zeros((2 * r, 2 * r), np.uint8); cv2.circle(m, (r, r), r - 1, 255, -1, cv2.LINE_AA)
    a[..., 3] = (a[..., 3].astype(np.uint16) * m // 255).astype(np.uint8)
    cv2.circle(a, (r, r), r - 2, (20, 20, 28, 255), 4, cv2.LINE_AA)
    hl = np.zeros((2 * r, 2 * r), np.float32); cv2.ellipse(hl, (int(r * .68), int(r * .55)), (int(r * .42), int(r * .24)), -30, 0, 360, 1, -1)
    hl = cv2.GaussianBlur(hl, (0, 0), r * .12) * .45
    a[..., :3] = np.clip(a[..., :3] + hl[..., None] * 255 * (a[..., 3:4] > 0), 0, 255).astype(np.uint8)
    _ec[(flag, r)] = a; return a


def gray(spr, k=.45):
    g = cv2.cvtColor(spr[..., :3], cv2.COLOR_RGB2GRAY).astype(np.float32) * k
    return np.dstack([np.repeat(g[..., None], 3, 2).astype(np.uint8), spr[..., 3]])


def soft_disc(r, color, a_max, blur):
    s = int(r * 2 + blur * 6); m = np.zeros((s, s), np.float32); cv2.circle(m, (s // 2, s // 2), int(r), 1, -1, cv2.LINE_AA)
    m = cv2.GaussianBlur(m, (0, 0), blur) * a_max
    out = np.zeros((s, s, 4), np.uint8); out[..., :3] = color; out[..., 3] = (m * 255).astype(np.uint8); return out


def panel(w, h, rad=34):
    a = np.zeros((h, w, 4), np.uint8); m = np.zeros((h, w), np.uint8)
    cv2.rectangle(m, (rad, 0), (w - rad, h), 255, -1); cv2.rectangle(m, (0, rad), (w, h - rad), 255, -1)
    for cx, cy in [(rad, rad), (w - rad - 1, rad), (rad, h - rad - 1), (w - rad - 1, h - rad - 1)]: cv2.circle(m, (cx, cy), rad, 255, -1, cv2.LINE_AA)
    a[..., :3] = (14, 10, 22); a[..., 3] = (m.astype(np.float32) * .86).astype(np.uint8)
    e = np.zeros((h, w), np.uint8); cv2.rectangle(e, (rad, 2), (w - rad, 6), 255, -1)                 # warm top edge
    a[e > 0, :3] = (255, 150, 70); a[e > 0, 3] = 230
    return a


PAD = 260
def lava(seed):
    rng = np.random.default_rng(seed); hh = H + PAD; acc = np.zeros((hh, W), np.float32)
    for k, (gh, amp) in enumerate([(14, 1.0), (30, .55), (64, .3)]):
        g = rng.random((gh * hh // W + 2, gh + 2)).astype(np.float32)
        acc += cv2.resize(g, (W, hh), interpolation=cv2.INTER_CUBIC) * amp
    acc = (acc - acc.min()) / (acc.max() - acc.min()); v = 1 - np.abs(2 * acc - 1); v = np.clip(v, 0, 1) ** 2.2   # ridged veins
    c0, c1, c2, c3 = [np.array(c, np.float32) for c in [(22, 4, 8), (90, 16, 8), (200, 70, 14), (245, 160, 70)]]
    img = np.where(v[..., None] < .45, c0 + (c1 - c0) * (v[..., None] / .45),
                   np.where(v[..., None] < .8, c1 + (c2 - c1) * ((v[..., None] - .45) / .35), c2 + (c3 - c2) * ((v[..., None] - .8) / .2)))
    img = cv2.GaussianBlur(img, (0, 0), 2.5); return np.clip(img * .62, 0, 255).astype(np.uint8)


def build(out_mp4, seed=1, ep=1, log=print, stills=None):
    rng = np.random.default_rng(seed * 11 + 5); sel = rng.choice(len(POOL), N, replace=False)
    names = [POOL[k][0] for k in sel]; flags = [POOL[k][1] for k in sel]
    seed, sim = pick(seed, log=log); fr = sim["frames"]; o_all = sim["out"]; isl = sim["isl"]; X = isl["X"]
    win = int(np.nonzero(o_all < 0)[0][0]); kos = sorted([k for k in range(N) if o_all[k] >= 0], key=lambda k: o_all[k])
    t_f = o_all[kos[-1]]
    lh = [e[1] for e in sim["ev"] if e[0] == "hit" and kos[-1] in (e[2], e[3]) and e[1] <= t_f]
    s0 = max(t_f - 1.1, (lh[-1] - .3) if lh else t_f - .8); s1 = t_f + .4; SM = .3; v1 = s0 + (s1 - s0) / SM
    def sim_t(v): return v if v < s0 else s0 + (v - s0) * SM if v < v1 else s1 + (v - v1)
    def vid_t(t): return t if t < s0 else s0 + (t - s0) / SM if t < s1 else v1 + (t - s1)
    v_end = vid_t(sim["T"]); CARD = 4.4; total = v_end + CARD; n = int(round(total * FPS)); LOOP = .35
    log(f"[sumo_island] video {total:.1f}s, winner {names[win]}, final KO at {t_f:.1f}s")
    t3 = o_all[kos[-2]]                                                         # moment it becomes LAST TWO
    lavaA, lavaB = lava(seed + 3), lava(seed + 4)
    balls = [flag_ball(f, R) for f in flags]; minis = [flag_ball(f, 32) for f in flags]; greys = [gray(m) for m in minis]
    shadow = soft_disc(R * .95, (0, 0, 0), .55, 5); glow = soft_disc(R * 1.2, (255, 255, 255), .35, 6)
    pan_spr = panel(W - 80, 270)
    slot_x = np.linspace(W / 2 - 3.5 * 122, W / 2 + 3.5 * 122, N); ROSTER_Y = 392
    tag = E.text_sprite(f"SUMO ISLAND  ·  ROUND #{ep}", 30, (255, 175, 90), "bold", spacing=5)
    sub = E.text_sprite("FALL IN THE LAVA = OUT", 20, (205, 200, 225), "bold", spacing=3)
    land = [.25 + .07 * k for k in range(N)]
    hits = np.array([(vid_t(e[1]), e[4], e[5], e[6]) for e in sim["ev"] if e[0] == "hit"]) if any(e[0] == "hit" for e in sim["ev"]) else np.zeros((0, 4))
    outs = [e for e in sim["ev"] if e[0] == "out"]
    SHADES = [(92, 100, 126), (82, 90, 115), (102, 110, 136)]; SIDE = (46, 38, 54); EDGE = (58, 60, 80); HOT = (255, 92, 40)
    ordy = np.argsort(X[:, 1]); ntile = isl["n"]
    def state(t):
        f = t * FPS; i0 = min(len(fr) - 2, int(f)); w = min(1.0, f - i0); A, B = fr[i0], fr[i0 + 1]
        return A[1] * (1 - w) + B[1] * w, A[2], i0
    def tiles(f, t, v):
        for k in ordy:
            dr, cr = isl["drop"][k], isl["crack"][k]
            if t >= dr + .6: continue
            cx, cy = X[k]; sc = 1.0; dy = 0.0; dx = 0.0; col = SHADES[isl["shade"][k]]; side = SIDE; cracking = 0.0
            if v < 1.0:
                a = (v - isl["appear"][k]) / .32
                if a <= 0: continue
                sc = max(.05, E.out_back(a, 1.4)); dy = (1 - E.smooth(a)) * 40
            if t >= dr:
                u = (t - dr) / .6; sc *= 1 - .45 * u; dy += 110 * u * u; col = E.mulc(col, 1 - .85 * u); side = E.mulc(SIDE, 1 - .85 * u)
            elif t >= cr:
                u = (t - cr) / CRACK; cracking = u; fl = u * (.55 + .45 * math.sin(t * 38 + k))
                col = tuple(int(c + (h - c) * (.12 + .7 * fl)) for c, h in zip(col, HOT)); dx = math.sin(t * 71 + k * 3.1) * 3.5 * u
            pts = (HX * sc + (cx + dx, cy + dy)).astype(np.int32)
            cv2.fillPoly(f, [pts + (0, DEPTH)], side, cv2.LINE_AA); cv2.fillPoly(f, [pts], col, cv2.LINE_AA)
            cv2.polylines(f, [pts], True, EDGE, 2, cv2.LINE_AA)
            if cracking > 0 and t < dr:
                l1, l2 = isl["lines"][k]; cc = (40, 12, 8) if cracking < .5 else (255, 230, 150)
                for L in (l1, l2): cv2.polylines(f, [(L * min(1, cracking * 2) * sc + (cx + dx, cy + dy)).astype(np.int32)], False, cc, 3, cv2.LINE_AA)
    def pops(f, v):
        for e in outs:
            age = v - vid_t(e[1]); k = e[2]
            if not 0 <= age < 1.4: continue
            s1_ = E.text_sprite(f"{names[k]} OUT", 50, (255, 110, 80), "black", stroke=6, stroke_color=(0, 0, 0))
            line = f"PUSHED BY {names[e[6]]}" if e[6] >= 0 else "THE FLOOR GAVE WAY"
            s2_ = E.text_sprite(line, 28, (255, 230, 170), "bold", stroke=4, stroke_color=(0, 0, 0)); hw = max(s1_.shape[1], s2_.shape[1]) * .55 + 6
            x = float(np.clip(e[3], 60 + hw, 1020 - hw)); y = float(np.clip(e[4] - 115 - 40 * age, 680, 1440)); a = 1 - E.smooth((age - 1.1) / .3)
            E.blit(f, s1_, x, y, alpha=a, scale=E.out_back(age / .25))
            E.blit(f, s2_, x, y + 50, alpha=a * E.smooth((age - .15) / .2))
    def card(f, u):
        a_ = E.smooth(u / .3); f[:] = cv2.convertScaleAbs(f, alpha=1 - .8 * a_)
        nm = names[win]
        E.blit(f, E.text_sprite(nm, 104 if len(nm) <= 7 else 86, (255, 215, 90), "black", stroke=7, stroke_color=(0, 0, 0)), W / 2, 620, alpha=a_, scale=E.out_back(u / .4))
        E.blit(f, E.text_sprite("IS THE LAST FLAG STANDING", 42, (255, 255, 255), "bold", stroke=4, stroke_color=(0, 0, 0)), W / 2, 715, alpha=E.smooth((u - .25) / .3))
        g = E.smooth((u - .3) / .4)
        if g > 0:
            for j in range(12):                                                      # rotating rays
                ang = j * math.pi / 6 + u * .6; r0, r1 = 120, 120 + 70 * g
                cv2.line(f, (int(540 + r0 * math.cos(ang)), int(950 + r0 * math.sin(ang))), (int(540 + r1 * math.cos(ang)), int(950 + r1 * math.sin(ang))), (255, 200, 80), 6, cv2.LINE_AA)
            E.blit(f, minis[win], W / 2, 950, scale=3.2 * E.out_back((u - .3) / .4))
        E.blit(f, E.text_sprite("KNOCKOUT ORDER", 24, (200, 195, 225), "bold", spacing=3), W / 2, 1165, alpha=E.smooth((u - .7) / .3))
        xs = np.linspace(W / 2 - 3 * 128, W / 2 + 3 * 128, 7)
        for j, k in enumerate(reversed(kos)):                                        # 2nd .. 8th
            a2 = E.smooth((u - .8 - .07 * j) / .25)
            E.blit(f, minis[k], xs[j], 1232, alpha=a2)
            E.blit(f, E.text_sprite(["2ND", "3RD", "4TH", "5TH", "6TH", "7TH", "8TH"][j], 22, (255, 160, 120), "bold", stroke=3, stroke_color=(0, 0, 0)), xs[j], 1288, alpha=a2)
        E.blit(f, E.text_sprite("WHO DID YOU PICK?", 50, (190, 230, 255), "black", stroke=5, stroke_color=(0, 0, 0)), W / 2, 1395, alpha=E.smooth((u - 1.4) / .3))
        E.blit(f, E.text_sprite("DROP YOUR FLAG IN THE COMMENTS", 32, (255, 230, 140), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1462, alpha=E.smooth((u - 1.7) / .3))
    pulse = {"alive": N, "isl": 100, "ta": -9.0}
    def draw(i, final=True):
        v = i / FPS; t = sim_t(min(v, v_end)); P, o, i0 = state(t)
        off = int(v * 24) % PAD; w_ = .5 + .5 * math.sin(v * 1.7)
        f = cv2.addWeighted(lavaA[off:off + H], 1 - w_, lavaB[PAD - off:PAD - off + H], w_, 0)
        tiles(f, t, v)
        for e_ in range(len(hits)):                                                 # impact sparks
            age = v - hits[e_, 0]
            if 0 <= age < .3:
                u = age / .3; x, y, sp = hits[e_, 1], hits[e_, 2], hits[e_, 3]; L = (14 + 70 * u) * min(1.4, sp / 500)
                for j in range(10):
                    ang = j * .628 + e_
                    cv2.line(f, (int(x + (L * .45) * math.cos(ang)), int(y + (L * .45) * math.sin(ang))), (int(x + L * math.cos(ang)), int(y + L * math.sin(ang))),
                             (255, 240, 170), max(1, int(5 * (1 - u))), cv2.LINE_AA)
        for k in np.argsort(P[:, 1]):
            x, y = P[k]
            if o[k] >= 0:
                u = (t - o[k]) / .8
                if u >= 1: continue
                cv2.circle(f, (int(x), int(y)), int(R * (1 + 1.8 * u)), (255, 200, 90), max(1, int(9 * (1 - u))), cv2.LINE_AA)
                E.blit(f, balls[k], x, y + 25 * u, alpha=1 - .8 * u, scale=max(.1, 1 - .85 * u)); continue
            if v < land[k]:
                a = (v - (land[k] - .45)) / .45
                if a <= 0: continue
                sc = 1 + 1.6 * (1 - a) ** 2; E.blit(f, shadow, x + 7, y + 12, alpha=a, scale=1 / sc); E.blit(f, balls[k], x, y - 160 * (1 - a) ** 2, alpha=min(1, a * 2), scale=sc); continue
            if i0 > 6:                                                               # speed trail
                sp = math.hypot(*(fr[i0][1][k] - fr[i0 - 1][1][k])) * FPS
                if sp > 330:
                    for j in range(1, 5):
                        q = fr[max(0, i0 - 2 * j)][1][k]; E.blit(f, glow, q[0], q[1], alpha=min(1, sp / 900) * (1 - j / 5), scale=1 - j * .1)
            E.blit(f, shadow, x + 7, y + 12); E.blit(f, balls[k], x, y)
        # ---- HUD
        E.blit(f, pan_spr, W / 2, 236 + 135); E.blit(f, tag, W / 2, 274); E.blit(f, sub, W / 2, 312)
        for k in range(N):
            isout = o[k] >= 0 and v >= vid_t(o[k]) - 1e-6
            if isout:
                E.blit(f, greys[k], slot_x[k], ROSTER_Y)
                d_ = 22; cx_, cy_ = int(slot_x[k]), ROSTER_Y
                cv2.line(f, (cx_ - d_, cy_ - d_), (cx_ + d_, cy_ + d_), (235, 50, 50), 7, cv2.LINE_AA); cv2.line(f, (cx_ + d_, cy_ - d_), (cx_ - d_, cy_ + d_), (235, 50, 50), 7, cv2.LINE_AA)
                pl = next(e[5] for e in outs if e[2] == k)
                E.blit(f, E.text_sprite(["", "", "2ND", "3RD", "4TH", "5TH", "6TH", "7TH", "8TH"][pl], 19, (255, 110, 90), "bold"), slot_x[k], ROSTER_Y + 50)
            else:
                age = v - max([vid_t(o_all[j]) for j in kos if vid_t(o_all[j]) <= v] or [-9])
                sc = 1.0 + (.12 * (1 - E.smooth(age / .4)) if age < .4 else 0)
                if v >= v_end and k == win: sc = 1.15 + .05 * math.sin(v * 8)
                E.blit(f, minis[k], slot_x[k], ROSTER_Y, scale=sc)
                E.blit(f, E.text_sprite(names[k], 16, (235, 235, 245), "bold"), slot_x[k], ROSTER_Y + 50)
        alive = int(sum(1 for k in range(N) if not (o[k] >= 0 and v >= vid_t(o[k]) - 1e-6)))
        isl_pct = int(round(100 * float((isl["drop"] > t).sum()) / ntile))
        if v < T_FIGHT:
            E.pill(f, 150, 885, W - 150, 1095, (0, 0, 0), .5)
            E.blit(f, E.text_sprite("LAST FLAG", 96, (255, 255, 255), "black", stroke=7, stroke_color=(0, 0, 0)), W / 2, 940)
            E.blit(f, E.text_sprite("STANDING WINS", 78, (255, 200, 80), "black", stroke=7, stroke_color=(0, 0, 0)), W / 2, 1035)
        elif v < T_FIGHT + .7:
            u = (v - T_FIGHT) / .7
            E.blit(f, E.text_sprite("FIGHT!", 170, (255, 120, 60), "black", stroke=9, stroke_color=(0, 0, 0)), W / 2, 990, alpha=1 - E.smooth((u - .5) / .5), scale=E.out_back(u / .35))
        if v < 4.8:
            txt = "8 FLAGS · 1 CRUMBLING ISLAND" if v < T_FIGHT else "PICK YOUR FLAG BEFORE IT CRUMBLES"
            spr = E.text_sprite(txt, 34, (255, 230, 140), "bold", stroke=4, stroke_color=(0, 0, 0))
            E.pill(f, W / 2 - spr.shape[1] / 2 - 34, 1550, W / 2 + spr.shape[1] / 2 + 34, 1616, (0, 0, 0), .62); E.blit(f, spr, W / 2, 1583)
        elif v < v_end:
            spr = E.text_sprite(f"ALIVE {alive}   ·   ISLAND {isl_pct}%", 36, (255, 255, 255), "bold", stroke=4, stroke_color=(0, 0, 0))
            E.pill(f, W / 2 - spr.shape[1] / 2 - 40, 1550, W / 2 + spr.shape[1] / 2 + 40, 1616, (0, 0, 0), .62)
            last_ko = max([vid_t(o_all[j]) for j in kos if vid_t(o_all[j]) <= v] or [-9]); pa = v - last_ko
            E.blit(f, spr, W / 2, 1583, scale=1 + (.15 * (1 - E.smooth(pa / .45)) if pa < .45 else 0))
        if vid_t(t3) <= v < s0:
            E.pill(f, 330, 520, W - 330, 588, (120, 10, 10), .7)
            E.blit(f, E.text_sprite("LAST TWO", 48, (255, 255, 255), "black", stroke=5, stroke_color=(0, 0, 0), spacing=4), W / 2, 554, alpha=.65 + .35 * math.sin(v * 9) ** 2)
        elif s0 <= v < v1:
            E.pill(f, 290, 520, W - 290, 588, (120, 10, 10), .7)
            E.blit(f, E.text_sprite("FINAL CLASH", 48, (255, 215, 90), "black", stroke=5, stroke_color=(0, 0, 0), spacing=4), W / 2, 554, alpha=.65 + .35 * math.sin(v * 12) ** 2)
        pops(f, v)
        if v >= v_end: card(f, v - v_end)
        if final and v > total - LOOP:
            bb = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - bb, draw(0, False), bb, 0)
        return f
    # ---- audio: tribal-ish pulse at 120 bpm, rock crunches on the beat, impacts, lava splashes, slow-mo riser, fanfare
    mix = E.Mix(total); hz = lambda m: float(E.midi_hz(m))
    for j in range(6): mix.add(.04 + j * .085, E.kalimba(hz(E.penta(j, 67)), .5), .3)
    for k in range(N): mix.add(land[k], E.thump(.18, 190, 60), .35, (P0 := (fr[0][1][k][0] - W / 2) / (W / 2) * .5))
    mix.add(T_FIGHT, E.chord([57, 64, 69], 1.2, E.bell), .5); mix.add(T_FIGHT, E.thump(.7, 130, 32), .9); mix.add(T_FIGHT - .2, E.whoosh(.4), .4)
    bass = [45, 45, 48, 43]; tb = T_FIGHT; k = 0
    while tb < s0 - .05:
        na = N - sum(1 for j in kos if vid_t(o_all[j]) <= tb)
        mix.add(tb, E.thump(.22, 150, 46), .42); mix.add(tb + BEAT / 2, E.kalimba(hz(bass[(k // 2) % 4]), .4), .3)
        mix.add(tb + BEAT / 2, E.tick(6400, .03), .1)
        if na <= 4: mix.add(tb + BEAT / 4, E.tick(5200, .025), .08); mix.add(tb + 3 * BEAT / 4, E.tick(5200, .025), .08)
        tb += BEAT; k += 1
    cr_t = sorted(set(float(c) for c in isl["crack"] if np.isfinite(c)))
    for c in cr_t:
        if vid_t(c) < s0: mix.add(vid_t(c), E.tick(1900, .06), .14)
        if vid_t(c + CRACK) < v_end: mix.add(vid_t(c + CRACK), E.thump(.35, 85, 30), .32); mix.add(vid_t(c + CRACK), E.whoosh(.25, 7), .18)
    per = {}
    for e in sim["ev"]:
        if e[0] != "hit": continue
        vt = vid_t(e[1]); b = int(vt * 5)
        if vt > v_end or per.get(b, 0) >= 2: continue
        per[b] = per.get(b, 0) + 1; pan = (e[4] - W / 2) / (W / 2) * .6; g = min(1.0, e[6] / 800)
        mix.add(vt, E.thump(.16, 260, 90), .25 + .35 * g, pan); mix.add(vt, E.kalimba(hz(E.penta(int(e[4] / W * 8) + 5, 60)), .4), .18 + .2 * g, pan)
    for e in outs:
        vt = vid_t(e[1]); pan = (e[3] - W / 2) / (W / 2) * .6
        mix.add(vt, E.slide_down(.9, 640, 130), .42, pan); mix.add(vt, E.chord([57, 60, 64], 1.0, E.bell), .26)
    mix.add(max(0, s0 - 1.8), E.riser(1.8 + (v1 - s0) * .6, 180, 2400), .32)
    mix.add(vid_t(t_f), E.thump(1.0, 100, 28), .9)
    for j, m in enumerate([69, 73, 76, 81]): mix.add(v_end + .2 + j * .12, E.kalimba(hz(m), 1.2), .5)
    mix.add(v_end + .7, E.chord([57, 61, 64, 69], 2.8, E.bell), .5)
    wav = out_mp4[:-4] + ".wav"; mix.write(wav, peak=.8)
    if stills:
        for t_ in stills: E.save_png(out_mp4[:-4] + f"_still_{t_:05.2f}.png", draw(min(n - 1, int(t_ * FPS)), False))
        return dict(total=total, v_end=v_end, s0=s0, v1=v1, t3=vid_t(t3), kos=[vid_t(o_all[j]) for j in kos])
    E.render(out_mp4, wav, n, draw); os.remove(wav)
    title = f"8 Flags, 1 Crumbling Island | Sumo Island Round #{ep}"
    desc = (f"8 flags bump each other on an island that crumbles into lava. Last one standing wins. Today: {names[win]} survives.\n\n"
            "Who did you pick? 👇\n\n#shorts #flags #lastonestanding #battleroyale #physics #simulation")
    return dict(duration=total, title=title, description=desc, tags=["flags", "last one standing", "battle royale", "physics", "simulation"],
                winner=names[win], knockout_order=[names[k] for k in kos], countries=names, seed=seed, thumb_ms=1400)


if __name__ == "__main__":                     # python3 -I lab/styles/sumo_island.py <out.mp4> <seed> [episode]
    import json
    out = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1; ep = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    res = build(out, seed, ep=ep, log=lambda *a: print(*a, file=sys.stderr)); print("RESULT=" + json.dumps(res, default=float))
