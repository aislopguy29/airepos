"""LAB STYLE moon_hop: 1-vs-1 sky-hop race to the moon. Split-screen towers: each animal auto-bounces up its own lane of
floating platforms (clouds low down, asteroid rocks in space), steering toward the highest platform it can reach.
Springs = super jump (BOING), cracked platforms crumble under you (CRACK), a misjudged hop = free-fall to a lower
platform (MISSED). Each lane has its own camera, so the sky behind each racer shows how high it is (day -> sunset ->
dusk -> space). A centre altitude ladder tracks both racers; first to touch the moon wins. Slow-mo final leap,
winner card, loop blend. Favorite (big jumps, slow feet) vs underdog (small jumps, quick feet). Pure simulation, no data."""
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import engine as E
from engine import W, H, FPS

EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
CAST = [dict(name="KANGAROO", emo="\U0001F998", col=(255, 176, 84), role="FAVORITE", jv=1600.0, vx=430.0, know=.45, slip=.08, pitch=55),
        dict(name="FROG", emo="\U0001F438", col=(118, 236, 120), role="UNDERDOG", jv=1520.0, vx=620.0, know=.62, slip=.06, pitch=67)]
LW = 476; LANE_X = [24, 580]; LAD_X = 540
G = 3400.0; FINISH = 6000.0; HEAD = 70.0
GROUND_Y = 1800                     # screen y of alt == cam
PW = 124                            # platform width (landing half-width PW/2 + 10)
T_GATE = 1.7; SIMHZ = 240; LEAD_H = 40.0
CAM_MAX = FINISH - 800
TOP_ALT = int(FINISH + 1150); BOT_ALT = -300
SPACE_ALT = 4600                    # clouds turn into asteroid rocks above this


# ------------------------------------------------------------------ world + simulation
def tower(seed, lane):
    rng = np.random.default_rng(seed * 31 + lane * 7 + 5); P = []; alt = 0.0; x = LW / 2
    while True:
        alt += rng.uniform(130, 235)
        if alt > FINISH - 300: break
        x = float(np.clip(x + rng.uniform(-200, 200), 70, LW - 70))
        P.append([x, alt, 1 if rng.random() < .09 else 0])
        if rng.random() < .5:                                   # side platform: often a cracked decoy sitting a bit higher
            x2 = float(np.clip(x + rng.choice([-1, 1]) * rng.uniform(160, 300), 70, LW - 70))
            if abs(x2 - x) >= 140: P.append([x2, alt + rng.uniform(-40, 90), 2 if rng.random() < .55 else 0])
    P.append([float(np.clip(x + rng.uniform(-150, 150), 70, LW - 70)), FINISH - rng.uniform(255, 285), 0])
    return np.array(P, np.float64)


