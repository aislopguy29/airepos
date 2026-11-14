"""LAB STYLE snake_duel: 1-vs-1 snake race on a neon grid. FIRE (favorite, starts 2 longer) vs ICE (underdog).
Both snakes hunt the same glowing orbs; every bite is +1 length, a mid-race STAR is +4. Crash into a wall or a body and you
BONK: you lose 40% of your length and the lost tail spills as crumbs your rival can eat. First snake to GOAL length wins.
Layout: top title + live status line, 20x22 arena, two race-lane progress bars at the bottom. Slow-mo final bite, winner
card, loop blend. Seed-searched for lead changes, a late crash and a close finish. Pure simulation, no data, no branding."""
import os, sys, math, bisect
from collections import deque
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import engine as E
from engine import W, H, FPS

EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
TEAMS = [dict(name="FIRE", emo="🔥", col=(255, 104, 40), lite=(255, 206, 110), deep=(170, 24, 18), role="FAVORITE", start=6),
         dict(name="ICE", emo="🧊", col=(70, 190, 255), lite=(205, 245, 255), deep=(24, 70, 170), role="UNDERDOG", start=4)]
COLS, ROWS, CS = 20, 22, 48
AX0, AY0 = 60, 452
AW, AH = COLS * CS, ROWS * CS                    # 960 x 1056 -> arena y 452..1508
GOAL, N_ORB, STAR_VAL, STUN, T_GATE = 30, 6, 4, .55, 1.8
STAR_AT = (7.5, 12.5)                            # sim seconds after the gate (jittered by seed)
DIRS = [(0, 1), (1, 0), (0, -1), (-1, 0)]
LANE_Y = (1572, 1634)
BX0, BX1 = 132, 900


def inb(c): return 0 <= c[0] < ROWS and 0 <= c[1] < COLS
def px(c): return AX0 + (c[1] + .5) * CS, AY0 + (c[0] + .5) * CS


def bfs(start, blocked, orbs):
    """distance-weighted best orb from start (stars count as much closer) and reachable cell count."""
    if start in orbs:
        k = orbs[start][0]; return (0 - (8 if k == "star" else 0)), 999
    seen = {start}; q = deque([(start, 0)]); best = 1e9
    while q:
        c, d = q.popleft()
        for dr, dc in DIRS:
            nc = (c[0] + dr, c[1] + dc)
            if nc in seen or not inb(nc) or nc in blocked: continue
            seen.add(nc)
            if nc in orbs:
                sc = d + 1 - (8 if orbs[nc][0] == "star" else 0)
                if sc < best: best = sc
            q.append((nc, d + 1))
    return best, len(seen)


