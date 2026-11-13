"""LAB STYLE flag_drop: 8 flag marbles race down a tall course (peg field, zigzag ramps, bumpers, funnel).
Camera follows the leader, live order strip on top, slow-mo photo finish, podium card. Pure physics + chance: no data."""
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import engine as E
from engine import W, H, FPS

EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
POOL = [("FRANCE", "🇫🇷"), ("ITALY", "🇮🇹"), ("USA", "🇺🇸"), ("UK", "🇬🇧"), ("MEXICO", "🇲🇽"), ("BRAZIL", "🇧🇷"), ("JAPAN", "🇯🇵"),
        ("INDIA", "🇮🇳"), ("GERMANY", "🇩🇪"), ("SPAIN", "🇪🇸"), ("CANADA", "🇨🇦"), ("KOREA", "🇰🇷"), ("ARGENTINA", "🇦🇷"),
        ("AUSTRALIA", "🇦🇺"), ("EGYPT", "🇪🇬"), ("SWEDEN", "🇸🇪")]
R, N = 30, 8
WL, WR = 34, W - 34
OFF = 170                                   # course offset so the gate sits below the HUD
GATE_Y, FINISH_Y = 470 + OFF, 4520 + OFF
CH = FINISH_Y + 640                          # course height (px): finish line ends ~1280 px down the screen
T_GATE, G, VMAX = 1.6, 2100.0, 1400.0

def course(seed):
    rng = np.random.default_rng(seed + 991)
    pegs = []
    for k in range(10):                                            # A: peg field
        y = 700 + k * 108
        for j in range(10):
            x = 92 + j * 112 + (56 if k % 2 else 0) + rng.uniform(-6, 6)
            if WL + 20 < x < WR - 20: pegs.append((x, y, 10, 0.55))
    segs = []                                                      # B: zigzag ramps
    for k in range(4):
        y = 1880 + k * 280
        if k % 2 == 0: segs.append(((WL, y), (800 + rng.uniform(-40, 40), y + 115)))
        else: segs.append(((WR, y), (280 + rng.uniform(-40, 40), y + 115)))
    for r_, row in enumerate(range(3020, 3800, 190)):              # C: bumper field
        xs = [200, 540, 880] if r_ % 2 == 0 else [370, 710]
        for x in xs: pegs.append((x + rng.uniform(-25, 25), row, 40, 1.12))
        for x in ([370, 710] if r_ % 2 == 0 else [200, 540, 880]): pegs.append((x, row + 30, 9, 0.5))
    segs += [((WL, 3930), (468, 4210)), ((WR, 3930), (612, 4210))]  # D: funnel (gap 144)
    for x in (430, 540, 650): pegs.append((x + rng.uniform(-10, 10), 4360, 10, 0.55))
    pegs = np.array(pegs, np.float64); pegs[:, 1] += OFF
    segs = [((a[0], a[1] + OFF), (b[0], b[1] + OFF)) for a, b in segs]
    return pegs, segs

