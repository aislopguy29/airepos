"""LAB STYLE stack_race: 4 food towers (pancakes, burgers, donuts, sushi) race to stack 20 layers up to a finish line.
A crane over each lane drops one layer at a time; a layer that lands off-centre can tip everything above the layer under it
(simple centre-of-mass rule), so leaning towers collapse in chunks and the lead flips. Side-by-side lanes on a diner counter,
live layer counters, TIMBER callouts, slow-mo final layer, ranked result card. Pure chance + simple statics: no data."""
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import engine as E
from engine import W, H, FPS

EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
FOODS = [("PANCAKES", "\U0001F95E", (255, 196, 80)), ("BURGERS", "\U0001F354", (255, 128, 72)),
         ("DONUTS", "\U0001F369", (255, 112, 196)), ("SUSHI", "\U0001F363", (96, 214, 206))]
N, GOAL = 4, 20
BW, BH = 144, 48; HALF = BW / 2
GROUND = 1500; FINISH = GROUND - GOAL * BH            # 540: top of layer 20
LANES = [160, 413, 667, 920]
RAIL_Y, HOOK_Y, HANG_Y = 345, 398, 430                # rail, claw tip, centre of a hanging layer
T0, G, G_FALL = 1.8, 6500.0, 3200.0                   # race start, drop gravity, tumble gravity
POST = 1.1                                            # sim seconds shown after the winning layer lands
AIM_CLAMP = 110

# ---------------------------------------------------------------- simulation
def simulate(seed):
    """Each lane is independent: release a layer, it falls to the top, then the centre-of-mass check runs.
    Returns per-lane drop lists; every drop is one layer's whole life (hook -> fall -> stacked -> maybe tumble)."""
    rng = np.random.default_rng(seed)
    spread = rng.uniform(15, 23, N); handle = rng.uniform(.20, .34, N)
    lanes = []
    for i in range(N):
        c = LANES[i]; t = T0 + rng.uniform(0, .2); xs = []; drops = []; stack = []    # stack = indices of drops in the tower
        while t < 45:
            n = len(xs); top = xs[-1] if xs else c
            sig = spread[i] * (1 + 1.1 * n / GOAL)
            lo = c - (75 if i == 0 else AIM_CLAMP); hi = c + (75 if i == N - 1 else AIM_CLAMP)      # outer lanes stay on screen
            aim = float(np.clip(top + rng.normal(0, sig) - .15 * (top - c), lo, hi))
            D = (GROUND - n * BH) - (HANG_Y + BH / 2); land = t + math.sqrt(2 * D / G)
            d = dict(rel=t, land=land, x=aim, level=n, fall=None, x_prev=(drops[-1]["x"] if drops else c),
                     appear=(drops[-1]["land"] + .06 if drops else 0.0))
            drops.append(d); xs.append(aim); stack.append(len(drops) - 1)
            fell = None
            for j in range(len(xs) - 1):
                com = float(np.mean(xs[j + 1:]))
                if abs(com - xs[j]) > HALF: fell = (j + 1, 1.0 if com > xs[j] else -1.0); break
            if fell:
                j1, dr = fell; chunk = stack[j1:]
                for m, k in enumerate(chunk):                                      # tumble parameters
                    drops[k]["fall"] = dict(t=land + .03 * m, dir=dr, vx=dr * (70 + 22 * m + rng.uniform(-15, 15)),
                                            vy=-rng.uniform(20, 70), w=dr * (1.6 + .35 * m + rng.uniform(-.3, .3)), m=m,
                                            size=len(chunk), base=j1)
                xs = xs[:j1]; stack = stack[:j1]
            d["height_after"] = len(xs); d["collapse"] = len(chunk) if fell else 0
            if len(xs) >= GOAL: d["finish"] = True; break
            t = land + handle[i] * (1 + rng.uniform(-.25, .25)) + (.3 if fell else 0)
        lanes.append(drops)
    fins = [next((d["land"] for d in L if d.get("finish")), 1e9) for L in lanes]
    win = int(np.argmin(fins)); t_win = fins[win]
    if t_win > 40: return None
    for i in range(N):                                                             # cranes stop when someone finishes
        lanes[i] = [d for d in lanes[i] if d["rel"] <= t_win]
    return dict(lanes=lanes, win=win, t_win=t_win, T=t_win + POST, spread=spread, handle=handle)

def height_at(L, t):
    h = 0
    for d in L:
        if d["land"] <= t: h = d["height_after"]
        else: break
    return h

