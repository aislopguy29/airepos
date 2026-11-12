"""STYLE: ring_elimination  (reference: @geoclash.games / @eterniq_visual 'last one inside is OUT').
Entities bounce inside a rotating ring with a gap. Escape through the gap = safe. Last one inside = eliminated.
Series mechanic: Day N, running tally of eliminated entities, 'N-1 return tomorrow'.
Data hook: circle size is driven by a .gov metric (default: Census population), so the data shapes the game."""
import os, sys, csv, math, json, hashlib
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import engine as E
from engine import W, H, FPS, SR

REGION = {"Northeast": (255, 120, 120), "Midwest": (255, 200, 70), "South": (70, 210, 175), "West": (100, 160, 255)}
DEF = dict(R=455, CX=540, CY=1010, gap_arc=360, gap_arc_end=760, min_speed=0.75, omega=0.9, speed=560, restitution=0.98, fall_g=1800,
           r_min=20, r_max=48, size_exp=0.45, max_t=75.0, dt=1 / 240)

def load_entities(spec, root):
    rows = list(csv.DictReader(open(os.path.join(root, spec["entities_csv"]))))
    gone = set(spec.get("eliminated_before", []))
    return [dict(code=r["code"], name=r["name"], region=r["region"], pop=int(r["population"]), rank=int(r["rank_of_51"]))
            for r in rows if r["code"] not in gone]

def radii(ents, cfg):
    pops = np.array([e["pop"] for e in ents], float)
    return cfg["r_min"] + (cfg["r_max"] - cfg["r_min"]) * (pops / pops.max()) ** cfg["size_exp"]

# ------------------------------------------------------------------ physics
def gap_half(cfg, rem, N):
    u = 1 - (rem - 1) / max(N - 1, 1)                      # 0 at start -> 1 when one is left
    return (cfg["gap_arc"] + (cfg["gap_arc_end"] - cfg["gap_arc"]) * u ** 1.3) / (2 * cfg["R"])

def simulate(r, seed, cfg):
    rng = np.random.default_rng(seed); N = len(r); R = cfg["R"]; dt = cfg["dt"]
    half = cfg["gap_arc"] / (2 * R); omega = cfg["omega"]
    th0 = rng.uniform(0, 2 * math.pi); sgn = rng.choice([-1, 1])
    pos = np.zeros((N, 2)); placed = []
    for i in np.argsort(-r):
        for _ in range(4000):
            a = rng.uniform(0, 2 * math.pi); d = (R - r[i] - 10) * math.sqrt(rng.uniform())
            p = np.array([d * math.cos(a), d * math.sin(a)])
            if all(np.hypot(*(p - pos[j])) > r[i] + r[j] + 5 for j in placed): pos[i] = p; placed.append(i); break
        else: raise RuntimeError("could not place entities; reduce radii")
    ang = rng.uniform(0, 2 * math.pi, N); vel = np.stack([np.cos(ang), np.sin(ang)], 1) * (cfg["speed"] * rng.uniform(.75, 1.25, N))[:, None]
    m = r ** 2; esc = np.full(N, np.nan); hist = []; wall = []; ball = []; e = cfg["restitution"]
    for s in range(int(cfg["max_t"] / dt)):
        t = s * dt; hist.append(pos.astype(np.float32).copy())
        pos += vel * dt
        gone = ~np.isnan(esc); vel[gone, 1] += cfg["fall_g"] * dt
        ia = np.nonzero(~gone)[0]
        if len(ia) > 1:                                          # ball-ball
            P = pos[ia]; Rr = r[ia]
            dx = P[:, 0][:, None] - P[:, 0][None, :]; dy = P[:, 1][:, None] - P[:, 1][None, :]
            dist = np.hypot(dx, dy); ov = (Rr[:, None] + Rr[None, :]) - dist; np.fill_diagonal(ov, -1)
            for a, b in zip(*np.nonzero(np.triu(ov > 0, 1))):
                i, j = ia[a], ia[b]; n = np.array([dx[a, b], dy[a, b]]) / max(dist[a, b], 1e-6)
                vn = float((vel[i] - vel[j]) @ n)
                if vn < 0:
                    jimp = -(1 + e) * vn / (1 / m[i] + 1 / m[j]); vel[i] += jimp / m[i] * n; vel[j] -= jimp / m[j] * n
                    ball.append((t, i, j, -vn))
                o = ov[a, b]; pos[i] += n * o * m[j] / (m[i] + m[j]); pos[j] -= n * o * m[i] / (m[i] + m[j])
        rem = int(np.isnan(esc).sum())
        half = gap_half(cfg, rem, N)
        spd = np.hypot(vel[ia, 0], vel[ia, 1]); lo = cfg["min_speed"] * cfg["speed"]
        slow = spd < lo; vel[ia[slow]] *= (lo / np.maximum(spd[slow], 1e-6))[:, None]
        thg = th0 + sgn * omega * t                              # ring + rotating gap
        d = np.hypot(pos[ia, 0], pos[ia, 1])
        for k in np.nonzero(d + r[ia] > R)[0]:
            i = ia[k]; phi = math.atan2(pos[i, 1], pos[i, 0]); delta = abs((phi - thg + math.pi) % (2 * math.pi) - math.pi)
            if delta < half - r[i] / R:
                if d[k] > R: esc[i] = t
            else:
                n = pos[i] / d[k]; vn = float(vel[i] @ n)
                if vn > 0: vel[i] -= 2 * vn * n; wall.append((t, i, vn))
                pos[i] = n * (R - r[i])
        if np.isnan(esc).sum() <= 1: break
    return dict(hist=np.array(hist), esc=esc, wall=wall, ball=ball, th0=th0, sgn=int(sgn), dt=dt)