def simulate(seed, n_names, dt=1 / 240, max_t=45.0):
    rng = np.random.default_rng(seed); pegs, segs = course(seed)
    P = np.stack([np.linspace(WL + 70, WR - 70, N) + rng.uniform(-8, 8, N), np.full(N, GATE_Y - 40.0)], 1)
    rng.shuffle(P[:, 0]); V = np.zeros((N, 2)); done = np.full(N, -1.0); ev = []; frames = []
    still = np.zeros(N); last_snd = np.full(N, -1.0); step = int(round(1 / (FPS * dt)))
    A = np.array([s[0] for s in segs], float); B = np.array([s[1] for s in segs], float)
    for s in range(int(max_t / dt)):
        t = s * dt
        if s % step == 0: frames.append(dict(t=t, P=P.copy(), done=done.copy()))
        if t < T_GATE: continue
        act = done < 0
        V[act, 1] += G * dt
        sp = np.hypot(V[:, 0], V[:, 1]); k = sp > VMAX; V[k] *= (VMAX / sp[k])[:, None]
        P[act] += V[act] * dt
        for i in np.nonzero(act)[0]:
            p, v = P[i], V[i]
            if p[0] < WL + R: p[0] = WL + R; v[0] = abs(v[0]) * .5
            if p[0] > WR - R: p[0] = WR - R; v[0] = -abs(v[0]) * .5
            d = p - pegs[:, :2]; dist = np.hypot(d[:, 0], d[:, 1]); hit = np.nonzero(dist < R + pegs[:, 2])[0]
            for h in hit:
                n = d[h] / max(dist[h], 1e-6); p[:] = pegs[h, :2] + n * (R + pegs[h, 2]); vn = v @ n
                if vn < 0:
                    v -= (1 + pegs[h, 3]) * vn * n
                    if abs(n[0]) < .15: v[0] += rng.uniform(-60, 60)          # never balance on top of a peg
                    if -vn > 90 and t - last_snd[i] > .05:
                        ev.append(("bump" if pegs[h, 2] > 20 else "peg", t, i, p[0], -vn)); last_snd[i] = t
            ab = B - A; ap = p - A; u = np.clip((ap * ab).sum(1) / (ab * ab).sum(1), 0, 1)
            C = A + ab * u[:, None]; dc = p - C; dd = np.hypot(dc[:, 0], dc[:, 1])
            for h in np.nonzero(dd < R)[0]:
                n = dc[h] / max(dd[h], 1e-6); p[:] = C[h] + n * R; vn = v @ n
                if vn < 0:
                    v -= 1.25 * vn * n; tng = v - (v @ n) * n; v -= tng * .004
                    if -vn > 160 and t - last_snd[i] > .08: ev.append(("ramp", t, i, p[0], -vn)); last_snd[i] = t
            if p[1] > FINISH_Y:
                done[i] = t; ev.append(("finish", t, i, p[0], int((done >= 0).sum())))
        idx = np.nonzero(done < 0)[0]                                       # ball-ball
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                i, j = idx[a], idx[b]; d = P[j] - P[i]; dist = math.hypot(*d)
                if 0 < dist < 2 * R:
                    n = d / dist; o = 2 * R - dist; P[i] -= n * o / 2; P[j] += n * o / 2
                    rel = (V[j] - V[i]) @ n
                    if rel < 0: V[i] += .9 * rel * n; V[j] -= .9 * rel * n
        for i in idx:                                                       # anti-jam kick
            still[i] = still[i] + dt if math.hypot(*V[i]) < 25 else 0
            if still[i] > .8: V[i] += (rng.uniform(-220, 220), -160); still[i] = 0
        if (done >= 0).sum() >= 3 and t > done[done >= 0].max() + .9:
            frames.append(dict(t=t, P=P.copy(), done=done.copy())); return dict(frames=frames, ev=ev, done=done, T=t, pegs=pegs, segs=segs)
    return None

def pick(seed0, tries=30, log=print):
    best = None
    for seed in range(seed0, seed0 + tries):
        sim = simulate(seed, N)
        if not sim: continue
        d = sim["done"]; fin = np.sort(d[d >= 0]); t1 = fin[0]
        lead = []
        for f in sim["frames"][::15]:
            if f["t"] < T_GATE + 1: continue
            act = f["done"] < 0
            if act.sum() == N: lead.append(int(np.argmax(f["P"][:, 1])))
        changes = sum(1 for a, b in zip(lead, lead[1:]) if a != b)
        gap = fin[1] - fin[0]
        score = -abs(t1 - 17) / 4 + min(changes, 8) * .35 - gap * 1.5
        if 12 <= t1 <= 22 and gap < 1.0 and (best is None or score > best[0]): best = (score, seed, sim, changes, gap)
    assert best, "no good seed"; log(f"[flag_drop] seed {best[1]}: winner at {np.sort(best[2]['done'][best[2]['done']>=0])[0]:.1f}s, lead changes {best[3]}, gap {best[4]:.2f}s")
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
    cv2.circle(a, (r, r), r - 2, (255, 255, 255, 255), 3, cv2.LINE_AA)
    hl = np.zeros((2 * r, 2 * r), np.float32); cv2.ellipse(hl, (int(r * .7), int(r * .55)), (int(r * .42), int(r * .25)), -30, 0, 360, 1, -1)
    hl = cv2.GaussianBlur(hl, (0, 0), r * .12) * .4
    a[..., :3] = np.clip(a[..., :3] + hl[..., None] * 255 * (a[..., 3:4] > 0), 0, 255).astype(np.uint8)
    _ec[(flag, r)] = a; return a