def simulate(seed):
    rng = np.random.default_rng(seed)
    bodies = [[(3, 7 - k) for k in range(TEAMS[0]["start"])], [(ROWS - 4, COLS - 6 + k) for k in range(TEAMS[1]["start"])]]
    grow = [0, 0]; stun = [-1.0, -1.0]; was_stun = [False, False]
    perr = [float(rng.uniform(.012, .03)), float(rng.uniform(.012, .03))]
    orbs = {}; ev = []; snaps = []
    stars = [T_GATE + STAR_AT[0] + float(rng.uniform(-1.2, 1.2)), T_GATE + STAR_AT[1] + float(rng.uniform(-1.2, 1.2))]

    def spawn_orb(t):
        occ = set(bodies[0]) | set(bodies[1]) | set(orbs)
        for _ in range(300):
            c = (int(rng.integers(1, ROWS - 1)), int(rng.integers(1, COLS - 1)))
            if c in occ or min(abs(c[0] - b[0][0]) + abs(c[1] - b[0][1]) for b in bodies) < 4: continue
            orbs[c] = ("orb", 1, t, -1); return

    def spawn_star(t):
        occ = set(bodies[0]) | set(bodies[1]) | set(orbs); best = None
        for _ in range(400):
            c = (int(rng.integers(2, ROWS - 2)), int(rng.integers(2, COLS - 2)))
            if c in occ: continue
            d = [abs(c[0] - b[0][0]) + abs(c[1] - b[0][1]) for b in bodies]
            sc = abs(d[0] - d[1]) * 2 + abs(min(d) - 9)
            if best is None or sc < best[0]: best = (sc, c)
        if best: orbs[best[1]] = ("star", STAR_VAL, t, -1); ev.append(("star", t, -1, best[1]))

    def score(i): return len(bodies[i]) + grow[i]

    def snap(t):
        snaps.append(dict(t=t, B=[list(b) for b in bodies], orbs=dict(orbs), sc=[score(0), score(1)],
                          stun=[stun[0] > t, stun[1] > t]))

    for _ in range(N_ORB): spawn_orb(0.0)
    snap(0.0); t = T_GATE; snap(t); win = -1

    def decide(i, t):
        b = bodies[i]; o = bodies[1 - i]; head = b[0]; d = (head[0] - b[1][0], head[1] - b[1][1])
        other_moves = stun[1 - i] <= t
        blocked = set(b[:-1] if grow[i] == 0 else b) | set(o[:-1] if (grow[1 - i] == 0 and other_moves) else o)
        cands = [dd for dd in DIRS if dd != (-d[0], -d[1])]
        if rng.random() < perr[i]:
            return cands[int(rng.integers(0, len(cands)))]
        safe = [dd for dd in cands if inb((head[0] + dd[0], head[1] + dd[1])) and (head[0] + dd[0], head[1] + dd[1]) not in blocked]
        if not safe:
            if was_stun[i]:
                bodies[i] = b[::-1]; was_stun[i] = False; return decide(i, t)
            return d
        best = None; oh = o[0]
        for dd in safe:
            nc = (head[0] + dd[0], head[1] + dd[1])
            dist, room = bfs(nc, blocked | {head}, orbs)
            sc = dist + (60 if room < len(b) + 3 else 0) + ((12 if other_moves else 2) if abs(nc[0] - oh[0]) + abs(nc[1] - oh[1]) == 1 else 0) + float(rng.uniform(0, .6))
            if best is None or sc < best[0]: best = (sc, dd)
        return best[1]

    while t < T_GATE + 40:
        rate = 8.5 + 4.5 * E.clamp((t - T_GATE) / 14)
        t += 1 / rate
        for j, ts in enumerate(stars):
            if ts and t >= ts:
                spawn_star(t); stars[j] = None
        moves = [None, None]
        for i in (0, 1):
            if stun[i] > t: continue
            moves[i] = decide(i, t); was_stun[i] = False
        new = [None if moves[i] is None else (bodies[i][0][0] + moves[i][0], bodies[i][0][1] + moves[i][1]) for i in (0, 1)]
        crash = [False, False]; headon = False
        for i in (0, 1):
            if new[i] is None: continue
            nh = new[i]
            if not inb(nh): crash[i] = True; continue
            for j in (0, 1):
                bj = bodies[j]; tail_free = new[j] is not None and grow[j] == 0 and new[j] not in orbs
                if nh in (bj[:-1] if tail_free else bj): crash[i] = True
        if new[0] is not None and new[1] is not None:
            if new[0] == new[1] or (new[0] == bodies[1][0] and new[1] == bodies[0][0]): crash = [True, True]; headon = True
        for i in (0, 1):
            if new[i] is None: continue
            b = bodies[i]
            if crash[i]:
                keep = max(3, int(round(len(b) * .6))); dropped = b[keep:]; bodies[i] = b[:keep]; grow[i] = 0
                stun[i] = t + STUN + (.35 if headon and i == int(rng.integers(0, 2)) else 0); was_stun[i] = True
                hx = new[i] if inb(new[i]) else b[0]
                ev.append(("crash", t, i, b[0], len(dropped), [tuple(c) for c in dropped], hx))
                for k, c in enumerate(dropped):
                    if k % 2 == 0 and c not in orbs: orbs[c] = ("crumb", 1, t, i)
                continue
            nh = new[i]; b.insert(0, nh)
            if nh in orbs:
                kind, val, _, own = orbs.pop(nh); grow[i] += val; ev.append(("eat", t, i, nh, kind, score(i) - 1))
                if kind == "orb": spawn_orb(t)
            if grow[i] > 0: grow[i] -= 1
            else: b.pop()
        for i in (0, 1):
            if score(i) >= GOAL and win < 0: win = i
        snap(t)
        if win >= 0:
            ev.append(("win", t, win, bodies[win][0])); snap(t + 3.0)
            return dict(snaps=snaps, ev=ev, win=win, t_win=t, final=[score(0), score(1)])
    return None


def lead_info(sim):
    sg = []; ts = []
    for s in sim["snaps"][2:]:
        a, b = s["sc"]
        if a != b:
            v = 1 if a > b else -1
            if not sg or sg[-1] != v: sg.append(v); ts.append(s["t"])
    return len(sg) - 1 if sg else 0, list(zip(ts, sg))


