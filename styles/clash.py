"""STYLE: country_clash - two flag balls fight in a box. Each country grabs its own themed food power-ups.
Bracket series: 8 countries, 7 days (QF x4, SF x2, Final). No real data shown (pure game account)."""
import os, sys, math, json
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import engine as E
from engine import W, H, FPS

EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
KITS = {  # (emoji, effect, callout)
 "FR": dict(name="FRANCE", flag="🇫🇷", color=(80, 140, 255), items=[("🥖", "power", "BAGUETTE BONK"), ("🥐", "speed", "CROISSANT RUSH"), ("🧀", "heal", "CHEESE HEAL")]),
 "IT": dict(name="ITALY", flag="🇮🇹", color=(60, 200, 110), items=[("🍝", "power", "SPAGHETTI WHIP"), ("☕", "speed", "ESPRESSO SHOT"), ("🍕", "heal", "PIZZA HEAL")]),
 "US": dict(name="USA", flag="🇺🇸", color=(90, 130, 255), items=[("⚾", "power", "FASTBALL"), ("🦅", "speed", "EAGLE DIVE"), ("🍔", "heal", "BURGER HEAL")]),
 "GB": dict(name="UK", flag="🇬🇧", color=(230, 70, 90), items=[("☂️", "power", "UMBRELLA JAB"), ("🚌", "speed", "DOUBLE-DECKER DASH"), ("🫖", "heal", "TEA BREAK")]),
 "MX": dict(name="MEXICO", flag="🇲🇽", color=(40, 180, 100), items=[("🌶️", "power", "CHILI BURN"), ("🪅", "speed", "PIÑATA POP"), ("🌮", "heal", "TACO HEAL")]),
 "BR": dict(name="BRAZIL", flag="🇧🇷", color=(250, 210, 40), items=[("⚽", "power", "BICYCLE KICK"), ("🥁", "speed", "SAMBA RUSH"), ("🥥", "heal", "COCONUT HEAL")]),
 "JP": dict(name="JAPAN", flag="🇯🇵", color=(240, 70, 80), items=[("🥷", "power", "NINJA STRIKE"), ("🚄", "speed", "BULLET TRAIN"), ("🍣", "heal", "SUSHI HEAL")]),
 "IN": dict(name="INDIA", flag="🇮🇳", color=(255, 150, 50), items=[("🏏", "power", "CRICKET SMASH"), ("🛺", "speed", "RICKSHAW RUSH"), ("🍛", "heal", "CURRY HEAL")]),
}
BOX = (90, 600, 990, 1420)          # x0, y0, x1, y1
R, V0, HP0 = 100, 720.0, 100.0

_ec = {}
def emoji_sprite(ch, size):
    k = (ch, size)
    if k in _ec: return _ec[k]
    f = ImageFont.truetype(EMOJI, 109); im = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((80, 80), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox()); s = size / max(im.size)
    im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS)
    _ec[k] = np.array(im); return _ec[k]