def draw_course(pegs, segs):
    y = np.linspace(0, 1, CH, dtype=np.float32)[:, None, None]
    bg = np.array((10, 12, 30), np.float32) * (1 - y) + np.array((30, 8, 40), np.float32) * y
    bg = np.broadcast_to(bg, (CH, W, 3)).copy()
    xx = np.linspace(-1, 1, W, dtype=np.float32)[None, :, None]; bg *= (1 - .35 * xx ** 2)
    bg = np.clip(bg, 0, 255).astype(np.uint8)
    for yy in range(0, CH, 96): cv2.line(bg, (0, yy), (W, yy), (24, 22, 48), 1)              # faint grid
    glow = np.zeros((CH // 2, W // 2, 3), np.uint8)
    for (x, y_, r, e) in pegs:
        col = (255, 120, 220) if r > 20 else (120, 220, 255)
        cv2.circle(glow, (int(x / 2), int(y_ / 2)), int(r / 2) + 3, col, -1, cv2.LINE_AA)
    for (a, b) in segs: cv2.line(glow, (int(a[0] / 2), int(a[1] / 2)), (int(b[0] / 2), int(b[1] / 2)), (255, 200, 90), 6, cv2.LINE_AA)
    g = cv2.resize(cv2.GaussianBlur(glow, (0, 0), 7), (W, CH)); cv2.addWeighted(bg, 1, g, 1.1, 0, bg)
    for (x, y_, r, e) in pegs:
        if r > 20: cv2.circle(bg, (int(x), int(y_)), int(r), (255, 150, 230), 5, cv2.LINE_AA); cv2.circle(bg, (int(x), int(y_)), int(r * .45), (255, 210, 245), -1, cv2.LINE_AA)
        else: cv2.circle(bg, (int(x), int(y_)), int(r), (210, 245, 255), -1, cv2.LINE_AA)
    for (a, b) in segs: cv2.line(bg, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), (255, 225, 150), 9, cv2.LINE_AA)
    cv2.rectangle(bg, (0, 0), (WL, CH), (40, 30, 70), -1); cv2.rectangle(bg, (WR, 0), (W, CH), (40, 30, 70), -1)
    for i, x in enumerate(range(WL, WR, 34)):                                                  # checkered finish
        for j in range(2):
            c = (245, 245, 245) if (i + j) % 2 == 0 else (20, 20, 20)
            cv2.rectangle(bg, (x, FINISH_Y + j * 34 - 34), (min(x + 34, WR), FINISH_Y + j * 34), c, -1)
    cv2.line(bg, (WL, GATE_Y), (WR, GATE_Y), (90, 255, 160), 6, cv2.LINE_AA)
    return bg

def build(out_mp4, seed=1, race_no=1, log=print, stills=None):
    rng = np.random.default_rng(seed * 7 + 3); sel = rng.choice(len(POOL), N, replace=False)
    names = [POOL[k][0] for k in sel]; flags = [POOL[k][1] for k in sel]
    seed, sim = pick(seed, log=log); fr = sim["frames"]; done = sim["done"]
    order = list(np.argsort(np.where(done >= 0, done, 1e9))); win = order[0]; t1 = done[win]
    S, s0, s1 = .33, t1 - .5, t1 + .25                                          # slow-mo photo finish
    v1 = s0 + (s1 - s0) / S
    def sim_t(v): return v if v < s0 else s0 + (v - s0) * S if v < v1 else s1 + (v - v1)
    def vid_t(t): return t if t < s0 else s0 + (t - s0) / S if t < s1 else v1 + (t - s1)
    v_end = vid_t(sim["T"]); CARD = 3.8; total = v_end + CARD; n = int(round(total * FPS)); LOOP = .35
    log(f"[flag_drop] video {total:.1f}s, winner {names[win]}")
    bg = draw_course(sim["pegs"], sim["segs"]); balls = [flag_ball(f, R) for f in flags]; minis = [flag_ball(f, 30) for f in flags]
    def state(t):
        f = t * FPS; i0 = min(len(fr) - 2, int(f)); w = min(1.0, f - i0); A, B = fr[i0], fr[i0 + 1]
        return A["P"] * (1 - w) + B["P"] * w, A["done"]
    # camera: follow the leader (lowest unfinished ball), critically damped
    cams = []; c = 0.0; cv_ = 0.0
    for i in range(n):
        v = min(i / FPS, v_end); P, d = state(sim_t(v)); act = d < 0
        target = (P[act, 1].max() if act.any() else FINISH_Y) - 0.60 * H if v > T_GATE else 0.0
        target = float(np.clip(target, 0, CH - H)); k_ = 4.0
        acc = k_ * k_ * (target - c) - 2 * k_ * cv_; cv_ += acc / FPS; c += cv_ / FPS; c = float(np.clip(c, 0, CH - H)); cams.append(c)
    slot_x = np.linspace(W / 2 - 3.5 * 104, W / 2 + 3.5 * 104, N); cur_x = slot_x.astype(float).copy(); prev = [list(range(N))]
    band = np.ones((H, 1, 1), np.float32); band[:470] = .1; band[470:540] = np.linspace(.1, 1, 70)[:, None, None]
    tag = E.text_sprite(f"FLAG DROP  ·  RACE #{race_no}", 30, (120, 230, 255), "bold", spacing=5)
    live = E.text_sprite("LIVE ORDER", 20, (200, 200, 220), "bold", spacing=3)
    hooks = [(0, T_GATE, "8 FLAGS · 1 DROP · FIRST TO THE BOTTOM WINS"), (T_GATE, 4.2, "PICK YOUR FLAG BEFORE THE GATE OPENS")]
    def ranks(P, d):
        o = list(prev[0]); key = np.where(d >= 0, -1e6 + d, -P[:, 1])
        for _ in range(N):
            sw = False
            for q in range(N - 1):
                a, b = o[q], o[q + 1]
                if key[b] < key[a] - (0 if d[b] >= 0 else 35): o[q], o[q + 1] = b, a; sw = True
            if not sw: break
        prev[0] = o; return o
    def draw(i, final=True):
        v = i / FPS; t = sim_t(min(v, v_end)); P, d = state(t); cam = cams[min(i, len(cams) - 1)]; ci = int(cam)
        f = bg[ci:ci + H].copy()
        if v < T_GATE:                                                           # gate countdown
            cv2.line(f, (WL, GATE_Y - ci), (WR, GATE_Y - ci), (90, 255, 160), 10, cv2.LINE_AA)
        for k in range(N):
            if d[k] >= 0 and t - d[k] > .6: continue
            x, y = P[k]; y -= cam
            if -R < y < H + R: E.blit(f, balls[k], x, y)
        rk = ranks(P, d) if final else prev[0]                                    # live order strip
        f[:] = (f * band).astype(np.uint8); E.blit(f, tag, W / 2, 268); E.blit(f, live, W / 2, 322)
        for pos in range(N): E.blit(f, E.text_sprite(str(pos + 1), 20, (255, 225, 120) if pos < 3 else (170, 170, 195), "bold"), slot_x[pos], 440)
        for pos, k in enumerate(rk):
            if final: cur_x[k] += (slot_x[pos] - cur_x[k]) * .22
            E.blit(f, minis[k], cur_x[k], 385, scale=1.2 if pos == 0 else 1.0)
        for (t0, t1_, txt) in hooks:
            if t0 <= v < t1_: E.pill(f, 60, 1548, W - 60, 1612, (0, 0, 0), .55); E.blit(f, E.text_sprite(txt, 32, (255, 230, 140), "bold", stroke=4, stroke_color=(0, 0, 0)), W / 2, 1580, alpha=E.smooth((v - t0) / .25))
        if v < T_GATE:
            cnt = ["3", "2", "1"][min(2, int(v / (T_GATE / 3)))]; u = (v % (T_GATE / 3)) / (T_GATE / 3)
            E.blit(f, E.text_sprite(cnt, 150, (255, 255, 255), "black", stroke=8, stroke_color=(0, 0, 0)), W / 2, 960, alpha=1 - u * .6, scale=E.out_back(u / .35))
        elif v < T_GATE + .6: E.blit(f, E.text_sprite("GO!", 150, (90, 255, 160), "black", stroke=8, stroke_color=(0, 0, 0)), W / 2, 960, alpha=1 - E.smooth((v - T_GATE) / .6))
        elif v >= 4.2 and v < s0:
            E.pill(f, 260, 1548, W - 260, 1612, (0, 0, 0), .55); E.blit(f, E.text_sprite(f"LEADER: {names[rk[0]]}", 34, (255, 255, 255), "bold", stroke=4, stroke_color=(0, 0, 0)), W / 2, 1580)
        if s0 <= v < v1: E.blit(f, E.text_sprite("PHOTO FINISH", 52, (255, 90, 120), "black", stroke=6, stroke_color=(0, 0, 0), spacing=4), W / 2, 580, alpha=.6 + .4 * math.sin(v * 12) ** 2)
        for e in sim["ev"]:                                                      # place pops at the line
            if e[0] == "finish":
                age = v - vid_t(e[1])
                if 0 <= age < 1.2 and e[4] <= 3:
                    txt = ["1ST", "2ND", "3RD"][e[4] - 1]; col = [(255, 215, 60), (220, 225, 235), (230, 150, 80)][e[4] - 1]
                    E.blit(f, E.text_sprite(f"{txt}  {names[e[2]]}", 54, col, "black", stroke=6, stroke_color=(0, 0, 0)), W / 2, FINISH_Y - cam - 120 - 60 * age,
                           alpha=1 - E.smooth((age - .9) / .3), scale=E.out_back(age / .25))
        if v >= v_end:                                                           # podium card
            u = v - v_end; a_ = E.smooth(u / .3)
            f[:] = cv2.convertScaleAbs(f, alpha=1 - .8 * a_)
            E.blit(f, E.text_sprite(f"{names[win]} WINS THE DROP", 70 if len(names[win]) < 8 else 58, (255, 255, 255), "black", stroke=6, stroke_color=(0, 0, 0)), W / 2, 700, alpha=a_, scale=E.out_back(u / .4))
            cols = [(255, 205, 60), (205, 212, 225), (215, 140, 75)]
            for pl, (cx, top, sc) in enumerate([(540, 1000, 2.3), (275, 1070, 1.7), (805, 1110, 1.6)]):
                k = order[pl]; g_ = E.smooth((u - .25 - .15 * pl) / .35); y_top = 1200 - (1200 - top) * g_
                if g_ > .01:
                    cv2.rectangle(f, (cx - 120, int(y_top)), (cx + 120, 1200), E.mulc(cols[pl], .55), -1, cv2.LINE_AA)
                    cv2.rectangle(f, (cx - 120, int(y_top)), (cx + 120, int(y_top) + 10), cols[pl], -1, cv2.LINE_AA)
                    E.blit(f, E.text_sprite(str(pl + 1), 64, (255, 255, 255), "black", stroke=4, stroke_color=(0, 0, 0)), cx, (y_top + 1200) / 2 + 4, alpha=g_)
                    E.blit(f, minis[k], cx, y_top - 30 * sc - 8, scale=sc * E.out_back((u - .45 - .15 * pl) / .35))
                E.blit(f, E.text_sprite(names[k], 30, cols[pl], "bold", stroke=3, stroke_color=(0, 0, 0)), cx, 1240, alpha=E.smooth((u - .6 - .15 * pl) / .3))
            E.blit(f, E.text_sprite("WHICH FLAG DID YOU PICK?", 40, (190, 230, 255), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1360, alpha=E.smooth((u - 1.1) / .3))
            E.blit(f, E.text_sprite("COMMENT IT BELOW", 32, (255, 230, 140), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1420, alpha=E.smooth((u - 1.4) / .3))
        if final and v > total - LOOP:
            bb = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - bb, draw(0, False), bb, 0)
        return f
    # ---- audio: glassy marble plinks over a light pulse, riser into the photo finish
    mix = E.Mix(total); hz = lambda m: float(E.midi_hz(m))
    for j in range(3): mix.add(j * T_GATE / 3, E.tick(hz(84), .09), .6)
    mix.add(T_GATE, E.chord([72, 76, 79], .8, E.bell), .5); mix.add(T_GATE, E.whoosh(.4), .5)
    beat = 60 / 124; tb = T_GATE; k = 0
    while tb < s0:
        mix.add(tb, E.thump(.2, 150, 48), .35); mix.add(tb + beat / 2, E.tick(6200, .03), .12)
        tb += beat; k += 1
    per_sec = {}
    for e in sim["ev"]:
        vt = vid_t(e[1]); sec = int(vt * 4)
        if vt > v_end or per_sec.get(sec, 0) > 6: continue
        per_sec[sec] = per_sec.get(sec, 0) + 1; pan = (e[3] - W / 2) / (W / 2) * .6
        if e[0] == "peg": mix.add(vt, E.kalimba(hz(E.penta(int(e[3] / W * 10), 72)), .35), min(.35, .1 + e[4] / 2500), pan)
        elif e[0] == "bump": mix.add(vt, E.bell(hz(E.penta(int(e[3] / W * 8) + 2, 60)), .6), .4, pan)
        elif e[0] == "ramp": mix.add(vt, E.thump(.15, 220, 90), .25, pan)
        elif e[0] == "finish" and e[4] <= 3: mix.add(vt, E.chord([[84, 88, 91], [79, 83, 86], [76, 79, 83]][e[4] - 1], 1.4, E.bell), .6)
    mix.add(max(0, s0 - 2.0), E.riser(2.0 + (v1 - s0) * .5, 220, 2600), .35)
    for j, m in enumerate([72, 76, 79, 84]): mix.add(v_end + .2 + j * .12, E.kalimba(hz(m), 1.2), .5)
    mix.add(v_end + .7, E.chord([60, 64, 67, 72], 2.6, E.bell), .5)
    wav = out_mp4[:-4] + ".wav"; mix.write(wav, peak=.8)
    if stills:
        for t_ in stills: E.save_png(out_mp4[:-4] + f"_still_{t_:05.2f}.png", draw(min(n - 1, int(t_ * FPS)), False))
        return dict(total=total, v_end=v_end, s0=s0, v1=v1)
    E.render(out_mp4, wav, n, draw); os.remove(wav)
    title = f"8 Flags Drop, Only 1 Wins | Flag Drop Race #{race_no}"
    desc = (f"8 flag marbles drop through pegs, ramps and bumpers. First to the bottom wins. Today: {names[win]} takes it, "
            f"{names[order[1]]} 2nd, {names[order[2]]} 3rd. Pure physics and chance.\n\nWhich flag did you pick? 👇\n\n"
            "#shorts #marblerace #flags #satisfying #physics #simulation")
    return dict(duration=total, title=title, description=desc, tags=["marble race", "flags", "countries", "physics", "satisfying", "simulation"],
                winner=names[win], podium=[names[k] for k in order[:3]], countries=names, seed=seed, thumb_ms=int(T_GATE * 1000 + 500))

if __name__ == "__main__":                     # python3 -I lab/styles/flag_drop.py <out.mp4> <seed> [episode]
    import json
    out = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1; ep = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    res = build(out, seed, race_no=ep, log=lambda *a: print(*a, file=sys.stderr)); print("RESULT=" + json.dumps(res, default=float))
