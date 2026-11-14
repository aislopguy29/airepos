"""LAB STYLE brick_siege: 1-vs-1 fortress breakout duel (DOG fort on top vs CAT fort on the bottom of a vertical arena).
Each core keeps launching balls; a ball flies through its own bricks, bounces off and smashes enemy bricks (1 hit, steel = 2),
BOMB bricks blow up their neighbours and chain into other bombs, x2 bricks split the ball. Opposing balls clash and bounce.
A ball that reaches the enemy core cracks it (-1 HP). First core to 0 loses; slow-mo final hit, then the losing fort
collapses in a chain reaction from its core outward. HUD = segmented core-HP bars above/below the arena. Pure physics +
chance: no data."""
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import engine as E
from engine import W, H, FPS

EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
TEAMS = [dict(name="DOG", emo="🐶", ball=(255, 158, 52), brick=(214, 92, 48), dark=(120, 44, 24), hud=(255, 190, 110)),
         dict(name="CAT", emo="🐱", ball=(70, 215, 255), brick=(70, 98, 220), dark=(30, 44, 120), hud=(150, 220, 255))]
COLS, ROWS, CS = 20, 25, 48
AX0, AY0 = 60, 380
AW, AH = COLS * CS, ROWS * CS                 # 960 x 1200 arena
FORT, CORE_C, CORE_R = 9, (8, 12), 3         # fort depth (rows), core cols [10,14), core depth
NORM, STEEL, BOMB, SPLIT, CORE = 0, 1, 2, 3, 9
BR, SPEED = 12, 900.0
T_GATE, LAUNCH, CAP, ENERGY, CORE_HP, FIRST = 1.6, 0.9, 12, 10, 8, 3
BLAST_R, CHAIN_DT = 2.25, 0.09


def lrow(team, lr): return lr if team == 0 else ROWS - 1 - lr