def simulate(seed, max_t=42.0):
    rng = np.random.default_rng(seed + 17); T = [tower(seed, k) for k in range(2)]
    brk = [np.full(len(T[k]), np.inf) for k in range(2)]
    st = [dict(x=LW / 2, a=0.0, vy=0.0, vx=0.0, tx=LW / 2, tgt=-1, tl=0.0, launch=0.0, land_t=-9.0, ll=0.0, done=-1.0, mf=False) for _ in range(2)]
    ev = []; frames = []; dt = 1 / SIMHZ; step = SIMHZ // FPS; lead = [-1]; t_win = [None]

    def choose(k, t):
        s = st[k]; c = CAST[k]; P = T[k]; v = s["vy"]; hmax = v * v / (2 * G); diff = s["ll"] - st[1 - k]["ll"]
        slip = c["slip"] * (2.2 if diff > 250 else .35 if diff < -250 else 1.0)
        know = min(.95, c["know"] + (.25 if diff < -250 else 0))
        s["launch"] = s["a"]; s["mf"] = False
        if s["a"] + hmax + HEAD >= FINISH:
            s["tgt"] = -2; s["tx"] = s["x"]; s["tl"] = t + v / G; return
        dz = P[:, 1] - s["a"]; ok = (dz > 25) & (dz < hmax - 15) & (brk[k] > t)
        tl = (v + np.sqrt(np.maximum(v * v - 2 * G * dz, 0))) / G
        ok &= np.abs(P[:, 0] - s["x"]) <= c["vx"] * tl * .85 + PW / 2 - 20
        idx = [i for i in np.nonzero(ok)[0] if not (P[i, 2] == 2 and rng.random() < know)]
        if not idx:
            s["tgt"] = -1; s["tx"] = s["x"]; s["tl"] = t + 2 * v / G; return
        idx.sort(key=lambda i: -P[i, 1]); i = idx[1] if len(idx) > 1 and rng.random() < .25 else idx[0]
        s["tgt"] = i; s["tx"] = P[i, 0]; s["tl"] = t + tl[i]
        if rng.random() < slip:                                  # misjudged hop
            s["tx"] = float(np.clip(P[i, 0] + rng.choice([-1, 1]) * rng.uniform(PW / 2 + 30, PW / 2 + 90), 42, LW - 42))

    for n in range(int(max_t * SIMHZ)):
        t = n * dt
        if n % step == 0:
            frames.append(dict(t=t, x=np.array([s["x"] for s in st]), a=np.array([s["a"] for s in st]), vx=np.array([s["vx"] for s in st]),
                               vy=np.array([s["vy"] for s in st]), land=np.array([s["land_t"] for s in st]), ll=np.array([s["ll"] for s in st]),
                               done=np.array([s["done"] for s in st])))
        if t < T_GATE: continue
        if abs(t - T_GATE) < dt / 2:
            for k in range(2): st[k]["vy"] = CAST[k]["jv"]; st[k]["land_t"] = t; choose(k, t); ev.append(("hop", t, k, st[k]["x"], 0.0, 0))
        for k in range(2):
            s = st[k]; c = CAST[k]; P = T[k]
            if s["done"] >= 0: continue
            trem = max(s["tl"] - t, .06); vdes = float(np.clip((s["tx"] - s["x"]) / trem, -c["vx"], c["vx"]))
            s["vx"] += (vdes - s["vx"]) * min(1.0, 12 * dt); s["x"] = float(np.clip(s["x"] + s["vx"] * dt, 40, LW - 40))
            s["vy"] -= G * dt; a0 = s["a"]; a1 = a0 + s["vy"] * dt
            if a1 + HEAD >= FINISH:                                   # touched the moon
                s["a"] = FINISH - HEAD; s["vy"] = 0; s["done"] = t; ev.append(("moon", t, k, s["x"], s["a"], 0))
                if t_win[0] is None: t_win[0] = t
                continue
            if s["vy"] < 0:
                if s["tgt"] >= 0 and not s["mf"] and a1 < P[s["tgt"], 1] - 4 and P[s["tgt"], 1] > s["launch"] - 1:
                    s["mf"] = True; ev.append(("miss", t, k, s["x"], a1, 0))
                hit = np.nonzero((P[:, 1] <= a0) & (P[:, 1] > a1) & (np.abs(P[:, 0] - s["x"]) <= PW / 2 + 10) & (brk[k] > t))[0]
                if len(hit) or a1 <= 0:
                    if len(hit): i = hit[np.argmax(P[hit, 1])]; pa, kind = P[i, 1], int(P[i, 2])
                    else: i, pa, kind = -1, 0.0, 0
                    if kind == 2:
                        brk[k][i] = t; s["a"] = pa - .5; ev.append(("crack", t, k, P[i, 0], pa, i)); continue
                    s["a"] = pa; s["land_t"] = t; drop = s["ll"] - pa; s["ll"] = pa
                    rb = float(np.clip((st[1 - k]["ll"] - pa) / 2500, 0, .09))              # rubber band: trailing racer hops a bit higher
                    s["vy"] = c["jv"] * (1 + rb) * (1.72 if kind == 1 else 1.0)
                    ev.append(("spring" if kind == 1 else "hop", t, k, s["x"], pa, i))
                    if drop > 150: ev.append(("drop", t, k, s["x"], pa, int(drop)))
                    choose(k, t); continue
            s["a"] = a1
        if t > T_GATE + .8 and min(st[0]["done"], st[1]["done"]) < 0:   # lead changes (by last platform reached)
            d = st[0]["ll"] - st[1]["ll"]
            if lead[0] == -1 and abs(d) > LEAD_H: lead[0] = 0 if d > 0 else 1
            elif lead[0] == 0 and d < -LEAD_H: lead[0] = 1; ev.append(("lead", t, 1, 0, 0, 0))
            elif lead[0] == 1 and d > LEAD_H: lead[0] = 0; ev.append(("lead", t, 0, 0, 0, 0))
        if t_win[0] is not None and t > t_win[0] + 1.3:
            frames.append(frames[-1]); return dict(frames=frames, ev=ev, T=t, towers=T, brk=brk, t1=t_win[0])
    return None


def pick(seed0, tries=40, log=print):
    best = None
    for seed in range(seed0, seed0 + tries):
        sim = simulate(seed)
        if not sim: continue
        t1 = sim["t1"]; ev = sim["ev"]; win = [e for e in ev if e[0] == "moon"][0][2]
        fr = min(sim["frames"], key=lambda f: abs(f["t"] - t1)); gap = FINISH - HEAD - fr["a"][1 - win]
        if fr["done"][1 - win] >= 0: gap = 0
        changes = sum(1 for e in ev if e[0] == "lead"); late = [e for e in ev if e[0] == "lead" and e[1] > t1 - 7]
        drama = sum(1 for e in ev if e[0] in ("crack", "miss", "spring"))
        cnt = {k: sum(1 for e in ev if e[0] == k) for k in ("crack", "miss", "spring")}
        score = min(changes, 6) * .45 + (.8 if late else 0) - gap / 260 + (1.2 if win == 1 else 0) + min(drama, 10) * .12 - abs(t1 - 19.5) / 3
        okk = 16.0 <= t1 <= 23.5 and changes >= 3 and gap < 520 and min(cnt.values()) >= 1
        if okk and (best is None or score > best[0]): best = (score, seed, sim, changes, gap, win, cnt)
    assert best, "no good seed"
    log(f"[moon_hop] seed {best[1]}: winner {CAST[best[5]]['name']} at {best[2]['t1']:.1f}s, lead changes {best[3]}, gap {best[4]:.0f}px, {best[6]}")
    return best[1], best[2]