def leaders(sim, t_from, t_to, step=.05):
    """Leader over time: max height, ties keep the current leader (or whoever got there first)."""
    out = []; cur = None; reach = {}
    for t in np.arange(t_from, t_to, step):
        hs = [height_at(L, t) for L in sim["lanes"]]
        for i, h in enumerate(hs):
            if reach.get(i, (None,))[0] != h: reach[i] = (h, t)
        m = max(hs); cands = [i for i in range(N) if hs[i] == m]
        if m == 0: out.append((t, None, hs)); continue
        if cur not in cands: cur = min(cands, key=lambda i: reach[i][1])
        out.append((t, cur, hs))
    return out

def pick(seed0, tries=400, log=print):
    best = None
    for seed in range(seed0, seed0 + tries):
        sim = simulate(seed)
        if not sim: continue
        tw = sim["t_win"]; race = tw - T0; w = sim["win"]
        if not 11.5 <= race <= 17.5: continue
        fin_h = [height_at(L, sim["T"]) for L in sim["lanes"]]
        ru = max(h for i, h in enumerate(fin_h) if i != w)
        if ru < GOAL - 3 or min(fin_h) < 7: continue
        ld = leaders(sim, T0 + 1.0, tw, .1); seq = [c for _, c, _ in ld if c is not None]
        changes = sum(1 for a, b in zip(seq, seq[1:]) if a != b)
        big = [(d["land"], i, d["collapse"], d["level"]) for i, L in enumerate(sim["lanes"]) for d in L if d["collapse"] >= 4 and d["land"] < tw]
        late = any(t > T0 + .55 * race and lvl >= 12 for t, i, k, lvl in big)          # a tall tower loses a chunk late
        behind = max((hs[c] - hs[w] for t, c, hs in ld if t > T0 + .3 * race and c is not None), default=0)
        n_coll = sum(1 for L in sim["lanes"] for d in L if d["collapse"] and d["land"] < tw)
        score = (2.0 * (ru == GOAL - 1) + 1.0 * (ru == GOAL - 2) + .4 * min(changes, 6) + 1.5 * late + 1.2 * (behind >= 3)
                 + .3 * min(len(big), 4) - abs(race - 14.5) / 2 - .15 * max(0, n_coll - 10))
        if changes >= 3 and len(big) >= 2 and (best is None or score > best[0]):
            best = (score, seed, sim, dict(changes=changes, big=len(big), late=late, behind=behind, ru=ru, collapses=n_coll))
    assert best, "no good seed"
    log(f"[stack_race] seed {best[1]}: race {best[2]['t_win'] - T0:.1f}s, {best[3]}")
    return best[1], best[2], best[3]

# ---------------------------------------------------------------- sprites
def _rr(d, box, r, fill, outline=None, width=0):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)

