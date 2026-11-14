"""LAB STYLE turf_war: 1-vs-1 territory duel. A food favorite (PIZZA, bigger start) vs an underdog (TACO) spread across a
28x35 tile board like a cellular-automata colour war. Sauce pickups flip a whole blob to whoever reaches them first.
Rubber-banding keeps it close; the seed search keeps only comeback finishes where the UNDERDOG wins after trailing.
HUD = live split bar with percentages; slow-mo final 1.5 s, winner card, loop blend. Pure simulation, no data."""
import os, sys, math
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
import engine as E
from engine import W, H, FPS

EMOJI = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
TEAMS = [dict(name="PIZZA", emo="🍕", col=(236, 62, 66), lite=(255, 120, 110), role="FAVORITE"),
         dict(name="TACO", emo="🌮", col=(255, 206, 56), lite=(255, 236, 140), role="UNDERDOG")]
COLS, ROWS, CS = 28, 35, 36
AX0, AY0 = 36, 400
AW, AH = COLS * CS, ROWS * CS
SIMHZ, T_END, T_GATE, SLOW_LEN, SLOW_K = 30, 20.0, 1.7, 1.5, .4
PICKUPS = [(4.0, 11, 12), (8.0, 24, 15), (12.0, 17, 9), (15.5, 20, 19)]      # (appear t, row, col) baseline; jittered by seed
BLAST_R = 4.6
EMPTY = (30, 32, 52)


def nbr_count(m):
    n = np.zeros(m.shape, np.int8)
    n[1:] += m[:-1]; n[:-1] += m[1:]; n[:, 1:] += m[:, :-1]; n[:, :-1] += m[:, 1:]
    return n


def simulate(seed):
    rng = np.random.default_rng(seed); own = np.full((ROWS, COLS), -1, np.int8)
    own[1:5, 1:5] = 0; own[ROWS - 4:ROWS - 1, COLS - 4:COLS - 1] = 1
    pe, px = [.15, .125], [.06, .062]
    pu = [(t, int(np.clip(r + rng.integers(-3, 4), 4, ROWS - 5)), int(np.clip(c + rng.integers(-4, 5), 3, COLS - 4))) for (t, r, c) in PICKUPS]
    last = np.full((ROWS, COLS), -9.0, np.float32); states = []; lasts = []; ev = []; got = [False] * len(pu); share_hist = []
    yy, xx = np.mgrid[0:ROWS, 0:COLS]
    for k in range(int(T_END * SIMHZ) + 1):
        t = k / SIMHZ
        if k:
            m = [(own == 0).astype(np.int8), (own == 1).astype(np.int8)]; sh = [m[0].sum() / own.size, m[1].sum() / own.size]
            nb = [nbr_count(m[0]), nbr_count(m[1])]; claim = []
            for tm in (0, 1):
                op = 1 - tm; boost = 1 + 1.1 * max(0.0, sh[op] - sh[tm]) * 4
                base = np.where(own == -1, pe[tm], px[tm] / (1 + .5 * nb[op]))
                p = 1 - (1 - base * boost) ** nb[tm]; claim.append((rng.random(own.shape) < p) & (own != tm) & (nb[tm] > 0))
            both = claim[0] & claim[1]; coin = rng.random(own.shape) < .5
            c0 = claim[0] & (~both | coin); c1 = claim[1] & (~both | ~coin)
            new = own.copy(); new[c0] = 0; new[c1] = 1
            ch = new != own; last[ch] = t; own = new
            for j, (tp, pr, pc) in enumerate(pu):
                if got[j] or t < tp: continue
                win = own[max(0, pr - 1):pr + 2, max(0, pc - 1):pc + 2]; a, b = (win == 0).sum(), (win == 1).sum()
                if a + b:
                    tm = 0 if (a > b or (a == b and rng.random() < .5)) else 1
                    d2 = (yy - pr) ** 2 + (xx - pc) ** 2; z = d2 <= BLAST_R ** 2
                    own[z] = tm; last[z] = t; got[j] = True; ev.append(("blast", t, pr, pc, tm))
        states.append(own.copy()); lasts.append(last.copy())
        c0_ = (own == 0).sum(); c1_ = (own == 1).sum(); share_hist.append((t, c0_ / own.size, c1_ / own.size))
    fin = share_hist[-1]
    return dict(states=states, lasts=lasts, ev=ev, pu=pu, got=got, shares=share_hist, winner=int(fin[2] > fin[1]), margin=abs(fin[1] - fin[2]))