def layout(seed):
    rng = np.random.default_rng(seed * 13 + 5)
    owner = [[-1] * COLS for _ in range(ROWS)]; kind = [[NORM] * COLS for _ in range(ROWS)]; hp = [[0] * COLS for _ in range(ROWS)]
    for team in (0, 1):
        free = []
        for lr in range(FORT):
            for c in range(COLS):
                if lr == FORT - 1 and (c // 2) % 2 == 1: continue                      # merlons on the front row
                r = lrow(team, lr); owner[r][c] = team; hp[r][c] = 1
                if lr < CORE_R and CORE_C[0] <= c < CORE_C[1]: kind[r][c] = CORE
                elif (lr == CORE_R and CORE_C[0] - 1 <= c <= CORE_C[1]) or (lr < CORE_R and c in (CORE_C[0] - 1, CORE_C[1])):
                    kind[r][c] = STEEL; hp[r][c] = 2                                     # steel guard ring round the core
                else: free.append((r, c, lr))
        rng.shuffle(free); nb = ns = nst = 0
        for (r, c, lr) in free:
            if nb < 6 and 3 <= lr <= 7: kind[r][c] = BOMB; nb += 1
            elif ns < 4 and 4 <= lr <= 8: kind[r][c] = SPLIT; ns += 1
            elif nst < 10 and 1 <= lr <= 7: kind[r][c] = STEEL; hp[r][c] = 2; nst += 1
    return owner, kind, hp


def simulate(seed, dt=1 / 240, max_t=40.0):
    rng = np.random.default_rng(seed); owner, kind, hp = layout(seed)
    owner0 = [row[:] for row in owner]; kind0 = [row[:] for row in kind]
    dest = np.full((ROWS, COLS), np.inf); crack = np.full((ROWS, COLS), np.inf)
    core = [CORE_HP, CORE_HP]; ev = []; frames = []; balls = []; nid = [0]; blasts = []
    step = int(round(1 / (FPS * dt))); next_launch = T_GATE; tf = None; winner = None
    ccx = AX0 + (CORE_C[0] + CORE_C[1]) / 2 * CS

    def spawn(team, x, y, ang, t, why):
        vy = SPEED * math.cos(ang) * (1 if team == 0 else -1); vx = SPEED * math.sin(ang)
        balls.append([x, y, vx, vy, team, ENERGY, True, nid[0]]); ev.append(("spawn", t, team, x, y, nid[0], why)); nid[0] += 1

    def destroy(r, c, t, attacker, cause, depth=0):
        o = owner[r][c]; k = kind[r][c]; owner[r][c] = -1; dest[r, c] = t
        x, y = AX0 + (c + .5) * CS, AY0 + (r + .5) * CS
        ev.append(("brick", t, r, c, o, k, cause, depth))
        if k == BOMB: blasts.append((t + CHAIN_DT, r, c, o, attacker, depth + 1))
        if k == SPLIT and sum(1 for b in balls if b[6] and b[4] == attacker) < CAP + 3:
            spawn(attacker, x, y, rng.uniform(-.7, .7), t, "split")

    def hit_core(o, t, n_=1):
        nonlocal tf, winner
        if tf is not None: return
        core[o] = max(0, core[o] - n_); ev.append(("core", t, o, core[o]))
        if core[o] <= 0: tf = t; winner = 1 - o

    for s in range(int(max_t / dt)):
        t = s * dt
        if s % step == 0:
            frames.append((t, np.array([[b[0], b[1], b[4], b[7]] for b in balls if b[6]], float).reshape(-1, 4), tuple(core)))
        if tf is not None:
            if t > tf + 0.05: break
            continue
        if t < T_GATE: continue
        if t >= next_launch:                                                           # cores fire
            for team in (0, 1):
                if sum(1 for b in balls if b[6] and b[4] == team) < CAP:
                    y = AY0 + (CORE_R * CS + BR + 2 if team == 0 else AH - CORE_R * CS - BR - 2)
                    for j in range(FIRST if t < T_GATE + .01 else 1):
                        spawn(team, ccx + rng.uniform(-40, 40), y, rng.uniform(-.75, .75), t, "launch")
            next_launch += LAUNCH
        while blasts and min(b_[0] for b_ in blasts) <= t:                             # bomb chain reactions
            bl = min(blasts); blasts.remove(bl); _, br_, bc_, o, att, depth = bl
            ev.append(("blast", t, br_, bc_, o, depth)); core_hit = False
            for r in range(max(0, br_ - 3), min(ROWS, br_ + 4)):
                for c in range(max(0, bc_ - 3), min(COLS, bc_ + 4)):
                    if owner[r][c] != o or (r - br_) ** 2 + (c - bc_) ** 2 > BLAST_R ** 2: continue
                    if kind[r][c] == CORE: core_hit = True
                    else: destroy(r, c, t, att, "blast", depth)
            if core_hit: hit_core(o, t)
        live = [b for b in balls if b[6]]
        for b in live:
            x, y, vx, vy, team = b[0] + b[2] * dt, b[1] + b[3] * dt, b[2], b[3], b[4]; bounced = False
            if x < AX0 + BR: x = AX0 + BR; vx = abs(vx); bounced = True
            if x > AX0 + AW - BR: x = AX0 + AW - BR; vx = -abs(vx); bounced = True
            if y < AY0 + BR: y = AY0 + BR; vy = abs(vy); bounced = True
            if y > AY0 + AH - BR: y = AY0 + AH - BR; vy = -abs(vy); bounced = True
            en = 1 - team; best = None
            c0, c1 = max(0, int((x - BR - AX0) // CS)), min(COLS - 1, int((x + BR - AX0) // CS))
            r0, r1 = max(0, int((y - BR - AY0) // CS)), min(ROWS - 1, int((y + BR - AY0) // CS))
            for r in range(r0, r1 + 1):
                for c in range(c0, c1 + 1):
                    if owner[r][c] != en: continue
                    rx, ry = AX0 + c * CS, AY0 + r * CS
                    qx = min(max(x, rx), rx + CS); qy = min(max(y, ry), ry + CS); dx, dy = x - qx, y - qy; d2 = dx * dx + dy * dy
                    if d2 < BR * BR and (best is None or d2 < best[0]): best = (d2, r, c, dx, dy, qx, qy)
            if best:
                d2, r, c, dx, dy, qx, qy = best; d = math.sqrt(d2)
                if d < 1e-6: nx, ny = -vx / SPEED, -vy / SPEED
                else: nx, ny = dx / d, dy / d
                x, y = qx + nx * (BR + .5), qy + ny * (BR + .5); vn = vx * nx + vy * ny
                if vn < 0: vx -= 2 * vn * nx; vy -= 2 * vn * ny
                bounced = True
                if kind[r][c] == CORE: hit_core(en, t); b[5] -= 2; ev.append(("corehit", t, en, x, y))
                else:
                    hp[r][c] -= 1; b[5] -= 1
                    if hp[r][c] <= 0: destroy(r, c, t, team, "ball")
                    else: crack[r, c] = t; ev.append(("clank", t, r, c, en))
            if bounced:
                a = rng.uniform(-.05, .05); ca, sa = math.cos(a), math.sin(a); vx, vy = vx * ca - vy * sa, vx * sa + vy * ca
            sp = math.hypot(vx, vy) or 1.0; vx, vy = vx / sp * SPEED, vy / sp * SPEED
            if abs(vy) < .3 * SPEED:
                vy = math.copysign(.3 * SPEED, vy if vy else (1 if team == 0 else -1)); vx = math.copysign(math.sqrt(SPEED ** 2 - vy * vy), vx)
            b[0], b[1], b[2], b[3] = x, y, vx, vy
            if b[5] <= 0: b[6] = False; ev.append(("pop", t, team, x, y, b[7]))
        live = [b for b in balls if b[6]]                                                # opposing balls clash
        for i in range(len(live)):
            for j in range(i + 1, len(live)):
                p, q = live[i], live[j]
                if p[4] == q[4]: continue
                dx, dy = q[0] - p[0], q[1] - p[1]; d2 = dx * dx + dy * dy
                if 0 < d2 < 4 * BR * BR:
                    d = math.sqrt(d2); nx, ny = dx / d, dy / d; o_ = (2 * BR - d) / 2
                    p[0] -= nx * o_; p[1] -= ny * o_; q[0] += nx * o_; q[1] += ny * o_
                    rel = (q[2] - p[2]) * nx + (q[3] - p[3]) * ny
                    if rel < 0:
                        p[2] += rel * nx; p[3] += rel * ny; q[2] -= rel * nx; q[3] -= rel * ny
                        ev.append(("clash", t, (p[0] + q[0]) / 2, (p[1] + q[1]) / 2))
    if tf is None: return None
    return dict(frames=frames, ev=ev, dest=dest, crack=crack, owner0=owner0, kind0=kind0, tf=tf, winner=winner, T=frames[-1][0])


def drama(sim):
    hpt = [(e[1], e[2], e[3]) for e in sim["ev"] if e[0] == "core"]; cur = [CORE_HP, CORE_HP]; signs = []; w = sim["winner"]; deficit = 0
    for (t, o, h) in hpt:
        cur[o] = h; d = cur[1] - cur[0]
        if d: signs.append(1 if d > 0 else -1)
        deficit = max(deficit, cur[1 - w] - cur[w])
    changes = sum(1 for a, b in zip(signs, signs[1:]) if a != b)
    return changes, deficit, cur[w]


def pick(seed0, tries=40, log=print):
    best = None
    for seed in range(seed0, seed0 + tries):
        sim = simulate(seed)
        if not sim: continue
        ch, de, left = drama(sim); tf = sim["tf"]
        score = min(ch, 4) * .6 + min(de, 4) * .5 - left * .55 - abs(tf - 18) / 3
        ok = 12.5 <= tf <= 23 and left <= 4
        log(f"[brick_siege] seed {seed}: tf {tf:.1f}s winner {TEAMS[sim['winner']]['name']} left {left} changes {ch} deficit {de} score {score:.2f}{'' if ok else ' (x)'}")
        if ok and (best is None or score > best[0]): best = (score, seed, sim)
    assert best, "no good seed"
    return best[1], best[2]


_ec = {}
def emoji(ch, size):
    if (ch, size) in _ec: return _ec[(ch, size)]
    f = ImageFont.truetype(EMOJI, 109); im = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((90, 90), ch, font=f, embedded_color=True, anchor="mm")
    im = im.crop(im.getbbox()); s = size / max(im.size)
    im = im.resize((max(1, int(im.size[0] * s)), max(1, int(im.size[1] * s))), Image.LANCZOS)
    a = np.array(im); _ec[(ch, size)] = a; return a


def rrect(img, x0, y0, x1, y1, rad, color):
    x0, y0, x1, y1, rad = int(x0), int(y0), int(x1), int(y1), int(rad)
    cv2.rectangle(img, (x0 + rad, y0), (x1 - rad, y1), color, -1); cv2.rectangle(img, (x0, y0 + rad), (x1, y1 - rad), color, -1)
    for cx, cy in ((x0 + rad, y0 + rad), (x1 - rad, y0 + rad), (x0 + rad, y1 - rad), (x1 - rad, y1 - rad)):
        cv2.circle(img, (cx, cy), rad, color, -1, cv2.LINE_AA)


def fort_art(owner0, kind0, seed):
    """Arena-local brick art + cell index map (sentinel ROWS*COLS = never a brick) + per-cell colour."""
    rng = np.random.default_rng(seed + 77)
    img = np.zeros((AH, AW, 3), np.uint8); idx = np.full((AH, AW), ROWS * COLS, np.int32); col = {}
    x2 = E.text_sprite("x2", 26, (40, 25, 5), "black")
    for r in range(ROWS):
        for c in range(COLS):
            o, k = owner0[r][c], kind0[r][c]
            if o < 0 or k == CORE: continue
            tm = TEAMS[o]; x0, y0 = c * CS + 2, r * CS + 2; x1, y1 = x0 + CS - 4, y0 + CS - 4
            if k == STEEL: base = tuple(int(.55 * a + .45 * b) for a, b in zip((150, 160, 178), tm["brick"]))
            elif k == BOMB: base = E.mulc(tm["dark"], 1.05)
            elif k == SPLIT: base = (246, 196, 64)
            else: base = E.mulc(tm["brick"], rng.uniform(.8, 1.12))
            col[(r, c)] = base
            rrect(img, x0, y0, x1 - 1, y1 - 1, 5, base)
            cv2.rectangle(img, (x0 + 4, y0 + 3), (x1 - 5, y0 + 7), E.mulc(base, 1.35), -1)            # bevel highlight
            cv2.rectangle(img, (x0 + 4, y1 - 7), (x1 - 5, y1 - 4), E.mulc(base, .62), -1)              # bevel shadow
            if k == NORM:                                                                              # stone texture
                cv2.line(img, (x0 + 5, (y0 + y1) // 2), (x1 - 6, (y0 + y1) // 2), E.mulc(base, .78), 2, cv2.LINE_AA)
                xm = x0 + int(rng.uniform(.3, .7) * (x1 - x0)); cv2.line(img, (xm, y0 + 8), (xm, (y0 + y1) // 2), E.mulc(base, .78), 2, cv2.LINE_AA)
            elif k == STEEL:
                for (px, py) in ((x0 + 9, y0 + 11), (x1 - 10, y0 + 11), (x0 + 9, y1 - 12), (x1 - 10, y1 - 12)):
                    cv2.circle(img, (px, py), 3, E.mulc(base, .55), -1, cv2.LINE_AA); cv2.circle(img, (px - 1, py - 1), 1, (235, 240, 250), -1)
                cv2.line(img, (x0 + 10, y1 - 16), (x1 - 16, y0 + 10), E.mulc(base, 1.25), 3, cv2.LINE_AA)
            elif k == BOMB:
                cx, cy = (x0 + x1) // 2, (y0 + y1) // 2 + 3
                cv2.circle(img, (cx, cy), 13, (28, 26, 34), -1, cv2.LINE_AA); cv2.circle(img, (cx - 4, cy - 4), 4, (120, 120, 140), -1, cv2.LINE_AA)
                cv2.line(img, (cx + 7, cy - 10), (cx + 13, cy - 16), (200, 170, 120), 3, cv2.LINE_AA)
                cv2.circle(img, (cx + 14, cy - 17), 4, (255, 210, 60), -1, cv2.LINE_AA); cv2.circle(img, (cx + 14, cy - 17), 2, (255, 255, 230), -1)
            elif k == SPLIT:
                h_, w_ = x2.shape[:2]; px, py = (x0 + x1) // 2 - w_ // 2, (y0 + y1) // 2 - h_ // 2
                a_ = x2[..., 3:4].astype(np.float32) / 255; roi = img[py:py + h_, px:px + w_]
                roi[:] = (roi * (1 - a_) + x2[..., :3] * a_).astype(np.uint8)
            idx[y0:y1, x0:x1] = r * COLS + c
    return img, idx, col


def core_sprite(team):
    tm = TEAMS[team]; w_, h_ = 4 * CS - 10, 3 * CS - 10
    spr = np.zeros((h_, w_, 4), np.uint8); rrect(spr, 0, 0, w_ - 1, h_ - 1, 18, (*tm["ball"], 255))
    rrect(spr, 5, 5, w_ - 6, h_ - 6, 14, (*E.mulc(tm["dark"], .9), 255))
    em = emoji(tm["emo"], 104); eh, ew = em.shape[:2]; px, py = (w_ - ew) // 2, (h_ - eh) // 2
    a = em[..., 3:4].astype(np.float32) / 255; roi = spr[py:py + eh, px:px + ew]
    roi[..., :3] = (roi[..., :3] * (1 - a) + em[..., :3] * a).astype(np.uint8)
    return spr


def make_bg():
    bg = E.make_bg(top=(10, 10, 26), bottom=(12, 8, 30), glow=(36, 30, 70))
    ar = bg[AY0:AY0 + AH, AX0:AX0 + AW].astype(np.float32) * .55
    yy = np.linspace(0, 1, AH, dtype=np.float32)[:, None]
    warm = np.array((70, 34, 18), np.float32); cool = np.array((16, 30, 78), np.float32)
    tint = np.clip(1 - yy * 2, 0, 1)[..., None] * warm + np.clip(yy * 2 - 1, 0, 1)[..., None] * cool
    ar = ar + tint * .55
    bg[AY0:AY0 + AH, AX0:AX0 + AW] = np.clip(ar, 0, 255).astype(np.uint8)
    for c in range(COLS + 1): cv2.line(bg, (AX0 + c * CS, AY0), (AX0 + c * CS, AY0 + AH), (34, 32, 56), 1)
    for r in range(ROWS + 1): cv2.line(bg, (AX0, AY0 + r * CS), (AX0 + AW, AY0 + r * CS), (34, 32, 56), 1)
    ym = AY0 + AH // 2
    for x in range(AX0 + 10, AX0 + AW, 44): cv2.line(bg, (x, ym), (x + 22, ym), (120, 110, 160), 3, cv2.LINE_AA)
    cv2.rectangle(bg, (AX0 - 6, AY0 - 6), (AX0 + AW + 5, AY0 + AH + 5), (150, 140, 210), 4, cv2.LINE_AA)
    return bg


def build(out_mp4, seed=1, ep=1, log=print, stills=None):
    seed, sim = pick(seed, log=log); fr = sim["frames"]; tf = sim["tf"]; win = sim["winner"]; lose = 1 - win
    owner0, kind0 = sim["owner0"], sim["kind0"]; ev = list(sim["ev"]); dest = sim["dest"].copy(); crack = sim["crack"]
    ccy = [AY0 + CORE_R * CS / 2, AY0 + AH - CORE_R * CS / 2]; ccx = AX0 + (CORE_C[0] + CORE_C[1]) / 2 * CS
    # ---- the losing fort collapses in a chain reaction from its core outward
    T_COL = tf + .3; col_ev = []
    for r in range(ROWS):
        for c in range(COLS):
            if owner0[r][c] == lose and kind0[r][c] != CORE and not np.isfinite(dest[r, c]):
                d = math.hypot(AX0 + (c + .5) * CS - ccx, AY0 + (r + .5) * CS - ccy[lose]) / CS
                dest[r, c] = T_COL + d * .05; col_ev.append(("brick", dest[r, c], r, c, lose, kind0[r][c], "collapse", 0))
    ev += col_ev; t_col_end = max([e[1] for e in col_ev] or [T_COL])
    S, s0, s1 = .3, tf - .55, tf + .2                                                    # slow-mo final hit
    v1 = s0 + (s1 - s0) / S; vf = s0 + (tf - s0) / S
    def sim_t(v): return v if v < s0 else s0 + (v - s0) * S if v < v1 else s1 + (v - v1)
    def vid_t(t): return t if t < s0 else s0 + (t - s0) / S if t < s1 else v1 + (t - s1)
    v_end = vid_t(max(t_col_end, tf + .9) + .45); CARD = 3.7; total = v_end + CARD; n = int(round(total * FPS)); LOOP = .35
    hp_at = lambda t, o: min([CORE_HP] + [e[3] for e in ev if e[0] == "core" and e[2] == o and e[1] <= t])
    log(f"[brick_siege] seed {seed}: final hit {tf:.1f}s, video {total:.1f}s, winner {TEAMS[win]['name']} ({hp_at(tf, win)} HP left)")
    # ---- chains of bomb blasts (for callouts)
    chains = []; cur = None
    for e in sorted([e for e in ev if e[0] == "blast"], key=lambda e: e[1]):
        if cur and e[4] == cur["o"] and e[5] > 0 and e[1] - cur["t1"] < .2: cur["n"] += 1; cur["t1"] = e[1]; cur["pos"] = (e[2], e[3])
        else:
            cur = dict(o=e[4], n=1, t1=e[1], pos=(e[2], e[3])); chains.append(cur)
    chains = [ch for ch in chains if ch["n"] >= 3]
    crit = {}
    for e in ev:
        if e[0] == "core" and e[3] <= 2 and e[3] > 0 and e[2] not in crit: crit[e[2]] = e[1]
    # ---- precomputed art
    bg = make_bg(); fort, cidx, bcol = fort_art(owner0, kind0, seed); cores = [core_sprite(0), core_sprite(1)]
    dflat = np.append(dest.reshape(-1), -np.inf)
    crng = np.random.default_rng(seed + 5); cracks = []
    for team in (0, 1):
        lines = []
        for k in range(CORE_HP):
            a = crng.uniform(0, 2 * math.pi); pts = [(crng.uniform(-14, 14), crng.uniform(-10, 10))]
            for j in range(3): a += crng.uniform(-.7, .7); rr = 22 + j * 24; pts.append((pts[0][0] + rr * math.cos(a) * 1.25, pts[0][1] + rr * math.sin(a) * .8))
            lines.append(np.array(pts))
        cracks.append(lines)
    steel_cr = {}
    for r in range(ROWS):
        for c in range(COLS):
            if np.isfinite(crack[r, c]):
                x0, y0 = AX0 + c * CS, AY0 + r * CS
                steel_cr[(r, c)] = np.array([[x0 + 10, y0 + 12], [x0 + 22, y0 + 24], [x0 + 18, y0 + 34], [x0 + 32, y0 + 40]], np.int32)
    bombs = [(r, c) for r in range(ROWS) for c in range(COLS) if kind0[r][c] == BOMB]
    ball_spr = {}
    for team in (0, 1):
        s_ = np.zeros((2 * BR + 6, 2 * BR + 6, 4), np.uint8); cc = BR + 3
        cv2.circle(s_, (cc, cc), BR + 2, (255, 255, 255, 255), -1, cv2.LINE_AA); cv2.circle(s_, (cc, cc), BR - 1, (*TEAMS[team]["ball"], 255), -1, cv2.LINE_AA)
        cv2.circle(s_, (cc - 3, cc - 4), 3, (255, 255, 255, 230), -1, cv2.LINE_AA); ball_spr[team] = s_
    def balls_at(t):
        g = min(t, fr[-1][0]) * FPS; i0 = min(len(fr) - 2, int(g)); w = min(1.0, g - i0)
        A, B = fr[i0][1], fr[i0 + 1][1]; out = []
        bmap = {int(b[3]): b for b in B}
        for a in A:
            b = bmap.get(int(a[3])); x, y = (a[0], a[1]) if b is None else (a[0] + (b[0] - a[0]) * w, a[1] + (b[1] - a[1]) * w)
            out.append((x, y, int(a[2]), int(a[3])))
        return out
    tag = E.text_sprite(f"BRICK SIEGE  ·  #{ep}", 28, (200, 190, 255), "bold", spacing=4)
    band = np.ones((H, 1, 1), np.float32); band[:376] = .2; band[1584:] = .2
    def hud(f, t, v, team, y):
        tm = TEAMS[team]; hp = hp_at(t, team); E.blit(f, emoji(tm["emo"], 62), 104, y)
        E.blit(f, E.text_sprite(tm["name"], 40, tm["hud"], "black", stroke=3, stroke_color=(0, 0, 0)), 145, y, anchor="l")
        x0, x1, gap = 268, 930, 8; sw = (x1 - x0 - gap * (CORE_HP - 1)) / CORE_HP
        lost_t = {e[3]: e[1] for e in ev if e[0] == "core" and e[2] == team}
        for k in range(CORE_HP):
            a, b = int(x0 + k * (sw + gap)), int(x0 + k * (sw + gap) + sw)
            if k < hp: rrect(f, a, y - 17, b, y + 17, 8, tm["ball"]); cv2.rectangle(f, (a + 6, y - 13), (b - 6, y - 9), E.mulc(tm["ball"], 1.4), -1)
            else:
                lt = lost_t.get(k, -9); age = v - vid_t(lt)
                rrect(f, a, y - 17, b, y + 17, 8, (255, 255, 255) if 0 <= age < .25 else (52, 48, 66))
        hs = E.text_sprite(str(hp), 44, (255, 255, 255) if hp > 2 else (255, 90, 90), "black", stroke=3, stroke_color=(0, 0, 0))
        last = max([vid_t(tt) for kk, tt in lost_t.items() if tt <= t] or [-9]); pa = v - last
        E.blit(f, hs, 982, y, scale=1 + (.45 * (1 - E.smooth(pa / .35)) if 0 <= pa < .35 else 0))
    def middle(f, txt, size, col, y=980, alpha=1.0, bgc=(0, 0, 0), scale=1.0):
        spr = E.text_sprite(txt, size, col, "black", stroke=5, stroke_color=(0, 0, 0))
        E.pill(f, W / 2 - spr.shape[1] / 2 * scale - 34, y - spr.shape[0] / 2 * scale - 8, W / 2 + spr.shape[1] / 2 * scale + 34, y + spr.shape[0] / 2 * scale + 8, bgc, .62 * alpha)
        E.blit(f, spr, W / 2, y, alpha=alpha, scale=scale)
    def draw(i, final=True):
        v = i / FPS; t = sim_t(min(v, v_end)); f = bg.copy()
        reg = f[AY0:AY0 + AH, AX0:AX0 + AW]; m = (dflat > t)[cidx]; reg[m] = fort[m]
        for (r, c), pts in steel_cr.items():
            if crack[r, c] <= t < dest[r, c]: cv2.polylines(f, [pts], False, (25, 25, 35), 3, cv2.LINE_AA)
        glow = np.zeros((H // 2, W // 2, 3), np.uint8)
        for (r, c) in bombs:
            if dest[r, c] > t:
                pu = .5 + .5 * math.sin(t * 7 + r + c); cv2.circle(glow, (int((AX0 + c * CS + 38) / 2), int((AY0 + r * CS + 12) / 2)), 5, (int(255 * pu), int(120 * pu), 30), -1)
        for team in (0, 1):                                                                       # cores
            hp = hp_at(t, team); cy = ccy[team]
            if team == lose and t >= tf: continue
            lt = max([e[1] for e in ev if e[0] == "core" and e[2] == team and e[1] <= t] or [-9]); age = t - lt
            dx = 8 * math.sin(age * 60) * math.exp(-age * 9) if age < .5 else 0
            E.blit(f, cores[team], ccx + dx, cy)
            for k in range(CORE_HP - hp):
                pts = (cracks[team][k] + [ccx + dx, cy]).astype(np.int32)
                cv2.polylines(f, [pts], False, (20, 10, 10), 5, cv2.LINE_AA); cv2.polylines(f, [pts], False, (255, 240, 220), 1, cv2.LINE_AA)
            if age < .18:
                ov = f[int(cy - 68):int(cy + 68), int(ccx - 91 + dx):int(ccx + 91 + dx)]; a_ = .6 * (1 - age / .18)
                ov[:] = (ov * (1 - a_) + 255 * a_).astype(np.uint8)
            if hp <= 2: cv2.circle(glow, (int(ccx / 2), int(cy / 2)), 60, (int(160 * (.5 + .5 * math.sin(v * 10))), 20, 20), -1)
        if t >= tf:                                                                               # losing core shatters
            age = t - tf; cy = ccy[lose]; rr = np.random.default_rng(seed + 9)
            for k in range(26):
                a = rr.uniform(0, 2 * math.pi); sp = rr.uniform(200, 900); d = sp * (1 - math.exp(-3 * age)) / 3
                sz = max(0, int(rr.uniform(10, 22) * (1 - age / 1.6)))
                if sz: x, y = ccx + math.cos(a) * d, cy + math.sin(a) * d; cv2.rectangle(f, (int(x - sz), int(y - sz)), (int(x + sz), int(y + sz)), TEAMS[lose]["ball"] if k % 2 else TEAMS[lose]["dark"], -1)
            if age < .9: cv2.circle(glow, (int(ccx / 2), int(cy / 2)), int(40 + 260 * E.smooth(age / .9)), (255, 230, 180), int(max(1, 30 * (1 - age / .9))))
            if age < .3: cv2.circle(glow, (int(ccx / 2), int(cy / 2)), 120, (255, 255, 255), -1)
        for e in ev:                                                                              # debris / blasts / sparks
            age = t - e[1]
            if e[0] == "brick" and 0 <= age < .7:
                r, c = e[2], e[3]; x0, y0 = AX0 + (c + .5) * CS, AY0 + (r + .5) * CS; rr = np.random.default_rng(r * 31 + c)
                col = bcol.get((r, c), (200, 200, 200))
                for k in range(3 if e[6] == "collapse" else 5):
                    a = rr.uniform(0, 2 * math.pi); sp = rr.uniform(120, 420); d = sp * (1 - math.exp(-5 * age)) / 5
                    sz = int(rr.uniform(5, 10) * (1 - age / .7)) + 1; x, y = x0 + math.cos(a) * d, y0 + math.sin(a) * d
                    cv2.rectangle(f, (int(x - sz), int(y - sz)), (int(x + sz), int(y + sz)), col, -1)
                if age < .12: cv2.rectangle(glow, (int((x0 - 22) / 2), int((y0 - 22) / 2)), (int((x0 + 22) / 2), int((y0 + 22) / 2)), (255, 240, 200), -1)
            elif e[0] == "blast" and 0 <= age < .45:
                x0, y0 = AX0 + (e[3] + .5) * CS, AY0 + (e[2] + .5) * CS; rad = BLAST_R * CS * (.3 + .9 * E.smooth(age / .3))
                cv2.circle(f, (int(x0), int(y0)), int(rad), (255, 220, 150), max(1, int(8 * (1 - age / .45))), cv2.LINE_AA)
                cv2.circle(glow, (int(x0 / 2), int(y0 / 2)), int(rad / 2), (255, 140, 40), -1 if age < .15 else max(1, int(10 * (1 - age / .45))))
            elif e[0] == "clash" and 0 <= age < .2:
                x0, y0 = e[2], e[3]; L = 10 + 40 * age / .2
                for a in (0, 1.05, 2.1):
                    cv2.line(f, (int(x0 - L * math.cos(a)), int(y0 - L * math.sin(a))), (int(x0 + L * math.cos(a)), int(y0 + L * math.sin(a))), (255, 255, 255), 2, cv2.LINE_AA)
        shrink = 1.0 if t < tf else max(0.0, 1 - (t - tf) / .4)
        if shrink > 0:                                                                            # balls + trails
            for k in range(6, 0, -1):
                for (x, y, team, _) in balls_at(max(0, t - k * .011)):
                    cv2.circle(f, (int(x), int(y)), max(1, int(BR * (1 - k / 7) * shrink)), E.mulc(TEAMS[team]["ball"], .35 + .5 * (1 - k / 7)), -1, cv2.LINE_AA)
            for (x, y, team, _) in balls_at(t):
                E.blit(f, ball_spr[team], x, y, scale=shrink); cv2.circle(glow, (int(x / 2), int(y / 2)), 9, TEAMS[team]["ball"], -1)
        E.add_glow(f, glow, 8, 1.0)
        for e in ev:                                                                              # small pops
            age = v - vid_t(e[1])
            if e[0] == "core" and 0 <= age < .8 and e[1] <= tf:
                y = ccy[e[2]] + (110 if e[2] == 0 else -110) + (-60 if e[2] == 1 else 60) * age
                E.blit(f, E.text_sprite("-1", 54, (255, 80, 80), "black", stroke=5, stroke_color=(0, 0, 0)), ccx + 120, y, alpha=1 - E.smooth((age - .55) / .25), scale=E.out_back(age / .2))
            elif e[0] == "spawn" and e[6] == "split" and 0 <= age < .6:
                E.blit(f, E.text_sprite("x2!", 40, (255, 215, 80), "black", stroke=4, stroke_color=(0, 0, 0)), e[3], e[4] - 30 - 40 * age, alpha=1 - E.smooth((age - .4) / .2))
        for ch in chains:
            age = v - vid_t(ch["t1"])
            if 0 <= age < 1.0:
                r, c = ch["pos"]; y = float(np.clip(AY0 + (r + .5) * CS, 560, 1400))
                E.blit(f, E.text_sprite(f"CHAIN x{ch['n']}!", 58, (255, 170, 60), "black", stroke=6, stroke_color=(0, 0, 0)), W / 2, y,
                       alpha=1 - E.smooth((age - .75) / .25), scale=E.out_back(age / .25))
        f[:] = (f * band).astype(np.uint8)                                                        # HUD bands
        E.blit(f, tag, W / 2, 266); hud(f, t, v, 0, 328); hud(f, t, v, 1, 1632)
        if v < T_GATE:                                                                            # hook
            a_ = E.smooth(v / .2); E.pill(f, 90, 846, W - 90, 1124, (0, 0, 0), .7 * a_)
            vs = E.text_sprite("DOG  VS  CAT", 92, (255, 255, 255), "black", stroke=6, stroke_color=(0, 0, 0))
            E.blit(f, vs, W / 2, 920, alpha=a_, scale=E.out_back(v / .3))
            E.blit(f, emoji("🐶", 84), W / 2 - vs.shape[1] / 2 - 56, 920, alpha=a_); E.blit(f, emoji("🐱", 84), W / 2 + vs.shape[1] / 2 + 56, 920, alpha=a_)
            E.blit(f, E.text_sprite("FIRST TO CRACK THE OTHER CORE WINS", 36, (255, 230, 140), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1012, alpha=E.smooth((v - .15) / .25))
            E.blit(f, E.text_sprite("PICK YOUR SIDE NOW", 40, (150, 255, 190), "black", stroke=4, stroke_color=(0, 0, 0)), W / 2, 1076, alpha=E.smooth((v - .5) / .25) * (.75 + .25 * math.sin(v * 12)))
        elif v < T_GATE + .6:
            u = (v - T_GATE) / .6; E.blit(f, E.text_sprite("SIEGE!", 130, (255, 215, 80), "black", stroke=8, stroke_color=(0, 0, 0)), W / 2, 980, alpha=1 - E.smooth((u - .5) / .5), scale=E.out_back(u / .4))
        elif v < 4.4: middle(f, "WHO CRACKS FIRST?", 48, (255, 255, 255), 980, E.smooth((v - T_GATE - .6) / .2) * (1 - E.smooth((v - 4.1) / .3)))
        for team, tc in crit.items():
            age = v - vid_t(tc)
            if 0 <= age < 1.4 and vid_t(tc) < s0: middle(f, f"{TEAMS[team]['name']} CORE CRITICAL!", 50, (255, 110, 110), 980, 1 - E.smooth((age - 1.1) / .3), (90, 0, 0))
        if s0 <= v < vf: middle(f, "FINAL HIT", 64, (255, 215, 80), 980, .75 + .25 * math.sin(v * 12) ** 2, (90, 0, 0))
        elif vf <= v < v_end: middle(f, f"{TEAMS[lose]['name']} CORE BROKEN!", 60, (255, 255, 255), 980, 1 - E.smooth((v - v_end + .3) / .3), (120, 0, 0), E.out_back((v - vf) / .3))
        if vid_t(tf) <= v < vid_t(tf) + .45:                                                     # impact shake
            k_ = (1 - (v - vid_t(tf)) / .45) * 16; f = np.roll(f, (int(k_ * math.sin(v * 70)), int(k_ * math.cos(v * 53))), (0, 1))
        if v >= v_end: card(f, v - v_end)
        if final and v > total - LOOP:
            bb = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - bb, draw(0, False), bb, 0)
        return f
    def card(f, u):
        a_ = E.smooth(u / .3); f[:] = cv2.convertScaleAbs(f, alpha=1 - .82 * a_); tw, tl = TEAMS[win], TEAMS[lose]
        E.blit(f, emoji(tw["emo"], 230), W / 2, 640, alpha=a_, scale=E.out_back(u / .45))
        E.blit(f, E.text_sprite(f"TEAM {tw['name']} WINS", 92, (255, 255, 255), "black", stroke=7, stroke_color=(0, 0, 0)), W / 2, 850, alpha=a_, scale=E.out_back((u - .1) / .4))
        E.blit(f, E.text_sprite(f"CORE SURVIVED WITH {hp_at(tf, win)} HP", 38, tw["hud"], "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 940, alpha=E.smooth((u - .45) / .3))
        E.blit(f, E.text_sprite(f"THE {tl['name']} FORT COLLAPSED", 34, (200, 200, 215), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 994, alpha=E.smooth((u - .65) / .3))
        E.blit(f, E.text_sprite("TEAM DOG OR TEAM CAT?", 52, (150, 255, 190), "black", stroke=5, stroke_color=(0, 0, 0)), W / 2, 1160, alpha=E.smooth((u - 1.0) / .3), scale=E.out_back((u - 1.0) / .35))
        E.blit(f, E.text_sprite("WHO TAKES THE REMATCH?", 36, (255, 230, 140), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1232, alpha=E.smooth((u - 1.35) / .3))
    # ---- audio: soft chiptune bed (A mixolydian, 112 bpm), brick blips pitched by depth, bomb booms, core thuds
    mix = E.Mix(total, mood="chiptune", bpm=112, root=57, scale="mixolydian"); hz = lambda m_: float(E.midi_hz(m_))
    beat = 60 / 112
    for j in range(3): mix.add(j * beat * .9, E.pulse(hz(69 + 5 * j), .12, .5, 18), .3)
    mix.add(T_GATE, E.chord([69, 73, 76, 81], 1.0, E.bell), .45); mix.add(T_GATE, E.thump(.5, 140, 40), .7); mix.add(T_GATE - .25, E.whoosh(.35), .35)
    mix.bed(T_GATE, s0, gain=.2, seed=seed, intensity=lambda tt: E.clamp((tt - T_GATE) / max(1, s0 - T_GATE) * 1.1))
    per = {}
    def ok(vt, cap=3):
        b = int(vt * 25)
        if per.get(b, 0) >= cap: return False
        per[b] = per.get(b, 0) + 1; return True
    for e in ev:
        vt = vid_t(e[1])
        if vt >= v_end: continue
        if e[0] == "brick" and e[6] != "collapse" and ok(vt):
            lr = e[2] if e[4] == 0 else ROWS - 1 - e[2]; pan = ((e[3] + .5) / COLS - .5) * 1.2
            mix.add(vt, E.pulse(hz(mix.scale_note(FORT - lr + 2, 1)), .11, .5, 26), .2, pan)
        elif e[0] == "clank" and ok(vt): mix.add(vt, E.triangle(hz(mix.scale_note(9, 1)), .09, 30), .25); mix.add(vt, E.tick(3200, .03), .08)
        elif e[0] == "blast" and ok(vt, 4): mix.add(vt, E.thump(.45, 120, 34), .5); mix.add(vt, E.whoosh(.28, int(e[1] * 100) % 50), .25)
        elif e[0] == "core" and e[1] < tf: mix.add(vt, E.thump(.35, 210, 55), .6); mix.add(vt, E.bell(hz(45 + 12 * e[2]), .6), .3)
        elif e[0] == "spawn" and e[6] == "split" and ok(vt): mix.add(vt, E.pulse(hz(81), .07, .25, 30), .2); mix.add(vt + .07, E.pulse(hz(88), .09, .25, 26), .2)
        elif e[0] == "clash" and ok(vt, 2): mix.add(vt, E.tick(2600, .04), .1)
    mix.add(max(0, s0 - 1.8), E.riser(1.8 + (v1 - s0) * .6, 200, 2400), .32)
    vf = vid_t(tf); mix.add(vf, E.thump(1.3, 110, 26), 1.0); mix.add(vf, E.whoosh(.8, 21), .55); mix.add(vf, E.chord([45, 52, 57], 1.4, E.saw), .4)
    for k, e in enumerate(sorted(col_ev, key=lambda e: e[1])[::4][:28]):
        mix.add(vid_t(e[1]), E.pulse(hz(mix.scale_note(14 - k // 2, 1)), .09, .5, 26), .16, ((e[3] + .5) / COLS - .5))
    for j, m_ in enumerate([69, 73, 76, 81, 85]): mix.add(v_end + .15 + j * .1, E.pulse(hz(m_), .22, .5, 9), .3)
    mix.add(v_end + .7, E.chord([57, 64, 69, 73, 79], 2.8, E.bell), .5)
    wav = out_mp4[:-4] + ".wav"; mix.write(wav, peak=.82)
    if stills:
        for t_ in stills: E.save_png(out_mp4[:-4] + f"_still_{t_:05.2f}.png", draw(min(n - 1, int(t_ * FPS)), False))
        return dict(total=total, v_end=v_end, s0=s0, v1=v1, vf=vf, crit={TEAMS[k]["name"]: vid_t(x) for k, x in crit.items()},
                    chains=[(vid_t(c["t1"]), c["n"]) for c in chains])
    E.render(out_mp4, wav, n, draw); os.remove(wav)
    ch_, de_, left = drama(sim); tw, tl = TEAMS[win], TEAMS[lose]
    title = f"Dog Fort vs Cat Fort: Whose Core Cracks First? | Brick Siege #{ep}"
    desc = ("Two forts, two cores, nonstop bouncing balls.\n\nThe dog fort sits on top, the cat fort on the bottom. Every ball smashes enemy bricks, "
            "bombs set off chain reactions and gold bricks split a ball in two. First core to hit zero loses its whole fort.\n\n"
            "Team Dog or Team Cat? 👇\n\n#shorts #dogvscat #brickbreaker #chainreaction #satisfying")
    return dict(title=title, description=desc, tags=["dog vs cat", "brick breaker", "chain reaction", "satisfying", "physics simulation", "fortress battle"],
                duration=total, winner=TEAMS[win]["name"], loser=TEAMS[lose]["name"], winner_hp_left=left, lead_changes=ch_,
                max_deficit_overcome=de_, final_hit_s=round(vf, 2), chain_reactions=len(chains), seed=seed, thumb_ms=int(T_GATE * 1000 - 400))


if __name__ == "__main__":                     # python3 -I lab/styles/brick_siege.py <out.mp4> <seed> [episode]
    import json
    out = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1; ep = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    res = build(out, seed, ep=ep, log=lambda *a: print(*a, file=sys.stderr)); print("RESULT=" + json.dumps(res, default=float))