def layer_sprite(kind, variant=0):
    """One food layer, BW x BH RGBA, drawn at 2x and downsampled."""
    S = 2; w, h = BW * S, BH * S; im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    rng = np.random.default_rng(7 + 31 * kind + variant)
    if kind == 0:                                    # pancake: golden slab, darker rim, optional syrup drip
        _rr(d, (2, 8, w - 3, h - 4), 30, (176, 104, 44))
        _rr(d, (2, 4, w - 3, h - 22), 30, (232, 170, 86))
        _rr(d, (16, 8, w - 17, 26), 10, (248, 206, 128))
        for _ in range(9):
            x = rng.uniform(30, w - 30); y = rng.uniform(40, h - 30)
            d.ellipse((x - 3, y - 2, x + 3, y + 2), fill=(196, 128, 60))
        if variant == 2:                             # a syrup drip on every third pancake
            x = 60 + rng.uniform(-10, 120)
            _rr(d, (x, 2, x + 18, 50), 9, (140, 70, 22)); d.ellipse((x - 3, 40, x + 21, 62), fill=(140, 70, 22))
            _rr(d, (x - 24, 0, x + 42, 12), 6, (140, 70, 22))
    elif kind == 1:                                  # burger: bun / lettuce / cheese / patty / bun
        _rr(d, (8, 70, w - 9, h - 2), 14, (196, 120, 50))
        _rr(d, (4, 46, w - 5, 76), 14, (98, 54, 30))
        for _ in range(14):
            x = rng.uniform(20, w - 20); y = rng.uniform(52, 70); d.ellipse((x - 3, y - 2, x + 3, y + 2), fill=(70, 36, 20))
        d.polygon([(10, 44), (w - 10, 44), (w - 30, 52), (w - 70, 64), (w - 110, 52), (150, 60), (110, 50), (60, 62), (30, 50)], fill=(250, 196, 46))
        pts = [(4, 46)] + [(8 + k * 14, 36 + (8 if k % 2 else 0)) for k in range(21)] + [(w - 4, 46)]
        d.polygon(pts + [(w - 4, 48), (4, 48)], fill=(96, 186, 62))
        d.pieslice((6, 0, w - 7, 84), 180, 360, fill=(218, 142, 58)); _rr(d, (6, 30, w - 7, 44), 6, (218, 142, 58))
        d.chord((30, 6, w - 31, 40), 190, 300, fill=(236, 172, 92))
        for _ in range(11):
            x = rng.uniform(40, w - 40); y = rng.uniform(10, 32); d.ellipse((x - 4, y - 2, x + 4, y + 2), fill=(252, 240, 210))
    elif kind == 2:                                  # donut side view: dough + pink icing with drips + sprinkles
        icing = [(255, 132, 196), (255, 120, 186), (250, 150, 205)][variant % 3]
        _rr(d, (4, 10, w - 5, h - 4), 40, (220, 156, 86)); _rr(d, (14, 60, w - 15, h - 8), 30, (196, 128, 62))
        pts = [(4, 40)]
        for k in range(13): x = 12 + k * 22; pts.append((x, 50 + (14 if k % 3 == 1 else 4) + rng.uniform(-3, 3)))
        pts += [(w - 4, 44), (w - 30, 6), (30, 6)]
        d.polygon(pts, fill=icing); _rr(d, (4, 4, w - 5, 48), 26, icing)
        _rr(d, (36, 12, w - 37, 22), 5, tuple(min(255, c + 40) for c in icing))
        cols = [(255, 255, 255), (255, 230, 80), (110, 200, 255), (130, 230, 140), (255, 120, 90)]
        for _ in range(16):
            x = rng.uniform(26, w - 26); y = rng.uniform(16, 44); a = rng.uniform(0, math.pi); dx, dy = 7 * math.cos(a), 7 * math.sin(a)
            d.line((x - dx, y - dy, x + dx, y + dy), fill=cols[int(rng.integers(0, 5))], width=5)
    else:                                            # sushi nigiri: rice base, salmon slice with fat stripes, nori strap
        _rr(d, (14, 40, w - 15, h - 2), 22, (246, 243, 234))
        for _ in range(26):
            x = rng.uniform(24, w - 24); y = rng.uniform(52, h - 12); d.ellipse((x - 5, y - 3, x + 5, y + 3), outline=(214, 210, 198), width=2)
        _rr(d, (2, 4, w - 3, 50), 22, (250, 128, 76))
        for k in range(7):
            x = 20 + k * 40; d.line((x, 8, x + 26, 46), fill=(255, 206, 176), width=7)
        _rr(d, (w // 2 - 18, 0, w // 2 + 18, h - 2), 6, (34, 52, 40))
    a = np.array(im.resize((BW, BH), Image.LANCZOS))
    return a

def emoji_sprite(ch, size):
    f = ImageFont.truetype(EMOJI, 109); im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((80, 80), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox()); s = size / max(im.size)
    return np.array(im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS))

_rot = {}
def rotated(spr, key, ang):
    q = int(round(math.degrees(ang) / 3.0)) * 3
    k = (key, q)
    if k in _rot: return _rot[k]
    hh, ww = spr.shape[:2]; P = int(math.hypot(hh, ww)) + 4
    pad = np.zeros((P, P, 4), np.uint8); y0, x0 = (P - hh) // 2, (P - ww) // 2; pad[y0:y0 + hh, x0:x0 + ww] = spr
    M = cv2.getRotationMatrix2D((P / 2, P / 2), -q, 1.0)
    _rot[k] = cv2.warpAffine(pad, M, (P, P), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return _rot[k]

# ---------------------------------------------------------------- static background
def draw_bg(race_no):
    bg = E.make_bg(top=(12, 30, 54), bottom=(54, 26, 40), glow=(70, 50, 40)).astype(np.float32)
    rng = np.random.default_rng(5); glow = np.zeros((H // 2, W // 2, 3), np.uint8)
    for _ in range(26):                                                       # warm bokeh lights
        x, y, r = rng.uniform(0, W / 2), rng.uniform(80, 760), rng.uniform(8, 26)
        col = [(255, 190, 110), (255, 140, 120), (140, 200, 255)][int(rng.integers(0, 3))]
        cv2.circle(glow, (int(x), int(y)), int(r), tuple(int(c * .5) for c in col), -1, cv2.LINE_AA)
    bg += cv2.resize(cv2.GaussianBlur(glow, (0, 0), 6), (W, H)).astype(np.float32) * .55
    for i, c in enumerate(LANES):                                             # lane panels tinted by food
        col = np.array(FOODS[i][2], np.float32)
        x0, x1 = c - 122, c + 122
        bg[FINISH - 10:GROUND, x0:x1] = bg[FINISH - 10:GROUND, x0:x1] * .9 + col * .045
    bg = np.clip(bg, 0, 255).astype(np.uint8)
    for x in [(LANES[k] + LANES[k + 1]) // 2 for k in range(N - 1)]:         # separators + layer ticks
        for y in range(FINISH, GROUND, 18): cv2.line(bg, (x, y), (x, y + 8), (70, 70, 96), 2, cv2.LINE_AA)
        for k in (5, 10, 15):
            y = GROUND - k * BH; cv2.line(bg, (x - 10, y), (x + 10, y), (120, 120, 150), 2, cv2.LINE_AA)
            E.blit(bg, E.text_sprite(str(k), 20, (150, 150, 180), "bold"), x, y - 16, alpha=.85)
    for k, x in enumerate(range(30, 1050, 24)):                              # checkered finish band
        for j in range(2):
            col = (245, 245, 245) if (k + j) % 2 == 0 else (24, 24, 30)
            cv2.rectangle(bg, (x, FINISH - 24 + j * 12), (min(x + 24, 1050) - 1, FINISH - 13 + j * 12), col, -1)
    E.blit(bg, E.text_sprite(f"FINISH  ·  {GOAL} LAYERS", 24, (255, 236, 160), "bold", stroke=3, stroke_color=(0, 0, 0), spacing=3), W / 2, FINISH - 50)
    cv2.rectangle(bg, (0, GROUND), (W, H), (92, 52, 34), -1)                 # diner counter
    cv2.rectangle(bg, (0, GROUND), (W, GROUND + 12), (150, 92, 56), -1)
    for k, x in enumerate(range(0, W, 40)):                                   # checkered counter trim
        cv2.rectangle(bg, (x, GROUND + 12), (x + 39, GROUND + 26), (210, 48, 52) if k % 2 == 0 else (240, 236, 228), -1)
    sh = np.ones((H - GROUND - 26, 1, 1), np.float32) * np.linspace(1, .55, H - GROUND - 26)[:, None, None]
    bg[GROUND + 26:] = (bg[GROUND + 26:] * sh).astype(np.uint8)
    for c in LANES:                                                           # plates
        cv2.ellipse(bg, (c, GROUND + 2), (104, 13), 0, 0, 360, (200, 204, 214), -1, cv2.LINE_AA)
        cv2.ellipse(bg, (c, GROUND - 1), (96, 10), 0, 0, 360, (246, 248, 252), -1, cv2.LINE_AA)
    cv2.rectangle(bg, (34, RAIL_Y - 7), (1046, RAIL_Y + 7), (150, 158, 176), -1, cv2.LINE_AA)    # crane rail
    cv2.line(bg, (34, RAIL_Y - 7), (1046, RAIL_Y - 7), (210, 216, 230), 2, cv2.LINE_AA)
    for x in range(60, 1040, 70): cv2.circle(bg, (x, RAIL_Y), 3, (96, 100, 120), -1, cv2.LINE_AA)
    E.blit(bg, E.text_sprite(f"STACK RACE  ·  #{race_no}", 30, (255, 214, 140), "bold", spacing=5), W / 2, 272)
    return bg

# ---------------------------------------------------------------- build
def build(out_mp4, seed=1, race_no=1, log=print, stills=None):
    seed, sim, info = pick(seed, log=log)
    lanes, win, t_win, T_end = sim["lanes"], sim["win"], sim["t_win"], sim["T"]
    names = [f[0] for f in FOODS]; accents = [f[2] for f in FOODS]
    wd = lanes[win][-1]                                                      # the winning layer
    S, s0, s1 = .33, wd["rel"] - .22, wd["land"] + .22                       # slow-mo around the final layer
    v1 = s0 + (s1 - s0) / S
    def sim_t(v): return v if v < s0 else s0 + (v - s0) * S if v < v1 else s1 + (v - v1)
    def vid_t(t): return t if t < s0 else s0 + (t - s0) / S if t < s1 else v1 + (t - s1)
    v_end = vid_t(T_end); CARD = 4.0; total = v_end + CARD; n = int(round(total * FPS)); LOOP = .35
    fin_h = [height_at(L, T_end) for L in lanes]
    order = sorted(range(N), key=lambda i: (-fin_h[i], i != win))
    log(f"[stack_race] video {total:.1f}s, winner {names[win]}, final heights {fin_h}")
    bg = draw_bg(race_no)
    sprites = [[layer_sprite(k, v) for v in range(3)] for k in range(N)]
    def spr_of(i, d): return sprites[i][(d["level"] * 7 + int(d["x"])) % 3 if i in (0, 2) else 0]
    emo = [emoji_sprite(f[1], 46) for f in FOODS]; emo_big = [emoji_sprite(f[1], 150) for f in FOODS]
    emo_mid = [emoji_sprite(f[1], 64) for f in FOODS]
    led = leaders(sim, 0, T_end + .01, 1 / FPS)
    def leader_at(t): return led[min(len(led) - 1, max(0, int(round(t * FPS))))][1]
    # events for callouts and audio
    colls = [(d["land"], i, d["collapse"], d["level"]) for i, L in enumerate(lanes) for d in L if d["collapse"]]
    big_t = [t for t, i, k, l in colls if k >= 4]
    rngc = np.random.default_rng(seed + 5)
    conf = [(rngc.uniform(-420, 420), rngc.uniform(-1100, -500), rngc.uniform(0, 2 * math.pi), rngc.uniform(-9, 9),
             [(255, 214, 80), (255, 112, 196), (96, 214, 206), (255, 255, 255), (255, 128, 72)][int(rngc.integers(0, 5))]) for _ in range(70)]

    def lane_state(i, t):
        """Draw list for lane i at sim time t: stacked layers with wobble, the falling layer, the hanging layer, hook x."""
        L = lanes[i]; c = LANES[i]; stacked, flying, tumbling = [], [], []
        hook_x = c; hang = None; last_land = -9; cur_h = 0
        for d in L:
            if d["land"] <= t: last_land = d["land"]; cur_h = d["height_after"]
        for k, d in enumerate(L):
            if t < d["appear"]: continue
            if t < d["rel"]:                                                    # on the hook, crane moving to aim
                u = E.smooth((t - d["appear"]) / max(.05, d["rel"] - d["appear"] - .05))
                hook_x = d["x_prev"] + (d["x"] - d["x_prev"]) * u
                hang = (hook_x, HANG_Y - 30 * (1 - E.smooth((t - d["appear"]) / .14)), E.smooth((t - d["appear"]) / .04), d)
            elif t < d["land"]:
                dt = t - d["rel"]; flying.append((d["x"], HANG_Y + .5 * G * dt * dt, d)); hook_x = d["x"]
            elif d["fall"] is not None and t >= d["fall"]["t"]:
                F = d["fall"]; dt = t - F["t"]; y0 = GROUND - (d["level"] + .5) * BH
                y = y0 + F["vy"] * dt + .5 * G_FALL * dt * dt
                if y < GROUND + 80: tumbling.append((d["x"] + F["vx"] * dt, y, F["w"] * dt, d))
                hook_x = d["x"]
            else:
                stacked.append(d); hook_x = d["x"]
        # landing jiggle
        dt = t - last_land; amp = 5.0 * math.exp(-6 * dt) * math.sin(2 * math.pi * 4.5 * dt) if 0 <= dt < 1 else 0.0
        return stacked, flying, tumbling, hang, hook_x, amp, cur_h

    hook_txt = [E.text_sprite("FIRST STACK TO", 82, (255, 255, 255), "black", stroke=7, stroke_color=(0, 0, 0)),
                E.text_sprite("THE LINE WINS", 82, (255, 255, 255), "black", stroke=7, stroke_color=(0, 0, 0))]
    hook_sub = E.text_sprite(f"4 FOODS  ·  {GOAL} LAYERS  ·  1 WOBBLE CAN END IT", 32, (255, 214, 140), "bold", stroke=4, stroke_color=(0, 0, 0))
    pick_txt = E.text_sprite("PICK YOUR STACK", 60, (255, 236, 160), "black", stroke=6, stroke_color=(0, 0, 0))
    name_spr = [E.text_sprite(nm, 26, accents[i], "bold", stroke=3, stroke_color=(0, 0, 0)) for i, nm in enumerate(names)]
    shake_ev = [(t, k) for t, i, k, l in colls if k >= 4]

    def draw(i_f, final=True):
        v = i_f / FPS; t = sim_t(min(v, v_end)); f = bg.copy()
        sx = sy = 0
        for (te, k) in shake_ev:
            age = v - vid_t(te)
            if 0 <= age < .3: a_ = 9 * (1 - age / .3); sx += int(a_ * math.sin(age * 90)); sy += int(a_ * .6 * math.cos(age * 77))
        states = [lane_state(i, t) for i in range(N)]
        lead = leader_at(t) if t >= T0 else None
        if lead is not None and v < v_end:                                       # leader lane glow
            c = LANES[lead]; ov = f[FINISH - 10:GROUND, c - 122:c + 122].astype(np.float32)
            f[FINISH - 10:GROUND, c - 122:c + 122] = np.clip(ov * 1.0 + np.array(accents[lead], np.float32) * .07, 0, 255).astype(np.uint8)
        tumb_all = []
        for i in range(N):
            stacked, flying, tumbling, hang, hook_x, amp, cur_h = states[i]; c = LANES[i]
            top_n = max(1, len(stacked))
            for d in stacked:
                y = GROUND - (d["level"] + .5) * BH; x = d["x"] + amp * (d["level"] + 1) / top_n
                E.blit(f, spr_of(i, d), x + sx, y + sy)
            if i == win and t >= wd["land"] and stacked:                          # gold edge on the winning tower
                a_ = .5 + .5 * math.sin(v * 9)
                for d in stacked[-1:]:
                    y = GROUND - (d["level"] + .5) * BH
                    cv2.rectangle(f, (int(d["x"] - HALF - 4 + sx), int(y - BH / 2 - 4 + sy)), (int(d["x"] + HALF + 4 + sx), int(y + BH / 2 + 2 + sy)),
                                  (255, 214, 80), 3, cv2.LINE_AA)
            for (x, y, d) in flying: E.blit(f, spr_of(i, d), x + sx, y + sy)
            # crane: trolley, cable, claw, hanging layer
            hx = hook_x
            cv2.line(f, (int(hx) + sx, RAIL_Y + 8 + sy), (int(hx) + sx, HOOK_Y - 6 + sy), (190, 196, 210), 3, cv2.LINE_AA)
            E.pill(f, hx - 30 + sx, RAIL_Y - 13 + sy, hx + 30 + sx, RAIL_Y + 13 + sy, E.mulc(accents[i], .75), .95)
            opened = hang is None
            for s_ in (-1, 1):
                ang = (.85 if opened else .35) * s_
                x2 = hx + s_ * 22 + sx; y2 = HOOK_Y + sy
                cv2.line(f, (int(hx) + sx, HOOK_Y - 6 + sy), (int(x2), int(y2)), (210, 216, 230), 4, cv2.LINE_AA)
                cv2.line(f, (int(x2), int(y2)), (int(x2 + s_ * (10 if opened else -4)), int(y2 + 10)), (210, 216, 230), 4, cv2.LINE_AA)
            if hang is not None and v < v_end:
                x, y, a_, d = hang; E.blit(f, spr_of(i, d), x + sx, y + sy, alpha=a_)
            tumb_all += [(x, y, ang, i, d) for (x, y, ang, d) in tumbling]
        for (x, y, ang, i, d) in tumb_all:                                       # tumbling layers over everything
            r = rotated(spr_of(i, d), (i, (d["level"] * 7 + int(d["x"])) % 3 if i in (0, 2) else 0), ang)
            E.blit(f, r, x + sx, y + sy)
        # counter cover (layers fall behind it) + labels
        f[GROUND + 26:] = bg[GROUND + 26:]
        for i in range(N):
            c = LANES[i]; h_now = states[i][6] if v < v_end else fin_h[i]
            hl = (lead == i)
            if hl: E.pill(f, c - 120, 1518, c + 120, 1622, E.mulc(accents[i], .45), .75)
            E.blit(f, emo[i], c - 92, 1546); E.blit(f, name_spr[i], c - 64, 1546, anchor="l")
            last = max([d["land"] for d in lanes[i] if d["land"] <= t] or [-9]); pop = 1 + .18 * max(0, 1 - (t - last) / .18)
            col = (255, 255, 255) if h_now < GOAL else (255, 214, 80)
            E.blit(f, E.text_sprite(f"{h_now}/{GOAL}", 46, col, "black", stroke=4, stroke_color=(0, 0, 0)), c, 1594, scale=pop)
        # collapse callouts
        for (te, i, k, lvl) in colls:
            age = v - vid_t(te)
            if not 0 <= age < 1.1: continue
            base = lvl + 1 - k                                                   # callout sits at the break point
            yb = min(1330, max(FINISH + 110, GROUND - base * BH - 50)); al = 1 - E.smooth((age - .8) / .3)
            if k >= 4:
                E.blit(f, E.text_sprite("TIMBER!", 66, (255, 96, 70), "black", stroke=7, stroke_color=(0, 0, 0)), min(max(LANES[i], 200), W - 200), yb - 50 * age, alpha=al, scale=E.out_back(age / .22))
                E.blit(f, E.text_sprite(f"-{k}", 56, (255, 255, 255), "black", stroke=6, stroke_color=(160, 20, 20)), LANES[i], yb + 66 - 50 * age, alpha=al)
            else:
                E.blit(f, E.text_sprite(f"-{k}", 46 if k > 1 else 38, (255, 150, 130), "black", stroke=5, stroke_color=(0, 0, 0)), LANES[i], yb - 50 * age, alpha=al, scale=E.out_back(age / .2))
        # hook / pick / go
        if v < T0 + .2:
            a_ = 1 - E.smooth((v - T0 + .1) / .3)
            E.pill(f, 70, 700, W - 70, 1030, (0, 0, 0), .5 * a_)
            E.blit(f, hook_sub, W / 2, 748, alpha=a_ * E.smooth(v / .15))
            E.blit(f, hook_txt[0], W / 2, 850, alpha=a_, scale=E.out_back(min(1, v / .3)))
            E.blit(f, hook_txt[1], W / 2, 950, alpha=a_, scale=E.out_back(min(1, (v - .08) / .3)))
        if .9 <= v < T0 + .9:
            a_ = E.smooth((v - .9) / .2) * (1 - E.smooth((v - T0 - .6) / .3))
            E.blit(f, pick_txt, W / 2, 1180, alpha=a_)
            for i in range(N): E.arrow_down(f, LANES[i], 1290 + 14 * math.sin(v * 10 + i), 30, accents[i], alpha=a_)
        if T0 <= v < T0 + .6:
            E.blit(f, E.text_sprite("GO!", 150, (120, 255, 170), "black", stroke=8, stroke_color=(0, 0, 0)), W / 2, 960, alpha=1 - E.smooth((v - T0) / .6), scale=E.out_back((v - T0) / .25))
        # bottom info pill
        if T0 + .9 <= v < v_end:
            hs = [states[i][6] for i in range(N)]; togo = GOAL - max(hs)
            if s0 <= v < v1 and t < wd["land"]:
                txt, col = f"FINAL LAYER: {names[win]}", (255, 110, 110)
            elif t >= wd["land"]:
                txt, col = f"{names[win]} HIT THE LINE", (255, 214, 80)
            elif lead is not None and togo <= 3:
                txt, col = f"{names[lead]} LEADS  ·  {togo} TO GO", (255, 180, 120)
            elif lead is not None:
                txt, col = f"LEADER: {names[lead]}", (255, 255, 255)
            else: txt = None
            if txt:
                big_ = s0 <= v < v1 and t < wd["land"]
                spr = E.text_sprite(txt, 36 if big_ else 32, col, "black" if big_ else "bold", stroke=4, stroke_color=(0, 0, 0)); wpx = spr.shape[1] + 70
                E.pill(f, W / 2 - wpx / 2, 1624, W / 2 + wpx / 2, 1674, (0, 0, 0), .62); E.blit(f, spr, W / 2, 1649)
        if t >= wd["land"] and v < v_end + .3:                                   # finish burst + confetti
            age = v - vid_t(wd["land"]); c = LANES[win]; y0 = FINISH
            for (vx, vy, ph, w_, col) in conf:
                x = c + vx * age; y = y0 + vy * age + 900 * age * age
                if 240 < y < GROUND: cv2.rectangle(f, (int(x - 6), int(y - 3)), (int(x + 6), int(y + 3)), col, -1)
            E.blit(f, E.text_sprite("FINISH!", 96, (255, 214, 80), "black", stroke=8, stroke_color=(0, 0, 0)), W / 2, 470, alpha=1 - E.smooth((age - 1.2) / .3), scale=E.out_back(age / .25))
            ru = max(fin_h[i] for i in range(N) if i != win)
            if GOAL - ru == 1 and age > .35:
                E.blit(f, E.text_sprite("BY ONE LAYER!", 50, (255, 255, 255), "black", stroke=6, stroke_color=(0, 0, 0)), W / 2, 1110, alpha=E.smooth((age - .35) / .2) * (1 - E.smooth((age - 1.6) / .3)))
        if v >= v_end:                                                           # result card
            u = v - v_end; a_ = E.smooth(u / .3)
            f[:] = cv2.convertScaleAbs(f, alpha=1 - .82 * a_)
            E.blit(f, emo_big[win], W / 2, 520, alpha=a_, scale=E.out_back(u / .4))
            E.blit(f, E.text_sprite(f"{names[win]} WIN", 92, (255, 214, 80), "black", stroke=7, stroke_color=(0, 0, 0)), W / 2, 690, alpha=a_, scale=E.out_back((u - .1) / .4))
            E.blit(f, E.text_sprite(f"STACK RACE #{race_no}  ·  FINAL HEIGHTS", 28, (200, 210, 230), "bold", spacing=3), W / 2, 790, alpha=E.smooth((u - .3) / .3))
            for r_, k in enumerate(order):
                g_ = E.smooth((u - .45 - .15 * r_) / .3); y = 880 + r_ * 104
                if g_ <= .01: continue
                E.pill(f, 120, y - 42, W - 120, y + 42, E.mulc(accents[k], .35 if r_ else .55), .85 * g_)
                E.blit(f, E.text_sprite(f"{r_ + 1}", 50, (255, 255, 255), "black", stroke=4, stroke_color=(0, 0, 0)), 180, y, alpha=g_)
                E.blit(f, emo_mid[k], 262, y, alpha=g_)
                E.blit(f, E.text_sprite(names[k], 44, accents[k], "black", stroke=4, stroke_color=(0, 0, 0)), 316, y, alpha=g_, anchor="l")
                bw = int(250 * fin_h[k] / GOAL)
                cv2.rectangle(f, (640, y - 10), (640 + 250, y + 10), (40, 40, 56), -1)
                if g_ > .5: cv2.rectangle(f, (640, y - 10), (640 + int(bw * E.smooth((g_ - .5) * 2)), y + 10), accents[k], -1)
                E.blit(f, E.text_sprite(f"{fin_h[k]}", 40, (255, 255, 255), "black", stroke=4, stroke_color=(0, 0, 0)), 930, y, alpha=g_)
            E.blit(f, E.text_sprite("WHICH STACK DID YOU PICK?", 46, (190, 236, 255), "black", stroke=5, stroke_color=(0, 0, 0)), W / 2, 1360, alpha=E.smooth((u - 1.3) / .3))
            E.blit(f, E.text_sprite("REMATCH IDEAS IN THE COMMENTS", 30, (255, 230, 150), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1430, alpha=E.smooth((u - 1.6) / .3))
        if final and v > total - LOOP:
            bb = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - bb, draw(0, False), bb, 0)
        return f

    # ---- audio: jazzy diner swing bed, plate-clink notes that climb with height, tumbling slides, finish bells
    mix = E.Mix(total, mood="jazzy", bpm=116, root=53, scale="dorian"); hz = lambda m: float(E.midi_hz(m))
    def inten(tt): return .35 + .6 * E.clamp((tt - T0) / max(1, s0 - T0))
    mix.bed(T0 - .1, total, gain=.26, seed=seed, intensity=inten, drums_off=[(s0, v1 + .05)])
    mix.add(0, E.whoosh(.4), .45); mix.add(.05, E.chord([65, 69, 72], .9, E.bell), .35)
    for j in range(3): mix.add(.95 + j * .27, E.tick(hz(84 + 2 * j), .08), .35)
    mix.add(T0, E.chord([77, 81, 84], .7, E.bell), .45)
    per = {}
    for i, L in enumerate(lanes):
        pan = (LANES[i] - W / 2) / (W / 2) * .7
        for d in L:
            vt = vid_t(d["land"]); key = int(vt * 10)
            if vt > v_end or per.get(key, 0) >= 2: continue
            per[key] = per.get(key, 0) + 1
            if d["collapse"]:
                k = d["collapse"]; mix.add(vt, E.slide_down(.5 + .08 * k, 560, 150), .32 + .03 * min(k, 6), pan)
                for m in range(min(k, 6)): mix.add(vt + .32 + .07 * m, E.thump(.25, 120, 45), .3, pan)
            else:
                mix.add(vt, E.kalimba(hz(mix.scale_note(d["height_after"] + 2, 1)), .45), .30, pan)
                mix.add(vt, E.tick(2600 + 90 * d["height_after"], .035), .10, pan)
    mix.add(max(0, s0 - 1.6), E.riser(1.6 + (v1 - s0) * .6, 240, 2600, seed=seed), .3)
    vw = vid_t(wd["land"])
    mix.add(vw, E.chord([77, 81, 84, 89], 1.8, E.bell), .62); mix.add(vw, E.thump(.4, 130, 44), .55)
    for j, m in enumerate([65, 69, 72, 77, 81]): mix.add(v_end + .25 + j * .11, E.kalimba(hz(m), 1.0), .42)
    mix.add(v_end + .8, E.chord([53, 65, 69, 72, 76], 2.8, E.epiano), .45)
    wav = out_mp4[:-4] + ".wav"; mix.write(wav, peak=.82)
    if stills:
        for t_ in stills: E.save_png(out_mp4[:-4] + f"_still_{t_:05.2f}.png", draw(min(n - 1, int(t_ * FPS)), False))
        return dict(total=total, v_end=v_end, s0=s0, v1=v1, seed=seed, info=info, fin_h=fin_h, winner=names[win])
    E.render(out_mp4, wav, n, draw); os.remove(wav)
    title = f"Pancakes vs Burgers vs Donuts vs Sushi: First Stack to the Top | Stack Race #{race_no}"
    desc = ("Four food towers, one finish line 20 layers up. A crane drops one layer at a time, and anything that lands off-centre "
            "can drag the top of the tower down with it.\n\nWhich stack did you pick? \U0001F447\n\n#shorts #stackrace #foodbattle #satisfying #physics")
    return dict(duration=total, title=title, description=desc,
                tags=["stack race", "food battle", "pancakes vs burgers", "satisfying", "physics simulation", "tower stacking"],
                winner=names[win], ranking=[names[k] for k in order], final_heights={names[k]: fin_h[k] for k in range(N)},
                seed=seed, sim_info=info, slowmo=[s0, v1], v_end=v_end, thumb_ms=1500)

if __name__ == "__main__":                     # python3 -I lab/styles/stack_race.py <out.mp4> <seed> [episode]
    import json
    out = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1; ep = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    res = build(out, seed, race_no=ep, log=lambda *a: print(*a, file=sys.stderr)); print("RESULT=" + json.dumps(res, default=float))