def lead_changes(sim):
    sg = []
    for (t, a, b) in sim["shares"]:
        if abs(a - b) > .03: sg.append(1 if a > b else -1)
    return sum(1 for x, y in zip(sg, sg[1:]) if x != y), sg


def pick(seed0, tries=60, log=print):
    best = None
    for seed in range(seed0, seed0 + tries):
        sim = simulate(seed); ch, sg = lead_changes(sim); sh = sim["shares"]
        trailing_mid = sum(1 for (t, a, b) in sh if 6 < t < 15 and a > b + .04) / max(1, sum(1 for (t, a, b) in sh if 6 < t < 15))
        late = [(a, b) for (t, a, b) in sh if t > T_END - 6]
        late_flip = any(a > b + .02 for a, b in late[:30]) and sim["winner"] == 1        # fav led late, taco still won
        ok = sim["winner"] == 1 and .02 <= sim["margin"] <= .2 and ch >= 2 and all(sim["got"][:3])
        score = min(ch, 5) * .5 + trailing_mid * 1.2 + (.8 if late_flip else 0) - abs(sim["margin"] - .1) * 6
        log(f"[turf_war] seed {seed}: winner {TEAMS[sim['winner']]['name']} margin {sim['margin']:.3f} changes {ch} trail {trailing_mid:.2f} flip {late_flip} score {score:.2f}{'' if ok else ' (x)'}")
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