# ------------------------------------------------------------------ sprites
_ec = {}
def emoji(ch, size):
    if (ch, size) in _ec: return _ec[(ch, size)]
    f = ImageFont.truetype(EMOJI, 109); im = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((100, 100), ch, font=f, embedded_color=True, anchor="mm"); im = im.crop(im.getbbox())
    s = size / max(im.size); im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS)
    a = np.array(im); _ec[(ch, size)] = a; return a


def _rgba(w, h): return np.zeros((h, w, 4), np.uint8)


def cloud_sprite(kind, space):
    """kind 0 normal, 1 spring, 2 cracked; space=True -> asteroid rock. Top surface sits at sprite row 14."""
    w, h = PW + 16, 70; a = _rgba(w, h); cx = w // 2
    if not space:
        body = (250, 251, 255, 255) if kind != 2 else (184, 188, 204, 255); shade = (206, 218, 240, 255) if kind != 2 else (140, 144, 166, 255)
        cv2.ellipse(a, (cx, 40), (PW // 2, 18), 0, 0, 360, shade, -1, cv2.LINE_AA)
        for (dx, dy, r) in ((-34, 30, 20), (0, 24, 26), (34, 30, 20), (-52, 38, 14), (52, 38, 14)):
            cv2.circle(a, (cx + dx, dy + 2), r, shade, -1, cv2.LINE_AA)
        cv2.ellipse(a, (cx, 36), (PW // 2 - 4, 15), 0, 0, 360, body, -1, cv2.LINE_AA)
        for (dx, dy, r) in ((-34, 28, 18), (0, 22, 24), (34, 28, 18), (-50, 35, 12), (50, 35, 12)):
            cv2.circle(a, (cx + dx, dy), r, body, -1, cv2.LINE_AA)
    else:
        body = (150, 128, 116, 255) if kind != 2 else (112, 100, 104, 255); edge = (92, 78, 72, 255)
        pts = np.array([[cx - 60, 30], [cx - 44, 16], [cx - 10, 12], [cx + 26, 14], [cx + 56, 22], [cx + 62, 38], [cx + 40, 54], [cx - 8, 58], [cx - 48, 52]], np.int32)
        cv2.fillPoly(a, [pts], edge, cv2.LINE_AA); cv2.fillPoly(a, [(pts * [1, 1] + [0, -3]).astype(np.int32)], body, cv2.LINE_AA)
        for (dx, dy, r) in ((-28, 32, 7), (14, 26, 5), (34, 40, 6), (-4, 44, 4)): cv2.circle(a, (cx + dx, dy), r, edge, -1, cv2.LINE_AA)
    if kind == 2:
        crack = np.array([[cx - 8, 10], [cx + 4, 24], [cx - 6, 34], [cx + 8, 46], [cx - 2, 58]], np.int32)
        cv2.polylines(a, [crack], False, (60, 60, 78, 255), 3, cv2.LINE_AA)
        cv2.line(a, (cx + 4, 24), (cx + 22, 30), (60, 60, 78, 255), 2, cv2.LINE_AA); cv2.line(a, (cx - 6, 34), (cx - 26, 40), (60, 60, 78, 255), 2, cv2.LINE_AA)
    return a


def spring_sprite(compressed):
    w, h = 44, 40; a = _rgba(w, h); top = 22 if compressed else 4; base = 36
    ys = np.linspace(base, top + 6, 6)
    for j in range(5):
        cv2.line(a, (8 if j % 2 == 0 else 36, int(ys[j])), (36 if j % 2 == 0 else 8, int(ys[j + 1])), (235, 70, 70, 255), 4, cv2.LINE_AA)
    cv2.rectangle(a, (4, top), (40, top + 6), (255, 210, 80, 255), -1, cv2.LINE_AA)
    return a


def sky_color(alt):
    keys = [(-300, (110, 196, 255)), (1200, (96, 172, 246)), (2300, (255, 178, 122)), (3200, (236, 112, 150)),
            (4100, (118, 64, 156)), (4900, (30, 24, 70)), (5600, (8, 8, 26)), (99999, (8, 8, 26))]
    for (a0, c0), (a1, c1) in zip(keys, keys[1:]):
        if alt <= a1:
            u = E.smooth((alt - a0) / (a1 - a0)); return tuple(c0[i] + (c1[i] - c0[i]) * u for i in range(3))
    return keys[-1][1]


def lane_strip(lane, seed):
    """Static backdrop of one lane: row r <-> altitude TOP_ALT - r."""
    rng = np.random.default_rng(seed * 13 + lane); n = TOP_ALT - BOT_ALT
    alts = TOP_ALT - np.arange(n)
    col = np.array([sky_color(a) for a in alts[::4]], np.float32); col = np.repeat(col, 4, 0)[:n]
    strip = np.broadcast_to(col[:, None, :], (n, LW, 3)).copy()
    xx = np.linspace(-1, 1, LW, dtype=np.float32)[None, :, None]; strip *= (1 - .18 * xx ** 2)
    strip = np.clip(strip, 0, 255).astype(np.uint8)
    for _ in range(14):                                                    # soft distant clouds (day/sunset)
        al = rng.uniform(300, 3600); r = int(TOP_ALT - al); x = int(rng.uniform(0, LW)); rx, ry = int(rng.uniform(70, 150)), int(rng.uniform(16, 30))
        ov = strip.copy(); cv2.ellipse(ov, (x, r), (rx, ry), 0, 0, 360, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.addWeighted(ov, .14 if al < 2200 else .09, strip, 1 - (.14 if al < 2200 else .09), 0, strip)
    for _ in range(260):                                                   # stars fade in with altitude
        al = rng.uniform(3900, TOP_ALT); r = int(TOP_ALT - al); x = int(rng.uniform(4, LW - 4))
        k = E.smooth((al - 3900) / 1300); b = int(140 + 115 * rng.random()); c = tuple(int(strip[r, x, j] * (1 - k) + b * k) for j in range(3))
        cv2.circle(strip, (x, r), 1 if rng.random() < .8 else 2, c, -1, cv2.LINE_AA)
    g0 = TOP_ALT - 0                                                       # ground (alt < 0)
    strip[g0:] = (78, 168, 82); strip[g0:g0 + 16] = (120, 214, 104)
    for x in range(0, LW, 18): cv2.circle(strip, (x + 9, g0 + 4), 9, (120, 214, 104), -1, cv2.LINE_AA)
    strip[g0 + 60:] = (120, 88, 60)
    moon = np.zeros((n, LW), np.float32); mc = (LW // 2 + (40 if lane == 0 else -40), int(TOP_ALT - (FINISH + 330)))   # moon: bottom at FINISH
    halo = np.zeros((n, LW), np.float32); cv2.circle(halo, mc, 380, 1.0, -1, cv2.LINE_AA)
    sub = slice(max(0, mc[1] - 520), mc[1] + 520); halo[sub] = cv2.GaussianBlur(halo[sub], (0, 0), 30)
    strip[sub] = np.clip(strip[sub] + halo[sub][..., None] * np.array([60, 60, 90], np.float32), 0, 255).astype(np.uint8)
    cv2.circle(strip, mc, 330, (222, 222, 232), -1, cv2.LINE_AA); cv2.circle(strip, (mc[0] - 30, mc[1] - 40), 330 - 36, (236, 236, 244), -1, cv2.LINE_AA)
    for (dx, dy, r) in ((-120, 180, 46), (90, 230, 34), (10, 120, 26), (150, 110, 22), (-60, 270, 18), (-170, 60, 30)):
        cv2.circle(strip, (mc[0] + dx, mc[1] + dy), r, (190, 190, 204), -1, cv2.LINE_AA); cv2.circle(strip, (mc[0] + dx + 4, mc[1] + dy + 4), int(r * .75), (205, 205, 216), -1, cv2.LINE_AA)
    return strip


# ------------------------------------------------------------------ build
def build(out_mp4, seed=1, race_no=1, log=print, stills=None):
    seed, sim = pick(seed, log=log); fr = sim["frames"]; ev = sim["ev"]; T = sim["towers"]; brk = sim["brk"]; t1 = sim["t1"]
    win = [e for e in ev if e[0] == "moon"][0][2]; lose = 1 - win
    S, s0, s1 = .3, t1 - .75, t1 + .2
    v1 = s0 + (s1 - s0) / S
    def sim_t(v): return v if v < s0 else s0 + (v - s0) * S if v < v1 else s1 + (v - v1)
    def vid_t(t): return t if t < s0 else s0 + (t - s0) / S if t < s1 else v1 + (t - s1)
    v_end = vid_t(sim["T"]); CARD = 3.7; total = v_end + CARD; n = int(round(total * FPS)); LOOP = .35
    ffin = min(fr, key=lambda f: abs(f["t"] - t1)); gap_m = int(round((FINISH - HEAD - ffin["a"][lose]) / 10)) if ffin["done"][lose] < 0 else 0
    lose_t = [e[1] for e in ev if e[0] == "moon" and e[2] == lose]; gap_s = round(lose_t[0] - t1, 1) if lose_t else None
    log(f"[moon_hop] video {total:.1f}s, winner {CAST[win]['name']}, loser short by {gap_m} m")

    strips = [lane_strip(k, seed) for k in range(2)]
    spr_plat = {(k, s): cloud_sprite(k, s) for k in range(3) for s in (False, True)}
    spr_half = {}
    for key, sp in spr_plat.items():
        if key[0] == 2: c = sp.shape[1] // 2; spr_half[key] = (sp[:, :c].copy(), sp[:, c:].copy())
    spr_spring = [spring_sprite(False), spring_sprite(True)]
    ani = [emoji(c["emo"], 92) for c in CAST]; ani_f = [a[:, ::-1].copy() for a in ani]
    mini = [emoji(c["emo"], 40) for c in CAST]; big = [emoji(c["emo"], 230) for c in CAST]; head = [emoji(c["emo"], 64) for c in CAST]
    spring_use = [dict() for _ in range(2)]
    for e in ev:
        if e[0] == "spring": spring_use[e[2]].setdefault(e[5], []).append(e[1])

    def state(t):
        f = t * FPS; i0 = min(len(fr) - 2, int(f)); w = min(1.0, max(0.0, f - i0)); A, B = fr[i0], fr[i0 + 1]
        return dict(x=A["x"] * (1 - w) + B["x"] * w, a=A["a"] * (1 - w) + B["a"] * w, vx=A["vx"], vy=A["vy"], land=A["land"], ll=A["ll"], done=A["done"])
    cams = [[], []]; c_ = [0.0, 0.0]; cv_ = [0.0, 0.0]; disp = [[], []]; dv = [0.0, 0.0]
    for i in range(n):
        v = min(i / FPS, v_end); s = state(sim_t(v))
        for k in range(2):
            tgt = float(np.clip(max(min(s["ll"][k] - 430, s["a"][k] - 300), s["a"][k] - 1000), 0, CAM_MAX)); kk = 5.0 if s["a"][k] - c_[k] < 1000 else 9.0
            acc = kk * kk * (tgt - c_[k]) - 2 * kk * cv_[k]; cv_[k] += acc / FPS; c_[k] = float(np.clip(max(c_[k] + cv_[k] / FPS, s["a"][k] - 1150), 0, CAM_MAX)); cams[k].append(c_[k])   # racer never hides under the HUD
            dv[k] += (s["ll"][k] - dv[k]) * .18; disp[k].append(dv[k])

    band = np.ones((520, 1, 1), np.float32); band[:430] = .16; band[430:520] = np.linspace(.16, 1, 90)[:, None, None]
    vs_spr = E.text_sprite("vs", 44, (255, 255, 255), "black", stroke=5, stroke_color=(0, 0, 0))
    nm_spr = [E.text_sprite(c["name"], 58, c["col"], "black", stroke=5, stroke_color=(0, 0, 0)) for c in CAST]
    sub_spr = E.text_sprite("FIRST TO TOUCH THE MOON WINS", 27, (175, 225, 255), "bold", spacing=3)
    role_spr = [E.text_sprite(c["role"], 20, (210, 210, 228), "bold", spacing=3) for c in CAST]
    hooks = [(0, T_GATE, "PICK ONE BEFORE THEY JUMP"), (T_GATE, 4.3, "BIG JUMPS  vs  QUICK FEET")]
    lead_ev = [e for e in ev if e[0] == "lead"]
    pops = [e for e in ev if e[0] in ("spring", "crack", "miss", "drop")]

    def lead_at(t):
        L = None
        for e in lead_ev:
            if e[1] <= t: L = e
        return L
    def draw(i, final=True):
        v = i / FPS; t = sim_t(min(v, v_end)); s = state(t)
        f = np.empty((H, W, 3), np.uint8); f[:] = (14, 15, 32)
        for k in range(2):
            cam = cams[k][min(i, n - 1)]; r0 = int(TOP_ALT - (cam + GROUND_Y)); lx = LANE_X[k]
            f[:, lx:lx + LW] = strips[k][r0:r0 + H]
            def sy(alt): return GROUND_Y - (alt - cam)
            P = T[k]
            for j in range(len(P)):
                y = sy(P[j, 1])
                if y < 380 or y > H + 80: continue
                kind = int(P[j, 2]); space = P[j, 1] > SPACE_ALT; x = lx + P[j, 0]
                if kind == 2 and t >= brk[k][j]:
                    age = t - brk[k][j]
                    if age < .7:
                        hl, hr = spr_half[(2, space)]; dy = 900 * age * age; al = 1 - E.smooth(age / .7)
                        E.blit(f, hl, x - hl.shape[1] / 2 - 30 * age, y + 21 + dy, alpha=al); E.blit(f, hr, x + hr.shape[1] / 2 + 30 * age, y + 21 + dy, alpha=al)
                    continue
                sp = spr_plat[(kind, space)]; E.blit(f, sp, x, y + sp.shape[0] / 2 - 14)
                if kind == 1:
                    comp = any(0 <= t - u < .16 for u in spring_use[k].get(j, []))
                    E.blit(f, spr_spring[1 if comp else 0], x, y - 20 - (0 if comp else 6))
            x = lx + s["x"][k]; y = sy(s["a"][k]); sq = t - s["land"][k]
            spr = ani_f[k] if (s["vx"][k] > 30 and k == 0) or (s["vx"][k] < -30 and k == 1) else ani[k]
            if s["vy"][k] > CAST[k]["jv"] * 1.2 and s["done"][k] < 0:                       # spring trail
                for g in range(1, 5): E.blit(f, spr, x, y - 46 + g * 34, alpha=.22 - g * .045)
            if 0 <= sq < .14 and s["done"][k] < 0:
                u = sq / .14; sxy = (1.18 - .18 * u, .78 + .22 * u)
                sp2 = cv2.resize(spr, (int(spr.shape[1] * sxy[0]), int(spr.shape[0] * sxy[1])), interpolation=cv2.INTER_LINEAR)
                E.blit(f, sp2, x, y - sp2.shape[0] / 2)
            else: E.blit(f, spr, x, y - spr.shape[0] / 2)
            for e in pops:                                                                  # event pops above the racer
                if e[2] != k: continue
                age = v - vid_t(e[1])
                if not 0 <= age < .9: continue
                txt, colr = {"spring": ("BOING!", (255, 226, 90)), "crack": ("CRACK!", (235, 235, 245)), "miss": ("MISSED!", (255, 96, 110)),
                             "drop": (f"-{e[5] // 10} m", (255, 140, 140))}[e[0]]
                px = float(np.clip(lx + e[3], lx + 120, lx + LW - 120)); py = sy(e[4]) - (190 if e[0] != "drop" else 120) - 70 * age
                if e[0] == "drop": py += 60
                E.blit(f, E.text_sprite(txt, 52, colr, "black", stroke=6, stroke_color=(0, 0, 0)), px, max(560, py), alpha=1 - E.smooth((age - .65) / .25), scale=E.out_back(age / .2))
        # lane frames + centre ladder
        for k in range(2): cv2.rectangle(f, (LANE_X[k] - 2, 0), (LANE_X[k] + LW + 1, H), (40, 44, 80), 3)
        y_top, y_bot = 600, 1640
        cv2.line(f, (LAD_X, y_top), (LAD_X, y_bot), (70, 78, 120), 4, cv2.LINE_AA)
        for q in range(11): yq = int(y_bot - (y_bot - y_top) * q / 10); cv2.line(f, (LAD_X - 10, yq), (LAD_X + 10, yq), (70, 78, 120), 2, cv2.LINE_AA)
        cv2.circle(f, (LAD_X, y_top - 22), 18, (226, 226, 236), -1, cv2.LINE_AA); cv2.circle(f, (LAD_X - 5, y_top - 26), 5, (190, 190, 204), -1, cv2.LINE_AA)
        cv2.circle(f, (LAD_X, y_bot + 18), 12, (110, 200, 100), -1, cv2.LINE_AA)
        for k in range(2):
            u = float(np.clip(s["a"][k] / (FINISH - HEAD), 0, 1)); E.blit(f, mini[k], LAD_X + (-17 if k == 0 else 17), y_bot - (y_bot - y_top) * u)
        # top HUD
        f[:520] = (f[:520] * band).astype(np.uint8)
        wl, wr, wv = nm_spr[0].shape[1], nm_spr[1].shape[1], vs_spr.shape[1]; tw = 64 + 14 + wl + 22 + wv + 22 + wr + 14 + 64; x0 = W / 2 - tw / 2
        E.blit(f, head[0], x0 + 32, 282); E.blit(f, nm_spr[0], x0 + 78, 285, anchor="l"); E.blit(f, vs_spr, x0 + 78 + wl + 22 + wv / 2, 288)
        E.blit(f, nm_spr[1], x0 + 78 + wl + 22 + wv + 22, 285, anchor="l"); E.blit(f, head[1], x0 + tw - 32, 282)
        E.blit(f, sub_spr, W / 2, 344)
        L = lead_at(t); ld = L[2] if L else (0 if s["ll"][0] > s["ll"][1] + LEAD_H else 1 if s["ll"][1] > s["ll"][0] + LEAD_H else -1)
        if s["done"][win] >= 0: ld = win
        for k in range(2):
            cx = LANE_X[k] + LW / 2; E.blit(f, role_spr[k], cx, 398)
            m = int(round(disp[k][min(i, n - 1)] / 10)); mt = "MOON!" if s["done"][k] >= 0 else f"{m} m"
            colr = (255, 214, 70) if ld == k and v > T_GATE + .8 else (240, 240, 250)
            E.blit(f, E.text_sprite(mt, 50, colr, "black", stroke=5, stroke_color=(0, 0, 0)), cx, 452)
            if ld == k and v > T_GATE + .8 and s["done"][k] < 0:
                E.pill(f, cx + 96, 432, cx + 196, 472, (255, 200, 60), .95); E.blit(f, E.text_sprite("LEAD", 22, (30, 20, 0), "black", spacing=2), cx + 146, 452)
        # bottom status line
        def status(txt, colr, a=1.0, wpad=60):
            sp = E.text_sprite(txt, 34, colr, "bold", stroke=4, stroke_color=(0, 0, 0)); hw = sp.shape[1] / 2 + 36
            E.pill(f, W / 2 - hw, 1550, W / 2 + hw, 1614, (0, 0, 0), .6 * a); E.blit(f, sp, W / 2, 1582, alpha=a)
        shown = False
        for (a0, a1, txt) in hooks:
            if a0 <= v < a1: status(txt, (255, 230, 140), E.smooth((v - a0) / .25)); shown = True
        if not shown and v < s0:
            if L and v - vid_t(L[1]) < 1.3: status(f"{CAST[L[2]]['name']} TAKES THE LEAD!", (255, 214, 70))
            elif s0 - v < 2.4: status("ALMOST AT THE MOON...", (180, 225, 255))
            elif ld >= 0: status(f"LEADER: {CAST[ld]['name']}", (255, 255, 255))
        if s0 <= v < v1: status("WHO TOUCHES IT FIRST?", (255, 110, 140), .7 + .3 * math.sin(v * 10) ** 2)
        if v < T_GATE:                                                                       # hook + countdown
            E.blit(f, E.text_sprite("FIRST TO THE MOON WINS", 64, (255, 255, 255), "black", stroke=7, stroke_color=(0, 0, 0)), W / 2, 720, scale=E.out_back(min(1, v / .3)))
            cnt = ["3", "2", "1"][min(2, int(v / (T_GATE / 3)))]; u = (v % (T_GATE / 3)) / (T_GATE / 3)
            E.blit(f, E.text_sprite(cnt, 150, (255, 255, 255), "black", stroke=8, stroke_color=(0, 0, 0)), W / 2, 960, alpha=1 - u * .6, scale=E.out_back(u / .35))
        elif v < T_GATE + .6: E.blit(f, E.text_sprite("JUMP!", 140, (120, 255, 140), "black", stroke=8, stroke_color=(0, 0, 0)), W / 2, 960, alpha=1 - E.smooth((v - T_GATE) / .6))
        tw_ = vid_t(t1)
        if tw_ <= v < v_end:
            age = v - tw_; E.blit(f, E.text_sprite(f"{CAST[win]['name']} TOUCHES THE MOON!", 50, (255, 226, 90), "black", stroke=6, stroke_color=(0, 0, 0)), W / 2, 640,
                                   alpha=E.smooth(age / .2), scale=E.out_back(age / .3))
        if v >= v_end:                                                                       # winner card
            u = v - v_end; a_ = E.smooth(u / .3); f[:] = cv2.convertScaleAbs(f, alpha=1 - .82 * a_)
            E.blit(f, big[win], W / 2, 640, alpha=a_, scale=E.out_back(u / .45))
            E.blit(f, E.text_sprite(f"{CAST[win]['name']} WINS", 104, CAST[win]["col"], "black", stroke=7, stroke_color=(0, 0, 0)), W / 2, 880, alpha=a_, scale=E.out_back((u - .1) / .4))
            E.blit(f, E.text_sprite("FIRST TO TOUCH THE MOON", 36, (175, 225, 255), "bold", spacing=3), W / 2, 975, alpha=E.smooth((u - .4) / .3))
            sub2 = (f"{CAST[lose]['name']} TOUCHED IT {gap_s:.1f} s LATER" if gap_s and gap_s >= .1 else f"{CAST[lose]['name']} WAS A SPLIT SECOND BEHIND") if gap_s is not None else f"{CAST[lose]['name']} WAS {gap_m} m SHORT"
            E.blit(f, E.text_sprite(sub2, 34, (230, 230, 240), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1040, alpha=E.smooth((u - .7) / .3))
            E.blit(f, E.text_sprite(f"TEAM {CAST[0]['name']} OR TEAM {CAST[1]['name']}?", 44, (255, 226, 120), "black", stroke=4, stroke_color=(0, 0, 0)), W / 2, 1200, alpha=E.smooth((u - 1.1) / .3))
            E.blit(f, mini[0], W / 2 - 70, 1290, alpha=E.smooth((u - 1.3) / .3), scale=1.6); E.blit(f, mini[1], W / 2 + 70, 1290, alpha=E.smooth((u - 1.3) / .3), scale=1.6)
        if final and v > total - LOOP:
            bb = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - bb, draw(0, False), bb, 0)
        return f

    # ---- audio: gentle glitch/IDM bed (pluck arps, clicky kit) + boing hops pitched by height, cracks, misses, moon chord
    mix = E.Mix(total, mood="glitch"); hz = lambda m: float(E.midi_hz(m))
    mix.bed(T_GATE, v_end, gain=.26, seed=seed, intensity=lambda tt: min(1.0, .3 + tt / (s0 + 1e-6) * .7), drums_off=[(s0, v1)])
    def boing(f0, dur=.22, up=1.7):
        tt = np.arange(int(dur * E.SR)) / E.SR; fq = f0 * (1 + (up - 1) * (1 - np.exp(-tt * 18)))
        return (np.sin(2 * np.pi * np.cumsum(fq) / E.SR) * np.exp(-tt * 14) * (1 - np.exp(-tt * 900)) * .5).astype(np.float32)
    for j in range(3): mix.add(j * T_GATE / 3, E.tick(hz(86), .09), .6)
    mix.add(T_GATE, E.chord([62, 66, 69, 74], .9, E.bell), .45); mix.add(T_GATE, E.whoosh(.4), .4)
    last_snd = [-1, -1]
    for e in ev:
        vt = vid_t(e[1])
        if vt > v_end: continue
        k = e[2]; pan = -.45 if k == 0 else .45
        if e[0] == "hop" and vt - last_snd[k] > .12:
            step_ = int(e[4] / FINISH * 9); mix.add(vt, boing(hz(CAST[k]["pitch"] + E.PENTA[step_ % 5] + 12 * (step_ // 5))), .2, pan); last_snd[k] = vt
        elif e[0] == "spring": mix.add(vt, boing(hz(CAST[k]["pitch"] + 7), .45, 2.6), .42, pan); mix.add(vt + .05, E.bell(hz(CAST[k]["pitch"] + 24), .7), .18, pan)
        elif e[0] == "crack": mix.add(vt, E.whoosh(.18, 7), .5, pan); mix.add(vt, E.thump(.18, 420, 160), .3, pan)
        elif e[0] == "miss": mix.add(vt, E.slide_down(.6, 720, 210), .3, pan)
        elif e[0] == "lead": mix.add(vt, E.chord([74, 78, 81], .8, E.bell), .3, pan)
        elif e[0] == "moon": mix.add(vt, E.chord([62, 66, 69, 74, 78], 2.4, E.bell), .62); mix.add(vt, E.thump(.5, 160, 40), .5)
    mix.add(max(0, s0 - 2.0), E.riser(2.0 + (v1 - s0) * .5, 240, 2600), .32)
    for j, m in enumerate([62, 66, 69, 74, 78]): mix.add(v_end + .2 + j * .11, E.pluck(hz(m), 1.0), .45)
    mix.add(v_end + .8, E.chord([50, 57, 62, 66, 69], 2.6, E.bell), .42)
    wav = out_mp4[:-4] + ".wav"; mix.write(wav, peak=.8)
    if stills:
        for t_ in stills: E.save_png(out_mp4[:-4] + f"_still_{t_:05.2f}.png", draw(min(n - 1, int(t_ * FPS)), False))
        return dict(total=total, v_end=v_end, s0=s0, v1=v1, t1=t1)
    E.render(out_mp4, wav, n, draw); os.remove(wav)
    cnt = {k: sum(1 for e in ev if e[0] == k) for k in ("spring", "crack", "miss", "lead")}
    title = f"{CAST[0]['name'].title()} vs {CAST[1]['name'].title()}: First to the Moon Wins | Moon Hop #{race_no}"
    desc = (f"Two jumpers, two towers of clouds and space rocks, one moon. Springs launch you, cracked platforms drop you. "
            f"Team {CAST[0]['name'].title()} or Team {CAST[1]['name'].title()}?\n\n#shorts #kangaroo #frog #race #simulation")
    return dict(duration=total, title=title, description=desc, tags=["kangaroo vs frog", "race", "simulation", "animals", "satisfying"],
                winner=CAST[win]["name"], loser=CAST[lose]["name"], gap_m=gap_m, loser_behind_s=gap_s, t_win=round(t1, 2), lead_changes=cnt["lead"],
                springs=cnt["spring"], cracks=cnt["crack"], misses=cnt["miss"], seed=seed, slowmo_video_s=[round(s0, 2), round(v1, 2)],
                thumb_ms=600)


if __name__ == "__main__":                     # python3 -I lab/styles/moon_hop.py <out.mp4> <seed> [episode] [stills,comma,sep]
    import json
    out = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1; ep = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    st_ = [float(x) for x in sys.argv[4].split(",")] if len(sys.argv) > 4 else None
    res = build(out, seed, race_no=ep, log=lambda *a: print(*a, file=sys.stderr), stills=st_); print("RESULT=" + json.dumps(res, default=float))