def pick(seed0, tries=140, log=print):
    best = None
    for seed in range(seed0, seed0 + tries):
        sim = simulate(seed)
        if not sim: continue
        tw = sim["t_win"] - T_GATE; win = sim["win"]; lose = 1 - win; ch, _ = lead_info(sim)
        crashes = [e for e in sim["ev"] if e[0] == "crash"]; late = [e for e in crashes if e[1] - T_GATE > tw * .6 and e[4] >= 4]
        deficit = max([s["sc"][lose] - s["sc"][win] for s in sim["snaps"][2:] if s["t"] - T_GATE > 4] + [0])
        stars = sum(1 for e in sim["ev"] if e[0] == "eat" and e[4] == "star")
        margin = GOAL - sim["final"][lose]
        ok = 13.0 <= tw <= 18.5 and ch >= 2 and margin <= 6 and len(crashes) >= 2 and stars >= 1
        score = min(ch, 6) * .5 + min(deficit, 8) * .25 + (1.0 if late else 0) + (1.2 if win == 1 else 0) - margin * .3 - abs(tw - 15.5) * .2
        if ok and (best is None or score > best[0]):
            best = (score, seed, sim)
            log(f"[snake_duel] seed {seed}: {TEAMS[win]['name']} wins {GOAL}-{sim['final'][lose]} in {tw:.1f}s, lead changes {ch}, "
                f"crashes {len(crashes)} (late {len(late)}), deficit {deficit}, stars {stars}, score {score:.2f}")
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