def build(out_mp4, seed, ep=1, log=print, stills=None):
    sim = simulate(seed); ch, _ = lead_changes(sim); win = sim["winner"]; lose = 1 - win
    S_SLOW = T_END - SLOW_LEN; G = T_GATE; v_slow = G + S_SLOW; v_end = v_slow + SLOW_LEN / SLOW_K; CARD = 3.3; LOOP = .35
    total = v_end + CARD
    def sim_t(v):
        if v < G: return 0.0
        s = v - G
        if s < S_SLOW: return s
        return min(T_END, S_SLOW + (s - S_SLOW) * SLOW_K)
    def vid_t(t): return G + t if t < S_SLOW else v_slow + (t - S_SLOW) / SLOW_K
    n = int(total * FPS); states, lasts, shares = sim["states"], sim["lasts"], sim["shares"]
    pal = np.array([EMPTY, TEAMS[0]["col"], TEAMS[1]["col"]], np.uint8)       # index owner+1 -> use own+1 with -1->0
    pal = np.array([EMPTY, TEAMS[0]["col"], TEAMS[1]["col"]], np.uint8)
    flash = np.array([(255, 255, 255)] * 3, np.uint8)
    tile = np.ones((CS, CS), np.float32); tile[:2] = .72; tile[:, :2] = .72; tile[-2:] = .55; tile[:, -2:] = .55; tile[2:6, 2:-2] *= 1.08
    tile = np.tile(tile, (ROWS, COLS))[..., None]
    bg = E.make_bg((10, 12, 30), (24, 10, 40), (60, 40, 110))
    band = np.ones((H, W, 1), np.float32)
    band[:380] = .55; band[380:AY0] = .45
    yy = np.arange(H)[:, None, None]; band = np.where((yy >= 232) & (yy < AY0), .5, 1.0).astype(np.float32) * np.ones((1, W, 1), np.float32)
    tag = E.text_sprite("@thatdatalover", 30, (225, 230, 245), "med", stroke=2, stroke_color=(0, 0, 0))
    def share_at(t):
        i = min(len(shares) - 1, int(t * SIMHZ)); return shares[i][1], shares[i][2]
    # lead-change popups (video time) after the first 3 s of sim, 2.5 s apart
    pops = []; prev = None; lastp = -9
    for (t, a, b) in shares:
        if abs(a - b) < .03: continue
        cur = 0 if a > b else 1
        if prev is not None and cur != prev and t - lastp > 2.5 and t > 3: pops.append((t, cur)); lastp = t
        prev = cur
    final_pop = [p for p in pops if p[0] > T_END - 7]
    s0 = vid_t(T_END - 6)                 # climax window begins
    def grid_img(t, i):
        k = min(len(states) - 1, int(t * SIMHZ)); st = states[k]; la = lasts[k]
        img = pal[st + 1]                                           # (ROWS, COLS, 3)
        age = t - la; fl = np.clip(1 - age / .35, 0, 1)[..., None] * (st >= 0)[..., None] * .55
        img = (img * (1 - fl) + 255 * fl).astype(np.uint8)
        big = cv2.resize(img, (AW, AH), interpolation=cv2.INTER_NEAREST)
        return (big * tile).clip(0, 255).astype(np.uint8)
    def draw(i, final=True):
        v = i / FPS; t = sim_t(min(v, v_end)); f = bg.copy()
        f[AY0:AY0 + AH, AX0:AX0 + AW] = grid_img(t, i)
        cv2.rectangle(f, (AX0 - 3, AY0 - 3), (AX0 + AW + 2, AY0 + AH + 2), (235, 235, 250), 3, cv2.LINE_AA)
        glow = np.zeros((H // 2, W // 2, 3), np.uint8)
        # home bases
        for tm, (r, c) in enumerate([(2.5, 2.5), (ROWS - 2.5, COLS - 2.5)]):
            E.blit(f, emoji(TEAMS[tm]["emo"], 92), AX0 + c * CS + (CS * .5 if tm == 0 else -CS * .5) * 0, AY0 + r * CS)
        # pickups
        for j, (tp, pr, pc) in enumerate(sim["pu"]):
            tg = [e for e in sim["ev"] if e[0] == "blast" and e[2] == pr and e[3] == pc]
            tc = tg[0][1] if tg else 99
            if tp <= t < tc:
                x, y = AX0 + (pc + .5) * CS, AY0 + (pr + .5) * CS; pu = .5 + .5 * math.sin(v * 9 + j)
                cv2.circle(f, (int(x), int(y)), int(BLAST_R * CS * (.97 + .03 * pu)), (255, 255, 255), 2, cv2.LINE_AA)
                cv2.circle(f, (int(x), int(y)), 30, (20, 20, 40), -1, cv2.LINE_AA)
                E.blit(f, emoji("🌶️", 46), x, y, scale=1 + .1 * pu); cv2.circle(glow, (int(x / 2), int(y / 2)), 34, (255, 150, 40), -1)
        for e in sim["ev"]:
            if e[0] != "blast": continue
            age = t - e[1]
            if 0 <= age < .55:
                x, y = AX0 + (e[3] + .5) * CS, AY0 + (e[2] + .5) * CS; rad = BLAST_R * CS * (.3 + .8 * E.smooth(age / .3)); col = TEAMS[e[4]]["lite"]
                cv2.circle(f, (int(x), int(y)), int(rad), (255, 255, 255), max(1, int(9 * (1 - age / .55))), cv2.LINE_AA)
                cv2.circle(glow, (int(x / 2), int(y / 2)), int(rad / 2), col, -1 if age < .15 else max(1, int(10 * (1 - age / .55))))
                E.blit(f, E.text_sprite("SAUCE BLAST!", 46, col, "black", stroke=5, stroke_color=(0, 0, 0)), W / 2, float(np.clip(y - 90, 470, 1560)),
                       alpha=1 - E.smooth((age - .4) / .15), scale=E.out_back(age / .2))
        E.add_glow(f, glow, 8, 1.0)
        f[:] = (f * band).astype(np.uint8)
        # HUD
        a, b = share_at(t); pa = int(round(100 * a / max(1e-9, a + b))); pb = 100 - pa
        E.blit(f, tag, W / 2, 266)
        bx0, bx1, by0, by1 = AX0, AX0 + AW, 352, 392
        occ = a + b if (a + b) > 0 else 1; frac = (a / occ) if occ else .5
        sp = AX0 + AW * frac
        cv2.rectangle(f, (bx0, by0), (bx1, by1), (40, 42, 62), -1); cv2.rectangle(f, (bx0, by0), (int(sp), by1), TEAMS[0]["col"], -1)
        cv2.rectangle(f, (int(sp), by0), (bx1, by1), TEAMS[1]["col"], -1); cv2.line(f, (int(sp), by0 - 8), (int(sp), by1 + 8), (255, 255, 255), 4, cv2.LINE_AA)
        cv2.rectangle(f, (bx0, by0), (bx1, by1), (235, 235, 250), 2, cv2.LINE_AA)
        for tm, xx, anc in ((0, AX0 + 8, "l"), (1, AX0 + AW - 8, "r")):
            val = pa if tm == 0 else pb
            lead_ = (a >= b) if tm == 0 else (b > a)
            lab = E.text_sprite(f"{TEAMS[tm]['emo'] if False else ''}{TEAMS[tm]['name']} {val}%", 40, (255, 255, 255), "black", stroke=5, stroke_color=(0, 0, 0))
            E.blit(f, lab, xx, 322, anchor=anc)
            E.blit(f, E.text_sprite(TEAMS[tm]["role"], 26, TEAMS[tm]["lite"], "bold", stroke=3, stroke_color=(0, 0, 0)), xx + (0 if tm == 0 else 0), 296 - 6, anchor=anc)
        # hook
        if v < G:
            a_ = E.smooth(v / .2); E.pill(f, 60, 800, W - 60, 1190, (0, 0, 0), .74 * a_)
            vs = E.text_sprite("PIZZA VS TACO", 78, (255, 255, 255), "black", stroke=6, stroke_color=(0, 0, 0))
            E.blit(f, vs, W / 2, 900, alpha=a_, scale=E.out_back(v / .3))
            E.blit(f, emoji("🍕", 96), 150, 900, alpha=a_); E.blit(f, emoji("🌮", 96), W - 150, 900, alpha=a_)
            E.blit(f, E.text_sprite("THE FAVORITE VS THE UNDERDOG", 38, (255, 230, 140), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1000, alpha=E.smooth((v - .15) / .25))
            E.blit(f, E.text_sprite("WHO TAKES THE BOARD?", 44, (255, 255, 255), "black", stroke=4, stroke_color=(0, 0, 0)), W / 2, 1072, alpha=E.smooth((v - .35) / .25))
            E.blit(f, E.text_sprite("PICK YOUR SIDE NOW", 40, (150, 255, 190), "black", stroke=4, stroke_color=(0, 0, 0)), W / 2, 1140, alpha=E.smooth((v - .6) / .25) * (.75 + .25 * math.sin(v * 12)))
        elif v < G + .6:
            u = (v - G) / .6; E.blit(f, E.text_sprite("GO!", 150, (255, 215, 80), "black", stroke=9, stroke_color=(0, 0, 0)), W / 2, 980, alpha=1 - E.smooth((u - .5) / .5), scale=E.out_back(u / .4))
        # lead-change pops
        for (tt, cur) in pops:
            age = v - vid_t(tt)
            if 0 <= age < 1.1 and vid_t(tt) < v_end:
                txt = "COMEBACK!" if cur == 1 and tt > 7 else "LEAD CHANGE!"
                spr = E.text_sprite(txt, 64, TEAMS[cur]["lite"], "black", stroke=6, stroke_color=(0, 0, 0))
                E.pill(f, W / 2 - spr.shape[1] / 2 - 34, 1648 - 60, W / 2 + spr.shape[1] / 2 + 34, 1648 + 60, (0, 0, 0), .62 * (1 - E.smooth((age - .8) / .3)))
                E.blit(f, spr, W / 2, 1648, alpha=1 - E.smooth((age - .8) / .3), scale=E.out_back(age / .25))
        if s0 <= v < v_end and v > G:
            spr = E.text_sprite("FINAL SECONDS", 56, (255, 215, 80), "black", stroke=6, stroke_color=(0, 0, 0))
            E.pill(f, W / 2 - spr.shape[1] / 2 - 34, 1648 - 56, W / 2 + spr.shape[1] / 2 + 34, 1648 + 56, (90, 0, 0), .62 * (.75 + .25 * math.sin(v * 12) ** 2))
            E.blit(f, spr, W / 2, 1648, alpha=.8 + .2 * math.sin(v * 12) ** 2)
        if v >= v_end: card(f, v - v_end)
        if final and v > total - LOOP:
            bb = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - bb, draw(0, False), bb, 0)
        return f
    fa, fb = share_at(T_END); wp = int(round((fb if win == 1 else fa) * 100)); lp = 100 - wp
    def card(f, u):
        a_ = E.smooth(u / .3); f[:] = cv2.convertScaleAbs(f, alpha=1 - .82 * a_); tw, tl = TEAMS[win], TEAMS[lose]
        E.blit(f, emoji(tw["emo"], 240), W / 2, 640, alpha=a_, scale=E.out_back(u / .45))
        E.blit(f, E.text_sprite(f"{tw['name']} WINS", 110, (255, 255, 255), "black", stroke=8, stroke_color=(0, 0, 0)), W / 2, 860, alpha=a_, scale=E.out_back((u - .1) / .4))
        E.blit(f, E.text_sprite(f"THE {tw['role']} TOOK THE BOARD {wp}-{lp}", 36, tw["lite"], "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 950, alpha=E.smooth((u - .45) / .3))
        E.blit(f, E.text_sprite("PIZZA OR TACO?", 66, (150, 255, 190), "black", stroke=5, stroke_color=(0, 0, 0)), W / 2, 1140, alpha=E.smooth((u - 1.0) / .3), scale=E.out_back((u - 1.0) / .35))
        E.blit(f, E.text_sprite("WHO GETS THE REMATCH?", 40, (255, 230, 140), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1220, alpha=E.smooth((u - 1.35) / .3))
    # ---- audio: upbeat marimba funk-pop bed (F major, 118 bpm); capture ticks pitched by fill; blasts boom; riser to slow-mo; bell chord on the card
    mix = E.Mix(total, mood="marimba", bpm=118, root=53, scale="major"); hz = lambda m_: float(E.midi_hz(m_)); beat = 60 / 118
    for j in range(4): mix.add(j * beat * .5, E.marimba(hz(65 + [0, 4, 7, 12][j]), .3), .3)
    mix.add(G, E.chord([65, 69, 72, 77], 1.0, E.bell), .45); mix.add(G, E.thump(.5, 140, 40), .7); mix.add(G - .25, E.whoosh(.35), .35)
    mix.bed(G, v_end, gain=.24, seed=seed, intensity=lambda tt: E.clamp((tt - G) / max(1, v_end - G) * 1.1), drums_off=[(v_slow + .2, v_end - .2)])
    per = {}
    def ok(vt, cap=2):
        b_ = int(vt * 14)
        if per.get(b_, 0) >= cap: return False
        per[b_] = per.get(b_, 0) + 1; return True
    for k in range(1, len(states)):
        t = k / SIMHZ; vt = vid_t(t)
        if vt >= v_end: break
        chg = int((lasts[k] == t).sum())
        if chg and ok(vt):
            tm = 0 if share_at(t)[0] > share_at(t)[1] else 1
            mix.add(vt, E.marimba(hz(mix.scale_note(int(share_at(t)[tm] * 14) + 2, 1)), .18), .12 + .02 * min(chg, 6), -.3 if tm == 0 else .3)
    for e in sim["ev"]:
        vt = vid_t(e[1])
        mix.add(vt, E.thump(.5, 130, 36), .55); mix.add(vt, E.whoosh(.3, 5), .3); mix.add(vt + .05, E.chord([77, 81, 84], .9, E.bell), .3)
    for (tt, cur) in pops: mix.add(vid_t(tt), E.bell(hz(84 if cur else 81), .6), .3)
    mix.add(max(0, v_slow - 1.8), E.riser(1.8, 200, 2400), .32)
    mix.add(v_slow, E.thump(.9, 110, 28), .8)
    mix.add(v_end, E.thump(1.3, 110, 26), 1.0); mix.add(v_end, E.whoosh(.8, 21), .5)
    for j, m_ in enumerate([65, 69, 72, 77, 81]): mix.add(v_end + .15 + j * .1, E.marimba(hz(m_), .5), .35)
    mix.add(v_end + .7, E.chord([53, 60, 65, 69, 76], 2.8, E.bell), .5)
    wav = out_mp4[:-4] + ".wav"; mix.write(wav, peak=.82)
    if stills:
        for t_ in stills: E.save_png(out_mp4[:-4] + f"_still_{t_:05.2f}.png", draw(min(n - 1, int(t_ * FPS)), False))
        return dict(total=total, v_end=v_end, v_slow=v_slow, pops=[(round(vid_t(a), 2), b) for a, b in pops], margin=sim["margin"], winner=TEAMS[win]["name"])
    E.render(out_mp4, wav, n, draw); os.remove(wav)
    return dict(duration=total, winner=TEAMS[win]["name"], loser=TEAMS[lose]["name"], win_pct=wp, lose_pct=lp, lead_changes=ch,
                seed=seed, thumb_ms=int(G * 1000 - 300), title="Pizza vs Taco: Favorite vs Underdog Turf War")


if __name__ == "__main__":                     # python3 -I lab/styles/turf_war.py <out.mp4> <seed> [episode]
    import json
    out = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1; ep = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    res = build(out, seed, ep=ep, log=lambda *a: print(*a, file=sys.stderr)); print("RESULT=" + json.dumps(res, default=float))