def flag_ball(code, r):
    f = ImageFont.truetype(EMOJI, 109); im = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((90, 90), KITS[code]["flag"], font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox()); h = min(im.size); cx, cy = im.size[0] // 2, im.size[1] // 2
    im = im.crop((cx - h // 2 + 6, cy - h // 2 + 6, cx + h // 2 - 6, cy + h // 2 - 6)).resize((2 * r, 2 * r), Image.LANCZOS)
    a = np.array(im); m = np.zeros((2 * r, 2 * r), np.uint8); cv2.circle(m, (r, r), r - 2, 255, -1, cv2.LINE_AA)
    a[..., 3] = (a[..., 3].astype(np.uint16) * m // 255).astype(np.uint8)
    # glossy highlight
    hl = np.zeros((2 * r, 2 * r), np.float32); cv2.ellipse(hl, (int(r * .7), int(r * .55)), (int(r * .45), int(r * .28)), -30, 0, 360, 1, -1)
    hl = cv2.GaussianBlur(hl, (0, 0), r * .12) * .35
    a[..., :3] = np.clip(a[..., :3] + hl[..., None] * 255 * (a[..., 3:4] > 0), 0, 255).astype(np.uint8)
    return a

# ---------------------------------------------------------------- simulation
def simulate(seed, max_t=60.0, dt=1 / 240):
    rng = np.random.default_rng(seed); x0, y0, x1, y1 = BOX
    pos = np.array([[x0 + 220.0, (y0 + y1) / 2 + rng.uniform(-80, 80)], [x1 - 220.0, (y0 + y1) / 2 + rng.uniform(-80, 80)]])
    ang = rng.uniform(0, 2 * math.pi, 2); vel = np.stack([np.cos(ang), np.sin(ang)], 1) * V0
    hp = np.array([HP0, HP0]); power = [0, 0]; speed_until = [0.0, 0.0]
    items = []; nxt_spawn = 1.0; owner_turn = int(rng.integers(2)); ev = []; frames = []; contact = False; t = 0.0
    step = int(round(1 / (FPS * dt)))
    for s in range(int(max_t / dt)):
        t = s * dt
        if s % step == 0: frames.append(dict(t=t, pos=pos.copy(), hp=hp.copy(), power=list(power),
                                                speed=[speed_until[i] > t for i in range(2)], items=[dict(it) for it in items]))
        if t >= nxt_spawn and len(items) < 4:                                       # spawn power-up
            for _ in range(50):
                p = np.array([rng.uniform(x0 + 70, x1 - 70), rng.uniform(y0 + 70, y1 - 70)])
                if np.min(np.hypot(*(pos - p).T)) > R + 90: break
            k = int(rng.integers(3)); items.append(dict(owner=owner_turn, kind=k, p=p, t0=t)); owner_turn ^= 1
            nxt_spawn = t + rng.uniform(1.1, 1.8)
        items = [it for it in items if t - it["t0"] < 5.5]
        for i in range(2):                                                          # move + walls
            sp = V0 * (1.6 if speed_until[i] > t else 1.0); v = np.hypot(*vel[i]); vel[i] *= sp / v
            pos[i] += vel[i] * dt
            for ax, lo, hi in ((0, x0, x1), (1, y0, y1)):
                if pos[i, ax] - R < lo: pos[i, ax] = lo + R; vel[i, ax] = abs(vel[i, ax]); ev.append(("wall", t, i))
                if pos[i, ax] + R > hi: pos[i, ax] = hi - R; vel[i, ax] = -abs(vel[i, ax]); ev.append(("wall", t, i))
            for j in range(len(items) - 1, -1, -1):                                 # pickups (owner only)
                it = items[j]
                if it["owner"] == i and np.hypot(*(pos[i] - it["p"])) < R + 38:
                    items.pop(j); kind = KITS_ORDER[i]["items"][it["kind"]][1]
                    if kind == "heal": hp[i] = min(HP0, hp[i] + 20)
                    elif kind == "power": power[i] = 2
                    else: speed_until[i] = t + 3.0
                    ev.append(("pick", t, i, it["kind"], it["p"].copy()))
        d = pos[1] - pos[0]; dist = np.hypot(*d)                                    # ball-ball hit
        if dist < 2 * R:
            n = d / dist
            if not contact:
                a0 = max(0.0, vel[0] @ n) / V0; a1 = max(0.0, -(vel[1] @ n)) / V0
                dmg1 = (3 + 11 * a0) * (2.5 if power[0] else 1); dmg0 = (3 + 11 * a1) * (2.5 if power[1] else 1)
                if power[0]: power[0] -= 1
                if power[1]: power[1] -= 1
                hp[1] -= dmg1; hp[0] -= dmg0; ev.append(("hit", t, (pos[0] + pos[1]) / 2, dmg0, dmg1))
                v0n, v1n = vel[0] @ n, vel[1] @ n; vel[0] += (v1n - v0n) * n; vel[1] += (v0n - v1n) * n
            o = 2 * R - dist; pos[0] -= n * o / 2; pos[1] += n * o / 2; contact = True
        else: contact = False
        if hp.min() <= 0:
            hp = np.maximum(hp, 0); frames.append(dict(t=t, pos=pos.copy(), hp=hp.copy(), power=list(power), speed=[False, False], items=[dict(it) for it in items]))
            return dict(frames=frames, ev=ev, T=t, winner=int(np.argmax(hp)), hp=hp)
    return None

KITS_ORDER = [None, None]

def pick_seed(a, b, base, tries=40, log=print):
    KITS_ORDER[0], KITS_ORDER[1] = KITS[a], KITS[b]; best = None
    for seed in range(base, base + tries):
        sim = simulate(seed)
        if not sim: continue
        lead = [np.sign(f["hp"][0] - f["hp"][1]) for f in sim["frames"]]; changes = sum(1 for i in range(1, len(lead)) if lead[i] and lead[i - 1] and lead[i] != lead[i - 1])
        w_hp = sim["hp"][sim["winner"]]; picks = sum(1 for e in sim["ev"] if e[0] == "pick")
        score = -abs(sim["T"] - 22) / 6 - abs(w_hp - 18) / 15 + min(changes, 3) * .6 + min(picks, 8) * .1
        if 14 <= sim["T"] <= 32 and 0 < w_hp <= 40 and (best is None or score > best[0]): best = (score, seed, sim)
    assert best, "no good seed"; log(f"[clash] seed {best[1]}: T={best[2]['T']:.1f}s winner HP {best[2]['hp'][best[2]['winner']]:.0f}"); return best[1], best[2]

# ---------------------------------------------------------------- build
def build(spec, root, out_dir, stills=None, log=print):
    a, b = spec["a"], spec["b"]; KA, KB = KITS[a], KITS[b]; kits = [KA, KB]
    seed, sim = pick_seed(a, b, spec.get("seed", 1), log=log)
    fr = sim["frames"]; T = sim["T"]; win = sim["winner"]; lose = 1 - win
    SLOW_T, SLOW = 0.7, 0.3                                   # last 0.7 s of sim at 0.3x
    v_slow0 = T - SLOW_T; v_end = v_slow0 + SLOW_T / SLOW
    def sim_t(v): return v if v <= v_slow0 else min(T, v_slow0 + (v - v_slow0) * SLOW)
    def vid_t(t): return t if t <= v_slow0 else v_slow0 + (t - v_slow0) / SLOW
    CARD = 4.0; total = v_end + CARD; n = int(round(total * FPS)); LOOP = .35
    stage = spec.get("stage", "QUARTERFINAL"); day = spec.get("day", 1)
    log(f"[clash] {KA['name']} vs {KB['name']}: video {total:.1f}s, winner {kits[win]['name']}")

    x0, y0, x1, y1 = BOX
    bg = E.make_bg(top=(10, 6, 18), bottom=(26, 8, 22), glow=(70, 30, 60))
    ov = bg.copy(); cv2.rectangle(ov, (x0, y0), (x1, y1), (6, 4, 12), -1); cv2.addWeighted(ov, .6, bg, .4, 0, bg)
    for i, c in enumerate([KA["color"], KB["color"]]):                       # half-tint arena
        ov = bg.copy(); xa, xb = (x0, (x0 + x1) // 2) if i == 0 else ((x0 + x1) // 2, x1)
        cv2.rectangle(ov, (xa, y0), (xb, y1), E.mulc(c, .25), -1); cv2.addWeighted(ov, .25, bg, .75, 0, bg)
    g = np.zeros((H // 2, W // 2, 3), np.uint8); cv2.rectangle(g, (x0 // 2, y0 // 2), (x1 // 2, y1 // 2), (200, 60, 160), 6); E.add_glow(bg, g, 8, .9)
    cv2.rectangle(bg, (x0, y0), (x1, y1), (255, 170, 230), 5, cv2.LINE_AA)
    E.blit(bg, E.text_sprite(spec.get("watermark", "@eas.ydata"), 26, (235, 235, 245), "bold", stroke=2, stroke_color=(0, 0, 0)), W - 48, 1590, alpha=.6, anchor="r")
    # legend under the box
    for side, K in enumerate(kits):
        cx = 300 if side == 0 else 780
        E.blit(bg, E.text_sprite(K["name"] + " POWER-UPS", 22, E.mulc(K["color"], 1.1), "bold", spacing=2), cx, 1462)
        for j, (em, kind, _) in enumerate(K["items"]):
            ex = cx - 120 + j * 120; E.blit(bg, emoji_sprite(em, 44), ex, 1508)
            E.blit(bg, E.text_sprite({"power": "×2.5 HIT", "speed": "SPEED", "heal": "+20 HP"}[kind], 18, (220, 220, 235), "bold"), ex, 1548)
    balls = [flag_ball(a, R), flag_ball(b, R)]
    tag = E.text_sprite(f"COUNTRY CLASH  ·  DAY {day}  ·  {stage}", 30, (255, 170, 230), "bold", spacing=4)
    vs_l = E.text_sprite(KA["name"], 60, (255, 255, 255), "bold", stroke=4, stroke_color=(0, 0, 0))
    vs_r = E.text_sprite(KB["name"], 60, (255, 255, 255), "bold", stroke=4, stroke_color=(0, 0, 0))
    vs = E.text_sprite("VS", 40, (255, 200, 80), "black", stroke=3, stroke_color=(0, 0, 0))
    hooks = [(0, 2.2, "2 COUNTRIES · 1 BOX · ONLY ONE LEAVES"), (2.2, 4.0, "PICK A SIDE NOW 👇"), (4.0, 99, "EACH COUNTRY ONLY GRABS ITS OWN SNACKS")]
    hook_sp = [E.text_sprite(h[2].replace(" 👇", ""), 30, (255, 225, 140), "bold") for h in hooks]
    pick_ev = [(vid_t(e[1]), e) for e in sim["ev"] if e[0] == "pick"]; hit_ev = [(vid_t(e[1]), e) for e in sim["ev"] if e[0] == "hit"]
    fi = lambda t: min(len(fr) - 1, int(t * FPS))
    def interp(t):
        f = t * FPS; i0 = min(len(fr) - 2, int(f)); w = min(1.0, f - i0); A, B = fr[i0], fr[i0 + 1]
        return A["pos"] * (1 - w) + B["pos"] * w, A["hp"] * (1 - w) + B["hp"] * w, A
    nxt = {}
    nxt_txt = spec.get("next", "")

    def hpbar(f, side, hp, v):
        K = kits[side]; xL = 70 if side == 0 else 560; wbar = 450; y = 470
        E.pill(f, xL, y, xL + wbar, y + 44, (20, 15, 30), .9)
        fw = int((wbar - 8) * max(0, hp) / HP0); col = K["color"] if hp > 25 else ((255, 70, 70) if int(v * 6) % 2 else (255, 160, 160))
        if fw > 8:
            if side == 0: cv2.rectangle(f, (xL + 4, y + 6), (xL + 4 + fw, y + 38), col, -1, cv2.LINE_AA)
            else: cv2.rectangle(f, (xL + wbar - 4 - fw, y + 6), (xL + wbar - 4, y + 38), col, -1, cv2.LINE_AA)
        E.blit(f, E.text_sprite(f"{int(math.ceil(max(0, hp)))} HP", 26, (255, 255, 255), "bold", stroke=3, stroke_color=(0, 0, 0)), xL + wbar / 2, y + 22)

    def draw(i, final=True):
        v = i / FPS; t = sim_t(v); P, HPv, A = interp(t); f = bg.copy()
        if v >= v_end - 1 / FPS: HPv = sim["hp"]
        for it in A["items"]:                                                          # items bob + fade in/out
            age = t - it["t0"]; s = E.out_back(min(1, age / .3)) * (1 - E.smooth((age - 5.0) / .5))
            if s <= 0.02: continue
            em = kits[it["owner"]]["items"][it["kind"]][0]; c = kits[it["owner"]]["color"]
            cv2.circle(f, (int(it["p"][0]), int(it["p"][1] + 6 * math.sin(age * 5))), int(48 * s), E.mulc(c, .55), 3, cv2.LINE_AA)
            E.blit(f, emoji_sprite(em, 72), it["p"][0], it["p"][1] + 6 * math.sin(age * 5), scale=s)
        for k in range(2):                                                             # balls + aura
            x, y = P[k]
            if A["power"][k]: cv2.circle(f, (int(x), int(y)), int(R + 14 + 4 * math.sin(v * 20)), (255, 90, 60), 6, cv2.LINE_AA)
            if A["speed"][k]: cv2.circle(f, (int(x), int(y)), R + 10, (120, 230, 255), 4, cv2.LINE_AA)
            if k == lose and v >= v_end: continue
            E.blit(f, balls[k], x, y)
        for (vt_, e) in hit_ev:                                                         # hit flash + damage numbers
            age = v - vt_
            if 0 <= age < .9:
                c = e[2]; 
                if age < .15: cv2.circle(f, (int(c[0]), int(c[1])), int(30 + 220 * age), (255, 255, 255), max(1, int(8 * (1 - age / .15))), cv2.LINE_AA)
                for k, dm in ((0, e[3]), (1, e[4])):
                    if dm < .5: continue
                    big = dm > 14; px = c[0] + (-90 if k == 0 else 90); py = c[1] - 40 - 90 * E.smooth(age / .9)
                    E.blit(f, E.text_sprite(f"-{int(round(dm))}", 54 if big else 40, (255, 80, 80) if big else (255, 220, 220), "black", stroke=4, stroke_color=(0, 0, 0)),
                           float(np.clip(px, 120, W - 120)), py, alpha=1 - E.smooth((age - .6) / .3), scale=1 + .3 * max(0, 1 - age / .12))
        for (vt_, e) in pick_ev:                                                        # pickup callouts
            age = v - vt_
            if 0 <= age < 1.1:
                k, kind = e[2], e[3]; txt = kits[k]["items"][kind][2] + "!"; p = e[4]
                E.blit(f, E.text_sprite(txt, 40, E.mulc(kits[k]["color"], 1.15), "black", stroke=5, stroke_color=(0, 0, 0)),
                       float(np.clip(p[0], 230, W - 230)), float(np.clip(p[1] - 70 - 40 * age, y0 + 40, y1 - 40)), alpha=1 - E.smooth((age - .8) / .3), scale=E.out_back(age / .2))
        E.blit(f, tag, W / 2, 268)                                                     # HUD
        E.blit(f, vs_l, 290, 360); E.blit(f, vs, W / 2, 362); E.blit(f, vs_r, 790, 360)
        hpbar(f, 0, HPv[0], v); hpbar(f, 1, HPv[1], v)
        for (t0, t1, _), sp in zip(hooks, hook_sp):
            if t0 <= v < min(t1, v_slow0): E.blit(f, sp, W / 2, 555, alpha=E.smooth((v - t0) / .25))
        if v_slow0 <= v < v_end: E.blit(f, E.text_sprite("FINAL HIT", 46, (255, 90, 90), "black", stroke=5, stroke_color=(0, 0, 0), spacing=6), W / 2, 555, alpha=.6 + .4 * math.sin(v * 14) ** 2)
        if v >= v_end:                                                                 # KO card
            u = v - v_end; a_ = E.smooth(u / .3); sc = E.out_back(u / .45)
            if u < .1: f[:1600] = cv2.add(f[:1600], np.full_like(f[:1600], int(170 * (1 - u / .1))))
            f[:1600] = cv2.convertScaleAbs(f[:1600], alpha=1 - .5 * a_); E.pill(f, 40, 700, W - 40, 1360, (8, 6, 14), .75 * a_)
            E.blit(f, balls[win], W / 2, 800, scale=.8 * sc)
            E.blit(f, E.text_sprite(spec.get("win_text", "{n} WINS").format(n=kits[win]['name']), 108 if len(kits[win]['name']) < 8 and not spec.get("win_text") else 76, (255, 255, 255), "black", stroke=6, stroke_color=(0, 0, 0)), W / 2, 965, alpha=a_, scale=sc)
            E.blit(f, E.text_sprite(f"with {int(math.ceil(sim['hp'][win]))} HP left", 38, E.mulc(kits[win]["color"], 1.15), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1060, alpha=E.smooth((u - .2) / .3))
            if nxt_txt: E.blit(f, E.text_sprite(nxt_txt, 36, (255, 200, 120), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1150, alpha=E.smooth((u - .6) / .3))
            c = E.smooth((u - 1.0) / .3)
            E.blit(f, E.text_sprite(spec.get("card_q", "WHO WINS THE WHOLE THING?"), 38, (255, 255, 255), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1235, alpha=c)
            E.blit(f, E.text_sprite(f"SEND THIS TO SOMEONE FROM {kits[lose]['name']}", 30, (190, 220, 255), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1290, alpha=E.smooth((u - 1.5) / .3))
        if final and v > total - LOOP:
            bb = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - bb, draw(0, False), bb, 0)
        return f

    # ---------------- audio: 8-bit arcade fighter (distinct from the kalimba series)
    SR = E.SR; tt = lambda d: np.arange(int(d * SR)) / SR
    def sq(f, d, decay=6.0, duty=.5, vol=.35):
        t_ = tt(d); ph = (t_ * f) % 1.0; w = np.where(ph < duty, 1.0, -1.0)
        return (w * np.exp(-t_ * decay) * (1 - np.exp(-t_ * 2000)) * vol).astype(np.float32)
    def tri(f, d, decay=5.0, vol=.45):
        t_ = tt(d); w = 2 * np.abs(2 * ((t_ * f) % 1.0) - 1) - 1
        return (w * np.exp(-t_ * decay) * vol).astype(np.float32)
    def sweep(f0, f1, d, duty=.25, vol=.3):
        t_ = tt(d); f = f0 * (f1 / f0) ** (t_ / d); ph = np.cumsum(f) / SR % 1.0
        return (np.where(ph < duty, 1.0, -1.0) * (1 - t_ / d) * vol).astype(np.float32)
    def noise(d, decay=25, vol=.4, seed=0, lp=1):
        n = np.random.default_rng(seed).standard_normal(len(tt(d)))
        if lp > 1: n = np.convolve(n, np.ones(lp) / lp, "same")
        return (n * np.exp(-tt(d) * decay) * vol).astype(np.float32)
    hz = lambda m: float(E.midi_hz(m))
    mix = E.Mix(total)
    # "READY... FIGHT" arcade intro
    mix.add(0.0, sq(hz(72), .12, 10), .5); mix.add(.14, sq(hz(79), .12, 10), .5); mix.add(.28, sweep(300, 1400, .35), .5)
    # driving beat: kick on beats, hats on offbeats, square bass on a minor riff; doubles hats when someone is low
    bpm = 132; beat = 60 / bpm; t_low = next((f["t"] for f in fr if f["hp"].min() < 30), None); v_low = vid_t(t_low) if t_low is not None else 1e9
    riff = [45, 45, 48, 45, 52, 50, 48, 43]; k = 0; tb = .55
    while tb < v_end - .05:
        intense = tb >= v_low; slow = tb >= v_slow0
        kick = E.thump(.22, 160, 45); mix.add(tb, kick, .55 if not slow else .35)
        mix.add(tb, sq(hz(riff[k % 8] + (12 if intense else 0) * 0), beat * .9, 7, .25, .22), .55)
        mix.add(tb + beat / 2, noise(.05, 70, .25, k, 1), .35)
        if intense: mix.add(tb + beat / 4, noise(.04, 80, .2, k + 99, 1), .3); mix.add(tb + 3 * beat / 4, noise(.04, 80, .2, k + 199, 1), .3)
        if k % 4 == 2: mix.add(tb, noise(.12, 30, .35, k + 7, 3), .45)          # snare on 3
        tb += beat * (1 if not slow else 1 / SLOW); k += 1
    for (vt_, e) in hit_ev:                                                        # hits: crunchy noise + falling square
        if vt_ > v_end: continue
        dm = e[3] + e[4]; pan = (e[2][0] - W / 2) / (W / 2) * .5; big = dm > 20
        mix.add(vt_, noise(.18 if big else .1, 22, .5, int(vt_ * 1000), 2), .55 + min(.4, dm / 50), pan)
        mix.add(vt_, sweep(900 if big else 650, 120, .22 if big else .14, .5, .35), .5, pan)
        if big: mix.add(vt_, E.thump(.3, 120, 40), .6)
    for (vt_, e) in pick_ev:                                                       # pickups: coin / power-up jingles
        if vt_ > v_end: continue
        kind = kits[e[2]]["items"][e[3]][1]; pan = -.4 if e[2] == 0 else .4; base = 76 if e[2] == 0 else 74
        if kind == "heal":
            for j, st in enumerate([0, 4, 7, 12]): mix.add(vt_ + j * .06, tri(hz(base + st), .18, 9), .45, pan)
        elif kind == "speed": mix.add(vt_, sweep(500, 2400, .25, .5, .3), .45, pan)
        else: mix.add(vt_, sq(hz(base - 5), .07, 12), .45, pan); mix.add(vt_ + .07, sq(hz(base + 7), .25, 6), .45, pan)
    mix.add(v_slow0, E.riser(v_end - v_slow0, 200, 3000), .4)
    mix.add(v_end, noise(.9, 5, .6, 42, 4), .9); mix.add(v_end, E.thump(1.2, 110, 28), 1.0)       # KO boom
    for j, m in enumerate([72, 76, 79, 84, 79, 84]):                                             # victory fanfare
        mix.add(v_end + .45 + j * .13, sq(hz(m), .35 if j < 5 else .9, 4, .25, .3), .5)
        mix.add(v_end + .45 + j * .13, tri(hz(m - 12), .35 if j < 5 else .9, 3), .35)
    wav = os.path.join(out_dir, spec["name"] + ".wav"); mix.write(wav, peak=.78)
    if stills:
        for t_ in stills: E.save_png(os.path.join(out_dir, f"{spec['name']}_still_{t_:05.2f}.png"), draw(int(t_ * FPS)))
        return dict(still_only=True, total=total, v_end=v_end)
    mp4 = os.path.join(out_dir, spec["name"] + ".mp4"); E.render(mp4, wav, n, draw)
    return dict(mp4=mp4, duration=total, winner=kits[win]["name"], winner_code=[a, b][win], loser=kits[lose]["name"], winner_hp=int(math.ceil(sim["hp"][win])),
                picks=len(pick_ev), hits=len(hit_ev), seed=seed)