def metrics(sim, N):
    es = np.sort(sim["esc"][~np.isnan(sim["esc"])])
    if len(es) < N - 1: return None
    return dict(T=float(es[-1]), phase3=float(es[-1] - es[-2]), t5=float(es[N - 6]))

def pick_seed(r, cfg, spec, root, log=print):
    best = None; N = len(r); lo, hi = spec.get("sim_len", [14, 48])
    for seed in range(spec.get("seed", 1), spec.get("seed", 1) + spec.get("seed_tries", 24)):
        key = hashlib.md5(json.dumps([seed, [round(float(x), 2) for x in r], {k: cfg[k] for k in ("R", "gap_arc", "gap_arc_end", "min_speed", "omega", "speed")}]).encode()).hexdigest()[:10]
        cp = os.path.join(root, "out", "cache", f"ring_{key}.npz")
        if os.path.exists(cp):
            z = np.load(cp, allow_pickle=True); sim = dict(hist=z["hist"], esc=z["esc"], wall=list(z["wall"]), ball=list(z["ball"]),
                                                              th0=float(z["th0"]), sgn=int(z["sgn"]), dt=float(z["dt"]))
        else:
            sim = simulate(r, seed, cfg); os.makedirs(os.path.dirname(cp), exist_ok=True)
            np.savez_compressed(cp, hist=sim["hist"], esc=sim["esc"], wall=np.array(sim["wall"]), ball=np.array(sim["ball"]),
                                th0=sim["th0"], sgn=sim["sgn"], dt=sim["dt"])
        mt = metrics(sim, N)
        if not mt: log(f"  seed {seed}: did not finish"); continue
        ok = lo <= mt["T"] <= hi and mt["phase3"] <= spec.get("max_photo_finish", 3.0)
        score = (0 if ok else -100) - abs(mt["phase3"] - 1.4) - abs(mt["T"] - 15) / 10
        log(f"  seed {seed}: T={mt['T']:.1f}s finish-gap={mt['phase3']:.1f}s {'OK' if ok else ''} score={score:.2f}")
        if best is None or score > best[0]: best = (score, seed, sim, mt)
        if spec.get("seed_tries", 24) > 1 and ok and score > -1.2: break
    return best

# ------------------------------------------------------------------ director: time warp (sim time -> video time)
def build_warp(sim, N, mt, spec):
    dt = sim["dt"]; es = np.sort(sim["esc"][~np.isnan(sim["esc"])]); n = int(mt["T"] / dt) + 2
    ts = np.arange(n) * dt
    rem = N - np.searchsorted(es, ts, side="right")
    m0 = max(1.0, (mt["t5"] + 1.0) / spec.get("body_seconds", 15.0))
    sp = np.where(rem >= 6, m0, np.where(rem >= 3, 1.0, spec.get("slowmo", 0.5)))
    sp = np.where(ts < 1.5, 1.0 + (m0 - 1.0) * E.smooth(ts / 1.5), sp)       # ease-in from x1.0
    k = int(0.8 / dt); sp = np.convolve(np.pad(sp, (k, k), mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), "valid")[:n]
    tv = np.concatenate([[0], np.cumsum(dt / sp[:-1])])
    return ts, tv, sp, es