def static_bg():
    bg = E.make_bg((8, 10, 26), (22, 8, 36), (50, 34, 100))
    for r in range(ROWS):
        for c in range(COLS):
            col = (24, 26, 50) if (r + c) % 2 == 0 else (30, 32, 60)
            cv2.rectangle(bg, (AX0 + c * CS, AY0 + r * CS), (AX0 + (c + 1) * CS - 1, AY0 + (r + 1) * CS - 1), col, -1)
    glow = np.zeros((H // 2, W // 2, 3), np.uint8)
    xs = np.linspace(0, 1, 64)
    for k in range(63):                                   # border: fire-orange on the left, ice-blue on the right
        u = xs[k]; col = tuple(int(TEAMS[0]["col"][j] * (1 - u) + TEAMS[1]["col"][j] * u) for j in range(3))
        xa, xb = int(AX0 - 4 + AW * xs[k]), int(AX0 - 4 + AW * xs[k + 1]) + 8
        cv2.line(glow, (xa // 2, (AY0 - 5) // 2), (xb // 2, (AY0 - 5) // 2), col, 4); cv2.line(glow, (xa // 2, (AY0 + AH + 4) // 2), (xb // 2, (AY0 + AH + 4) // 2), col, 4)
        cv2.line(bg, (xa, AY0 - 5), (min(xb, AX0 + AW + 4), AY0 - 5), col, 5, cv2.LINE_AA); cv2.line(bg, (xa, AY0 + AH + 4), (min(xb, AX0 + AW + 4), AY0 + AH + 4), col, 5, cv2.LINE_AA)
    cv2.line(bg, (AX0 - 5, AY0 - 5), (AX0 - 5, AY0 + AH + 4), TEAMS[0]["col"], 5, cv2.LINE_AA); cv2.line(glow, ((AX0 - 5) // 2, (AY0 - 5) // 2), ((AX0 - 5) // 2, (AY0 + AH + 4) // 2), TEAMS[0]["col"], 4)
    cv2.line(bg, (AX0 + AW + 4, AY0 - 5), (AX0 + AW + 4, AY0 + AH + 4), TEAMS[1]["col"], 5, cv2.LINE_AA); cv2.line(glow, ((AX0 + AW + 4) // 2, (AY0 - 5) // 2), ((AX0 + AW + 4) // 2, (AY0 + AH + 4) // 2), TEAMS[1]["col"], 4)
    E.add_glow(bg, glow, 7, .9)
    for k, y in enumerate(LANE_Y):                         # race lanes (static part)
        cv2.rectangle(bg, (BX0, y - 22), (BX1, y + 22), (34, 36, 62), -1)
        cv2.rectangle(bg, (BX0, y - 22), (BX1, y + 22), (90, 94, 130), 2, cv2.LINE_AA)
        for j in range(4):                                  # chequered finish block
            for q in range(2):
                c = (240, 240, 240) if (j + q) % 2 == 0 else (20, 20, 20)
                cv2.rectangle(bg, (BX1 + 2 + q * 11, y - 22 + j * 11), (BX1 + 12 + q * 11, y - 12 + j * 11), c, -1)
        E.blit(bg, emoji(TEAMS[k]["emo"], 50), 98, y)
    return bg


def build(out_mp4, seed=1, race_no=1, log=print, stills=None, tries=140):
    seed, sim = pick(seed, tries=tries, log=log); snaps = sim["snaps"]; ts = [s["t"] for s in snaps]; win = sim["win"]; lose = 1 - win
    t_win = sim["t_win"]; ev = sim["ev"]; ch, flips = lead_info(sim)
    S, s0, s1 = .33, t_win - .55, t_win + .14
    v1 = s0 + (s1 - s0) / S
    def sim_t(v): return v if v < s0 else s0 + (v - s0) * S if v < v1 else s1 + (v - v1)
    def vid_t(t): return t if t < s0 else s0 + (t - s0) / S if t < s1 else v1 + (t - s1)
    v_end = vid_t(t_win + .75); CARD = 3.8; LOOP = .35; total = v_end + CARD; n = int(round(total * FPS))
    log(f"[snake_duel] video {total:.1f}s, winner {TEAMS[win]['name']} {GOAL}-{sim['final'][lose]}")
    bg = static_bg(); TW, TL = TEAMS[win], TEAMS[lose]
    # status-line events (sim time, priority, text, colour)
    status = []
    for (tt, sgn) in flips[1:]:
        lead = 0 if sgn > 0 else 1
        status.append((tt, 2, f"{TEAMS[lead]['name']} TAKES THE LEAD!", TEAMS[lead]["lite"]))
    for e in ev:
        if e[0] == "star": status.append((e[1], 1, f"+{STAR_VAL} STAR ON THE BOARD!", (255, 225, 90)))
        elif e[0] == "eat" and e[4] == "star": status.append((e[1], 3, f"{TEAMS[e[2]]['name']} GRABS THE STAR! +{STAR_VAL}", (255, 225, 90)))
        elif e[0] == "crash" and e[1] < t_win: status.append((e[1], 3, f"{TEAMS[e[2]]['name']} CRASHED!  -{e[4]}", (255, 120, 130)))
    status.sort()

    def state(t):
        k = max(0, min(len(snaps) - 2, bisect.bisect_right(ts, t) - 1)); A, B = snaps[k], snaps[k + 1]
        w = 0.0 if B["t"] <= A["t"] else E.clamp((t - A["t"]) / (B["t"] - A["t"]))
        out = []
        for i in (0, 1):
            b0, b1 = A["B"][i], B["B"][i]
            if t < T_GATE: pts = [px(c) for c in b0]
            elif abs(b1[0][0] - b0[0][0]) + abs(b1[0][1] - b0[0][1]) == 1 and len(b1) - len(b0) in (0, 1):
                h0, h1 = px(b0[0]), px(b1[0]); t0, t1 = px(b0[-1]), px(b1[-1])
                pts = [(E.lerp(h0[0], h1[0], w), E.lerp(h0[1], h1[1], w))] + [px(c) for c in b0[:-1]] + [(E.lerp(t0[0], t1[0], w), E.lerp(t0[1], t1[1], w))]
            else: pts = [px(c) for c in (b1 if w > .5 else b0)]
            out.append(pts)
        return out, A, k

    def head_dir(pts):
        if len(pts) < 2: return (1.0, 0.0)
        dx, dy = pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]; L = math.hypot(dx, dy)
        if L < 1e-3 and len(pts) > 2: dx, dy = pts[1][0] - pts[2][0], pts[1][1] - pts[2][1]; L = math.hypot(dx, dy)
        return (dx / L, dy / L) if L > 1e-3 else (1.0, 0.0)

    def draw_snake(f, glow, pts, tm, i, v, stunned, winner_glow):
        T = TEAMS[tm]; nP = len(pts); th = 34
        P = [(int(round(x)), int(round(y))) for x, y in pts]
        cv2.polylines(glow, [np.array([(x // 2, y // 2) for x, y in P], np.int32)], False, T["col"], 12 if not winner_glow else 18, cv2.LINE_AA)
        for j in range(nP - 1, 0, -1):
            u = j / max(1, nP - 1); col = tuple(int(T["lite"][q] * (1 - u) * .35 + T["col"][q] * (1 - u) * .65 + T["deep"][q] * u) for q in range(3))
            cv2.line(f, P[j], P[j - 1], col, th, cv2.LINE_AA); cv2.circle(f, P[j], th // 2, col, -1, cv2.LINE_AA)
        shine = tuple(min(255, int(c * .5 + 255 * .5)) for c in T["lite"])
        cv2.polylines(f, [np.array([(x - 3, y - 4) for x, y in P[:max(2, nP - 2)]], np.int32)], False, shine, 6, cv2.LINE_AA)
        # particles: embers rise off FIRE, frost sparkles twinkle on ICE
        if tm == 0:
            for m in range(16):
                seg = (m * 7 + i // 5) % nP; ph = ((i * 1.0 + m * 13) % 34) / 34
                x = pts[seg][0] + math.sin(m * 2.3 + i * .05) * 12; y = pts[seg][1] - ph * 46
                col = (255, int(230 - 120 * ph), int(90 - 80 * ph)); r = max(1, int(4 * (1 - ph)))
                cv2.circle(f, (int(x), int(y)), r, col, -1, cv2.LINE_AA); cv2.circle(glow, (int(x / 2), int(y / 2)), r + 1, (255, 140, 40), -1)
        else:
            for m in range(12):
                seg = (m * 5 + i // 7) % nP; ph = ((i * 1.0 + m * 11) % 40) / 40; a_ = math.sin(ph * math.pi)
                x = pts[seg][0] + math.cos(m * 1.7) * 13; y = pts[seg][1] + math.sin(m * 2.9) * 13; L = int(3 + 8 * a_)
                c_ = (int(200 + 55 * a_), 250, 255)
                cv2.line(f, (int(x - L), int(y)), (int(x + L), int(y)), c_, 2, cv2.LINE_AA); cv2.line(f, (int(x), int(y - L)), (int(x), int(y + L)), c_, 2, cv2.LINE_AA)
        hx, hy = pts[0]; dx, dy = head_dir(pts); flash = stunned and int(v * 16) % 2 == 0
        cv2.circle(f, (int(hx), int(hy)), 23, (255, 255, 255) if flash else T["col"], -1, cv2.LINE_AA)
        cv2.circle(f, (int(hx), int(hy)), 23, T["lite"], 3, cv2.LINE_AA)
        cv2.circle(glow, (int(hx / 2), int(hy / 2)), 16, T["lite"], -1)
        for sgn in (-1, 1):
            ex, ey = hx + dx * 7 - dy * 10 * sgn, hy + dy * 7 + dx * 10 * sgn
            if stunned:
                for a_, b_ in ((-5, -5), (-5, 5)):
                    cv2.line(f, (int(ex + a_), int(ey + b_)), (int(ex - a_), int(ey - b_)), (20, 20, 30), 3, cv2.LINE_AA)
            else:
                cv2.circle(f, (int(ex), int(ey)), 8, (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(f, (int(ex + dx * 3), int(ey + dy * 3)), 4, (15, 15, 25), -1, cv2.LINE_AA)

    def status_at(t, v, A):
        if v >= vid_t(t_win): return (f"{TW['name']} HITS {GOAL}!", TW["lite"], 0)
        if s0 <= t: return ("FINAL BITE...", (255, 225, 90), 1)
        cur = None
        for (tt, pr, txt, col) in status:
            if tt <= t < tt + 1.15 and (cur is None or pr >= cur[0]): cur = (pr, txt, col, tt)
        if cur: return (cur[1], cur[2], 2, cur[3])
        a, b = A["sc"]
        if t < T_GATE + .2: return (f"FIRST SNAKE TO {GOAL} WINS", (255, 255, 255), 0)
        if a == b: return (f"TIED  {a}-{b}", (255, 255, 255), 0)
        ld = 0 if a > b else 1
        return (f"{TEAMS[ld]['name']} LEADS  {max(a, b)}-{min(a, b)}", TEAMS[ld]["lite"], 0)

    def draw(i, final=True):
        v = i / FPS; t = sim_t(min(v, v_end)); f = bg.copy(); glow = np.zeros((H // 2, W // 2, 3), np.uint8)
        P, A, k = state(t)
        # orbs, crumbs, star
        for c, (kind, val, born, own) in A["orbs"].items():
            x, y = px(c); age = t - born; pop = E.out_back(age / .3) if age < .3 else 1.0
            if kind == "star":
                pu = .5 + .5 * math.sin(v * 8)
                cv2.circle(glow, (int(x / 2), int(y / 2)), int(26 + 6 * pu), (255, 200, 60), -1)
                if age < .6: cv2.circle(f, (int(x), int(y)), int(30 + 260 * E.smooth(age / .6)), (255, 230, 120), max(1, int(8 * (1 - age / .6))), cv2.LINE_AA)
                E.blit(f, emoji("⭐", 58), x, y, scale=max(.05, pop * (1 + .1 * pu)))
            elif kind == "crumb":
                col = TEAMS[own]["lite"]; r = int(8 * pop) + 1
                cv2.circle(glow, (int(x / 2), int(y / 2)), 7, TEAMS[own]["col"], -1); cv2.circle(f, (int(x), int(y)), r, col, -1, cv2.LINE_AA)
            else:
                pu = math.sin(v * 6 + c[0] * 1.3 + c[1] * .7); r = max(1, int((11 + 2 * pu) * pop))
                cv2.circle(glow, (int(x / 2), int(y / 2)), 9, (255, 230, 150), -1)
                cv2.circle(f, (int(x), int(y)), r, (255, 244, 200), -1, cv2.LINE_AA); cv2.circle(f, (int(x), int(y)), max(1, r - 5), (255, 255, 255), -1, cv2.LINE_AA)
        # snakes: loser first, winner drawn on top
        stunned = A["stun"]; won = t >= t_win
        for tm in (lose, win):
            draw_snake(f, glow, P[tm], tm, i, v, stunned[tm] and t >= T_GATE, won and tm == win)
        # eat pops + crash bursts
        for e in ev:
            age = t - e[1]
            if e[0] == "eat" and 0 <= age < .45:
                x, y = px(e[3]); T = TEAMS[e[2]]; big = e[4] == "star"
                cv2.circle(f, (int(x), int(y)), int(14 + (70 if big else 34) * E.smooth(age / .45)), T["lite"], max(1, int(5 * (1 - age / .45))), cv2.LINE_AA)
                spr = E.text_sprite(f"+{STAR_VAL}" if big else "+1", 54 if big else 30, (255, 230, 100) if big else T["lite"], "black", stroke=4 if big else 3, stroke_color=(0, 0, 0))
                E.blit(f, spr, float(np.clip(x, 110, 970)), float(np.clip(y - 34 - 50 * age, AY0 + 30, AY0 + AH - 30)), alpha=1 - E.smooth((age - .3) / .15))
            elif e[0] == "crash" and 0 <= age < .9:
                T = TEAMS[e[2]]; hx, hy = px(e[3])
                for q, c in enumerate(e[5]):
                    if age > .5: break
                    x, y = px(c); ang = q * 2.399 + e[2]; sp = 160 + 60 * (q % 3)
                    xx, yy = x + math.cos(ang) * sp * age, y + math.sin(ang) * sp * age + 260 * age * age
                    cv2.rectangle(f, (int(xx - 7), int(yy - 7)), (int(xx + 7), int(yy + 7)), T["col"], -1, cv2.LINE_AA)
                if age < .3: cv2.circle(f, (int(hx), int(hy)), int(30 + 90 * E.smooth(age / .3)), (255, 255, 255), max(1, int(8 * (1 - age / .3))), cv2.LINE_AA)
                spr = E.text_sprite("BONK!", 64, (255, 255, 255), "black", stroke=6, stroke_color=T["deep"])
                E.blit(f, spr, float(np.clip(hx, 170, 910)), float(np.clip(hy - 70, AY0 + 50, AY0 + AH - 50)), alpha=1 - E.smooth((age - .7) / .2), scale=E.out_back(age / .22))
        E.add_glow(f, glow, 9, .85)
        # winner crown
        if won:
            u = (t - t_win) / .35 if v < v_end else 1.0; hx, hy = P[win][0]
            E.blit(f, emoji("👑", 64), hx, hy - 52, scale=max(.05, E.out_back(min(1, u))))
        # intro tags above the snakes
        if v < T_GATE + 1.0:
            al = 1 - E.smooth((v - T_GATE - .6) / .4)
            for tm in (0, 1):
                hx, hy = P[tm][0]; T = TEAMS[tm]; yy = hy - 58 if tm == 0 else hy + 58
                spr = E.text_sprite(T["role"], 34, T["lite"], "black", stroke=4, stroke_color=(0, 0, 0))
                E.blit(f, spr, float(np.clip(hx, 150, 930)), yy, alpha=al)
        # top HUD
        title = E.text_sprite(f"FIRE  VS  ICE", 72, (255, 255, 255), "black", stroke=6, stroke_color=(0, 0, 0))
        E.blit(f, title, W / 2, 292); E.blit(f, emoji("🔥", 70), W / 2 - title.shape[1] / 2 - 52, 292); E.blit(f, emoji("🧊", 66), W / 2 + title.shape[1] / 2 + 52, 292)
        st = status_at(t, v, A); txt, col, kind_ = st[0], st[1], st[2]
        sc = 1.0
        if kind_ == 2: sc = E.out_back((t - st[3]) / .2) if t - st[3] < .2 else 1.0
        spr = E.text_sprite(txt, 44, col, "black", stroke=5, stroke_color=(0, 0, 0))
        if spr.shape[1] > 940: spr = cv2.resize(spr, (940, int(spr.shape[0] * 940 / spr.shape[1])), interpolation=cv2.INTER_AREA)
        E.pill(f, W / 2 - min(470, spr.shape[1] / 2 + 30), 380 - 38, W / 2 + min(470, spr.shape[1] / 2 + 30), 380 + 38, (0, 0, 0), .55 if kind_ == 0 else .75)
        alpha = .8 + .2 * math.sin(v * 12) ** 2 if kind_ == 1 else 1.0
        E.blit(f, spr, W / 2, 380, alpha=alpha, scale=sc)
        # race lanes
        sc_ = A["sc"]
        for tm, y in enumerate(LANE_Y):
            T = TEAMS[tm]; val = min(GOAL, sc_[tm]); xe = int(BX0 + (BX1 - BX0) * val / GOAL)
            cv2.rectangle(f, (BX0 + 2, y - 20), (max(BX0 + 3, xe), y + 20), T["col"], -1)
            cv2.rectangle(f, (BX0 + 2, y - 20), (max(BX0 + 3, xe), y - 12), T["lite"], -1)
            lead = sc_[tm] > sc_[1 - tm]
            if lead: cv2.rectangle(f, (BX0, y - 22), (BX1, y + 22), T["lite"], 3, cv2.LINE_AA)
            E.blit(f, E.text_sprite(T["name"], 28, (255, 255, 255), "black", stroke=3, stroke_color=(0, 0, 0)), BX0 + 14, y, anchor="l")
            E.blit(f, E.text_sprite(str(sc_[tm]), 44, T["lite"], "black", stroke=4, stroke_color=(0, 0, 0)), 968, y)
        # hook overlay before the gate
        if v < T_GATE:
            E.pill(f, 60, 760, W - 60, 1220, (0, 0, 0), .76)
            vs = E.text_sprite("FIRE VS ICE", 92, (255, 255, 255), "black", stroke=7, stroke_color=(0, 0, 0))
            E.blit(f, vs, W / 2, 858, scale=.92 + .08 * E.out_back(v / .3))
            E.blit(f, emoji("🔥", 84), 140, 858); E.blit(f, emoji("🧊", 80), W - 140, 858)
            E.blit(f, E.text_sprite(f"FIRST SNAKE TO {GOAL} WINS", 50, (255, 230, 140), "black", stroke=4, stroke_color=(0, 0, 0)), W / 2, 960)
            E.blit(f, E.text_sprite("CRASH AND YOU LOSE YOUR TAIL", 36, (230, 232, 245), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1036)
            E.blit(f, E.text_sprite("PICK A SIDE NOW", 52, (150, 255, 190), "black", stroke=5, stroke_color=(0, 0, 0)), W / 2, 1130,
                   alpha=.75 + .25 * math.sin(v * 12) ** 2)
        elif v < T_GATE + .6:
            u = (v - T_GATE) / .6
            E.blit(f, E.text_sprite("GO!", 150, (255, 225, 90), "black", stroke=9, stroke_color=(0, 0, 0)), W / 2, 980, alpha=1 - E.smooth((u - .5) / .5), scale=E.out_back(u / .4))
        if s0 <= t < t_win and v < v1:                       # slow-mo vignette
            a_ = .25 + .1 * math.sin(v * 10)
            f[:] = cv2.convertScaleAbs(f, alpha=1 - a_ * .35)
        if v >= v_end: card(f, v - v_end)
        if final and v > total - LOOP:
            bb = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - bb, draw(0, False), bb, 0)
        return f

    deficit = max([s["sc"][lose] - s["sc"][win] for s in snaps[2:]] + [0])
    sub_line = (f"THE UNDERDOG CAME BACK FROM {deficit} DOWN" if win == 1 and deficit >= 3 else
                f"THE UNDERDOG PULLED IT OFF" if win == 1 else
                f"THE FAVORITE SURVIVED A {deficit}-POINT HOLE" if deficit >= 3 else "THE FAVORITE HELD ON")

    def card(f, u):
        a_ = E.smooth(u / .3); f[:] = cv2.convertScaleAbs(f, alpha=1 - .82 * a_)
        E.blit(f, emoji(TW["emo"], 230), W / 2, 640, alpha=a_, scale=max(.05, E.out_back(u / .45)))
        E.blit(f, E.text_sprite(f"{TW['name']} WINS", 120, (255, 255, 255), "black", stroke=8, stroke_color=(0, 0, 0)), W / 2, 858, alpha=a_, scale=max(.05, E.out_back((u - .1) / .4)))
        E.blit(f, E.text_sprite(f"{sim['final'][win]} - {sim['final'][lose]}", 64, TW["lite"], "black", stroke=5, stroke_color=(0, 0, 0)), W / 2, 965, alpha=E.smooth((u - .35) / .3))
        E.blit(f, E.text_sprite(sub_line, 34, (230, 232, 245), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1040, alpha=E.smooth((u - .55) / .3))
        E.blit(f, E.text_sprite("TEAM FIRE OR TEAM ICE?", 58, (150, 255, 190), "black", stroke=5, stroke_color=(0, 0, 0)), W / 2, 1190, alpha=E.smooth((u - 1.0) / .3), scale=max(.05, E.out_back((u - 1.0) / .35)))
        E.blit(f, E.text_sprite("WHO TAKES THE REMATCH?", 40, (255, 230, 140), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1268, alpha=E.smooth((u - 1.35) / .3))

    # ---- audio: synthwave bed (B minor, 108 bpm, detuned saw pads, saw 8th bass, 808); fire bites = warm plucks, ice bites = glass bells
    mix = E.Mix(total, mood="synthwave", bpm=108, root=47, scale="minor"); hz = lambda m_: float(E.midi_hz(m_)); beat = 60 / 108
    for j in range(3): mix.add(.15 + j * .5, E.saw(hz(71), .25, harm=8, decay=9), .35); mix.add(.15 + j * .5, E.tick(2400, .05), .25)
    mix.add(T_GATE, E.chord([59, 62, 66, 71], 1.2, E.bell), .4); mix.add(T_GATE, E.thump(.6, 130, 38), .7); mix.add(T_GATE - .3, E.whoosh(.35), .35)
    v_slow = vid_t(s0)
    mix.bed(T_GATE, vid_t(t_win), gain=.26, seed=seed, intensity=lambda tt: E.clamp((tt - T_GATE) / max(1, v_slow - T_GATE) * 1.15),
            drums_off=[(v_slow, v_end + 1)])
    per = {}
    for e in ev:
        vt = vid_t(e[1])
        if vt > v_end: continue
        if e[0] == "eat":
            b_ = int(vt * 12)
            if per.get(b_, 0) >= 2: continue
            per[b_] = per.get(b_, 0) + 1; note = mix.scale_note(min(e[5], 34) // 2, 1); pan = -.35 if e[2] == 0 else .35
            if e[4] == "star":
                for j, m_ in enumerate([0, 4, 7, 12]): mix.add(vt + j * .06, E.bell(hz(note + m_), .7), .3, pan)
            elif e[2] == 0: mix.add(vt, E.pluck(hz(note), .4), .4, pan)
            else: mix.add(vt, E.bell(hz(note + 12), .45), .22, pan)
        elif e[0] == "crash" and e[1] <= t_win:
            mix.add(vt, E.thump(.55, 150, 34), .8); mix.add(vt, E.slide_down(.6, 620, 140), .3, -.3 if e[2] == 0 else .3)
        elif e[0] == "star":
            mix.add(vt, E.chord([83, 86, 90], .9, E.bell), .35)
    for (tt, sgn) in flips[1:]: mix.add(vid_t(tt), E.saw(hz(78 if sgn > 0 else 83), .3, harm=6, decay=7), .25)
    mix.add(max(0, v_slow - 1.8), E.riser(1.8 + (v1 - v_slow) * .6, 220, 2600), .32)
    vw = vid_t(t_win); mix.add(vw, E.thump(1.2, 120, 28), 1.0); mix.add(vw, E.whoosh(.8, 21), .5)
    for j, m_ in enumerate([71, 74, 78, 83, 86]): mix.add(vw + .12 + j * .09, E.saw(hz(m_), .35, harm=8, decay=6), .3)
    mix.add(v_end, E.pad([hz(m_) for m_ in (47, 59, 62, 66, 71)], CARD, attack=.4, release=1.0), .55)
    mix.add(v_end + .5, E.chord([71, 74, 78, 83], 2.6, E.bell), .4)
    wav = out_mp4[:-4] + ".wav"; mix.write(wav, peak=.84)
    info = dict(total=total, v_end=v_end, v_slow=v_slow, v_win=vw, winner=TW["name"], final=sim["final"], lead_changes=ch, seed=seed)
    if stills:
        for t_ in stills: E.save_png(out_mp4[:-4] + f"_still_{t_:05.2f}.png", draw(min(n - 1, int(t_ * FPS)), False))
        os.remove(wav); return info
    E.render(out_mp4, wav, n, draw); os.remove(wav)
    crashes = sum(1 for e in ev if e[0] == "crash" and e[1] <= t_win)
    return dict(duration=total, title=f"Fire vs Ice Snake Race: First to {GOAL} Wins | Snake Duel #{race_no}",
                description=f"Fire starts two longer. Ice is the underdog. Both snakes chase the same orbs; crash and you lose your tail.",
                tags=["snake race", "fire vs ice", "snake game", "satisfying", "simulation"], winner=TW["name"], loser=TL["name"],
                final_score=sim["final"], lead_changes=ch, crashes=crashes, comeback_deficit=deficit, seed=seed,
                thumb_ms=900, v_win=vw)


if __name__ == "__main__":                     # python3 -I lab/styles/snake_duel.py <out.mp4> <seed> [episode]
    import json
    out = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1; ep = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    res = build(out, seed, race_no=ep, log=lambda *a: print(*a, file=sys.stderr)); print("RESULT=" + json.dumps(res, default=float))