# ------------------------------------------------------------------ build
def build(spec, root, out_dir, smoke=None, stills=None, log=print):
    cfg = {**DEF, **spec.get("cfg", {})}; ents = load_entities(spec, root); N = len(ents)
    r = radii(ents, cfg); R, CX, CY = cfg["R"], cfg["CX"], cfg["CY"]
    log(f"[ring] {N} entities, radii {r.min():.0f}-{r.max():.0f}px, searching seeds…")
    best = pick_seed(r, cfg, spec, root, log); assert best, "no seed finished"
    _, seed, sim, mt = best; log(f"[ring] seed {seed}: sim {mt['T']:.1f}s, final gap {mt['phase3']:.1f}s")
    ts_grid, tv_grid, sp_grid, es = build_warp(sim, N, mt, spec)
    esc = sim["esc"]; hist = sim["hist"]; dt = sim["dt"]
    loser = int([i for i in range(N) if np.isnan(esc[i])][0])
    shield = spec.get("shield"); saved = None
    if shield and ents[loser]["code"] == shield and spec.get("mode", "elim") == "elim":
        saved = loser; loser = int(np.nanargmax(np.where(np.isnan(esc), -1, esc)))   # shield holds: closest escape goes out
    shield_i = next((i for i, e_ in enumerate(ents) if e_["code"] == shield), None)
    L = ents[loser]
    v_esc = np.where(np.isnan(esc), np.inf, np.interp(np.nan_to_num(esc), ts_grid, tv_grid))
    v_end = float(np.interp(mt["T"], ts_grid, tv_grid)); CARD = spec.get("card_seconds", 3.6)
    total = v_end + CARD; n_frames = int(round(total * FPS)); LOOP = 0.35
    if smoke: n_frames = min(n_frames, int(smoke * FPS))
    day = spec.get("episode", 1); series = spec.get("series", "STATE ELIMINATION")
    tally = spec.get("eliminated_before", [])
    log(f"[ring] video {total:.1f}s @ {FPS}fps = {int(round(total*FPS))} frames. Eliminated: {L['name']} ({L['code']})")

    # ---------- static art
    bg = E.make_bg(top=(6, 8, 20), bottom=(18, 8, 36), glow=(35, 40, 100))
    ov = bg.copy(); cv2.circle(ov, (CX, CY), R - 4, (4, 5, 14), -1, cv2.LINE_AA); cv2.addWeighted(ov, .5, bg, .5, 0, bg)
    E.bake_source_bar(bg, spec["source_line"])
    if spec.get("watermark"):                                   # small handle watermark, baked into every frame
        E.blit(bg, E.text_sprite(spec["watermark"], 26, (235, 235, 245), "bold", stroke=2, stroke_color=(0, 0, 0)), W - 48, 1590, alpha=.6, anchor="r")
    sprites = []
    for e_, rr in zip(ents, r):
        col = REGION[e_["region"]]; sprites.append(dict(
            fill=E.mulc(col, .42), edge=col, lab=E.text_sprite(e_["code"], max(15, int(rr * .74)), (255, 255, 255), "bold", stroke=2, stroke_color=(10, 10, 20))))
    title = E.text_sprite(spec.get("title", "LAST ONE INSIDE IS OUT"), 66, (255, 255, 255), "bold", stroke=5, stroke_color=(0, 0, 0))
    tag = E.text_sprite(f"{series}  ·  DAY {day}", 31, (120, 220, 255), "bold", spacing=4)
    lab_in = E.text_sprite("STILL INSIDE", 30, (190, 200, 225), "bold", spacing=5)
    order = np.argsort(-r)
    popups = [(v_esc[i], i) for i in range(N) if np.isfinite(v_esc[i])]
    nums = {n: E.text_sprite(str(n), 92, (255, 255, 255), "black", stroke=4, stroke_color=(0, 0, 0)) for n in range(0, N + 1)}
    tracks = [(0.0, 2.2, spec.get("hook_sub", f"{N} STATES · 1 GAP · WHO ESCAPES LAST?"), (255, 255, 255)),
              (2.2, 3.4, "PICK YOUR STATE. NOW WATCH IT.", (255, 225, 120)),
              (3.6, v_end * .5, "ESCAPE THROUGH THE GAP TO STAY SAFE", (170, 180, 205)),
              (v_end * .5, v_end * .5 + 3.2, spec.get("cta_mid", "ROOTING FOR A STATE? DROP IT BELOW"), (255, 225, 120)),
              (v_end * .5 + 3.4, v_end - 0.2, "THE GAP GROWS AS STATES ESCAPE", (170, 180, 205))]
    track_sp = [E.text_sprite(t[2], 33, t[3], "bold", spacing=1) for t in tracks]
    surv_sp = E.text_sprite("LAST TWO", 30, (255, 225, 120), "bold", spacing=5)
    card_col = tuple(spec.get("card_color", [255, 85, 85]))
    elim_sp = E.text_sprite(spec.get("card_word", "ELIMINATED"), 62, card_col, "bold", stroke=4, stroke_color=(0, 0, 0), spacing=8)
    name_sp = E.text_sprite(L["name"].upper(), 118 if len(L["name"]) < 11 else 92 if len(L["name"]) < 15 else 74, (255, 255, 255), "bold", stroke=6, stroke_color=(0, 0, 0))
    rk = L["rank"]; rk_txt = f"{L['pop']:,} people · " + ("least populous of the " + str(51) if rk == 51 else f"#{rk} of 51 by population")
    stat_sp = E.text_sprite(rk_txt, 36, (230, 235, 250), "med", stroke=3, stroke_color=(0, 0, 0))
    back_sp = E.text_sprite(spec.get("back_text", "{n} RETURN TOMORROW  ·  DAY {d}").format(n=N - 1, d=day + 1), 40, (120, 220, 255), "bold", stroke=3, stroke_color=(0, 0, 0))
    cta_sp = E.text_sprite(spec.get("cta_end", "WHICH STATE ARE YOU ROOTING FOR?"), 38, (255, 225, 120), "bold", stroke=3, stroke_color=(0, 0, 0))
    cta2_sp = E.text_sprite(spec.get("cta_send", f"SEND THIS TO SOMEONE FROM {L['name'].upper()}"), 32, (255, 255, 255), "bold", stroke=3, stroke_color=(0, 0, 0), spacing=1)
    saved_sp = E.text_sprite(f"SHIELD SAVED {ents[saved]['name'].upper()} · CLOSEST ESCAPE GOES OUT", 30, (255, 205, 70), "bold", stroke=3, stroke_color=(0, 0, 0)) if saved is not None else None
    shield_lab = E.text_sprite("SHIELD", 22, (255, 205, 70), "bold", stroke=3, stroke_color=(0, 0, 0), spacing=3)
    out_sp = E.text_sprite(spec.get("tally_label", "OUT") + ": " + ", ".join(tally[-8:]), 28, E.mulc(card_col, 1.0), "bold") if tally else None
    ring_col = tuple(spec.get("ring_color", [120, 215, 255])); glow_col = tuple(spec.get("glow_color", [40, 120, 255]))

    def sim_time(v):
        return float(np.interp(v, tv_grid, ts_grid)) if v <= v_end else mt["T"]
    def positions(ts):
        f = ts / dt; a = int(min(f, len(hist) - 2)); w = f - a
        return hist[a] * (1 - w) + hist[a + 1] * w
    def ring(f, th, v):
        hg = gap_half(cfg, int(N - np.sum(v_esc <= v)), N)
        a0 = math.degrees(th + hg); a1 = math.degrees(th - hg) + 360
        g = np.zeros((H // 2, W // 2, 3), np.uint8)
        cv2.ellipse(g, (CX // 2, CY // 2), (R // 2, R // 2), 0, a0, a1, glow_col, 12, cv2.LINE_AA)
        E.add_glow(f, g, 9, 1.0)
        cv2.ellipse(f, (CX, CY), (R, R), 0, a0, a1, ring_col, 9, cv2.LINE_AA)
        for aa in (a0, a1):
            cv2.circle(f, (int(CX + R * math.cos(math.radians(aa))), int(CY + R * math.sin(math.radians(aa)))), 9, (255, 255, 255), -1, cv2.LINE_AA)

    def draw(i, final=True):
        v = i / FPS; ts = sim_time(v); P = positions(ts); f = bg.copy()
        th = sim["th0"] + sim["sgn"] * cfg["omega"] * (ts if v <= v_end else mt["T"] + (v - v_end) * .6)
        ring(f, th, v); rem = int(N - np.sum(v_esc <= v)); inside = [k for k in range(N) if v_esc[k] > v]
        for k in order:                                                            # balls (big first)
            te = v - v_esc[k]
            sc = 1.0 if te < 0.25 else max(0.0, 1 - E.smooth((te - 0.25) / 0.45))
            if sc <= 0: continue
            x, y = CX + P[k, 0], CY + P[k, 1]; rr = r[k] * sc; s = sprites[k]
            cv2.circle(f, (int(x), int(y)), int(rr), s["fill"], -1, cv2.LINE_AA); cv2.circle(f, (int(x), int(y)), int(rr), s["edge"], 4, cv2.LINE_AA)
            E.blit(f, s["lab"], x, y, scale=sc)
            if k == shield_i and v < v_end:
                cv2.circle(f, (int(x), int(y)), int(rr + 9), (255, 205, 70), 4, cv2.LINE_AA); E.blit(f, shield_lab, x, y - rr - 20)
        if rem == 2 and v < v_end:                                                 # photo-finish callout
            for k in inside:
                pr = 1 + .12 * math.sin(v * 14); cv2.circle(f, (int(CX + P[k, 0]), int(CY + P[k, 1])), int(r[k] * pr + 9), (255, 225, 120), 3, cv2.LINE_AA)
            E.blit(f, surv_sp, CX, CY - R - 36, alpha=.9)
        for (ve, k) in popups:                                                     # +SAFE popups
            age = v - ve
            if 0 <= age < 0.9:
                u = P[k] / max(np.hypot(*P[k]), 1); px, py = CX + u[0] * (R + 70), CY + u[1] * (R + 70) - 28 * E.smooth(age / .9)
                px = float(np.clip(px, 110, W - 110)); py = float(np.clip(py, 520, 1440))
                E.blit(f, E.text_sprite(f"{ents[k]['code']} SAFE", 34, sprites[k]["edge"], "bold", stroke=4, stroke_color=(0, 0, 0)), px, py, alpha=1 - E.smooth(age / .9), scale=.9 + .25 * E.out_back(age / .25))
        if v < v_end: E.blit(f, tag, W / 2, 292)
        E.blit(f, title, W / 2, 372)                  # header
        for (t0, t1, _, _), sp in zip(tracks, track_sp):
            if t0 <= v < t1: E.blit(f, sp, W / 2, 452, alpha=E.smooth((v - t0) / .25) * (1 - E.smooth((v - (t1 - .25)) / .25)))
        if out_sp is not None: E.blit(f, out_sp, W - 40, 292, anchor="r")
        last = np.max(v_esc[np.isfinite(v_esc) & (v_esc <= v)]) if np.any(np.isfinite(v_esc) & (v_esc <= v)) else -9
        pulse = 1 + .35 * max(0, 1 - (v - last) / .28)
        E.blit(f, lab_in, W / 2 - 150, 1530); E.blit(f, nums[rem], W / 2 + 130, 1532, scale=pulse)
        spd = float(np.interp(ts, ts_grid, sp_grid)); E.blit(f, E.text_sprite(f"SPEED ×{spd:.1f}", 28, (150, 160, 190), "bold"), W - 120, 1532)
        if v >= v_end:                                                              # result card
            u = v - v_end; a = E.smooth(u / .35); f[:1600] = cv2.convertScaleAbs(f[:1600], alpha=1 - .55 * a)
            k = loser if saved is None else saved; x, y = CX + P[k, 0], CY + P[k, 1]
            cv2.circle(f, (int(x), int(y)), int(r[k] + 10 + 5 * math.sin(u * 9)), card_col, 5, cv2.LINE_AA)
            sc = E.out_back(u / .45)
            E.pill(f, 40, 780, W - 40, 1440, (6, 6, 14), .72 * a)
            E.blit(f, elim_sp, W / 2, 845, alpha=a, scale=sc); E.blit(f, name_sp, W / 2, 985, alpha=a, scale=sc)
            E.blit(f, stat_sp, W / 2, 1078, alpha=E.smooth((u - .15) / .3))
            if saved_sp is not None: E.blit(f, saved_sp, W / 2, 1232, alpha=E.smooth((u - .6) / .3))
            E.blit(f, back_sp, W / 2, 1170, alpha=E.smooth((u - .5) / .3))
            c = E.smooth((u - 1.0) / .35); E.blit(f, cta_sp, W / 2, 1300, alpha=c); E.blit(f, cta2_sp, W / 2, 1352, alpha=c)
            E.arrow_down(f, W / 2, 1410 + 8 * math.sin(u * 7), 22, (255, 255, 255), alpha=c)
            E.blit(f, E.text_sprite(f"{series}  ·  DAY {day} FINAL", 30, (120, 220, 255), "bold", spacing=4), W / 2, 292)
        if final and v > total - LOOP:                                              # seamless loop: dissolve to frame 0
            f0 = draw(0, final=False); b = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - b, f0, b, 0)
        return f

    # ---------- audio (event driven: every sound is placed at the video time of the thing that caused it)
    mix = E.Mix(total); vt = lambda t_: float(np.interp(t_, ts_grid, tv_grid))
    mix.add(0.03, E.bell(float(E.midi_hz(88)), 1.0), .22)
    last_t, bins = {}, {}
    for (t_, i, sp_) in sim["wall"]:
        v = vt(t_)
        if v > v_end or v - last_t.get(i, -1) < .08: continue
        b = int(v * 12); 
        if bins.get(b, 0) >= 4: continue
        bins[b] = bins.get(b, 0) + 1; last_t[i] = v
        deg = int(np.interp(r[int(i)], [r.min(), r.max()], [11, 1])); mix.add(v, E.tick(float(E.midi_hz(E.penta(deg, 72))), .08), .06 * E.clamp(sp_ / 600, .3, 1.2), float(np.clip(P0 := hist[min(int(t_ / dt), len(hist) - 1)][int(i)][0] / R, -1, 1)) * .6)
    for (t_, i, j, sp_) in sim["ball"][::3]:
        v = vt(t_)
        if v > v_end or v - last_t.get(("b", int(i)), -1) < .1: continue
        b = int(v * 12)
        if bins.get(b, 0) >= 4: continue
        bins[b] = bins.get(b, 0) + 1; last_t[("b", int(i))] = v; mix.add(v, E.tick(float(E.midi_hz(55 + int(i) % 7 * 2)), .06), .03 * E.clamp(sp_ / 500, .3, 1.2))
    done = 0
    for k in np.argsort(v_esc):                                                    # one melody note per escape
        if not np.isfinite(v_esc[k]): continue
        x = hist[min(int(esc[k] / dt), len(hist) - 1)][k][0] / R
        note = E.ODE[done % len(E.ODE)]; done += 1
        mix.add(v_esc[k], E.kalimba(float(E.midi_hz(note + 12)), 1.1), .55, float(np.clip(x, -1, 1)) * .5)
        mix.add(v_esc[k], E.bell(float(E.midi_hz(note + 24)), 1.2), .10); mix.add(v_esc[k] - .02, E.whoosh(.3, int(k)), .07)
    v5 = vt(mt["t5"]); vtn = v5
    while vtn < v_end - .2:                                                       # accelerating heartbeat in the last 5
        mix.add(vtn, E.thump(.35, 240, 70), .55); mix.add(vtn, E.tick(1200, .03), .08)
        vtn += E.lerp(.62, .30, E.clamp((vtn - v5) / max(v_end - v5, 1e-3)))
    v3 = float(v_esc[np.argsort(v_esc)[N - 4]]) if N > 4 else v5
    ris = E.riser(max(v_end - v3, .5)); mix.add(v3, ris, .45)
    mix.add(v_end, E.thump(1.2, 120, 30), 1.0); mix.add(v_end, E.slide_down(1.1, 520, 140), .4)
    mix.add(v_end + .35, E.chord([57, 60, 64], 2.6), .35); mix.add(v_end + 1.1, E.bell(float(E.midi_hz(69)), 2.2), .15)
    wav = os.path.join(out_dir, spec["name"] + ".wav"); mix.write(wav)

    if stills:
        for t_ in stills:
            E.save_png(os.path.join(out_dir, f"{spec['name']}_still_{t_:05.2f}.png"), draw(int(t_ * FPS)))
        return dict(still_only=True)
    mp4 = os.path.join(out_dir, spec["name"] + ".mp4"); E.render(mp4, wav, n_frames, draw)
    E.save_png(os.path.join(out_dir, spec["name"] + "_cover.png"), draw(int(spec.get("cover_t", 0.9) * FPS)))
    return dict(saved=(ents[saved]['name'] if saved is not None else None), mp4=mp4, wav=wav, duration=total, frames=int(round(total * FPS)), eliminated=L, seed=seed, N=N,
                v_end=v_end, escapes=int(np.isfinite(v_esc).sum()))
