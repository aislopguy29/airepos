"""STYLE: neon_doubling  (reference: @visualanimationss 'EVERY BOUNCE = 2x', neon string art).
A ball bounces inside a neon ring; every bounce doubles the counter and draws a chord. The chords close into a
star polygon on the final bounce. Milestones are .gov benchmarks; the final bounce passes the target benchmark.
Comment bait: 'guess the bounce number' before the reveal."""
import os, sys, math, json
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import engine as E
from engine import W, H, FPS

def money(v):
    for div, word in ((1e12, "TRILLION"), (1e9, "BILLION"), (1e6, "MILLION")):
        if v >= div: return f"${v/div:,.1f} {word}" if v / div < 100 else f"${v/div:,.0f} {word}"
    return f"${v:,.0f}" if v >= 10 or v == int(v) else f"${v:,.2f}"

def build(spec, root, out_dir, smoke=None, stills=None, log=print):
    bm = sorted(json.load(open(os.path.join(root, spec["benchmarks"]))), key=lambda b: b["value"])
    target = bm[-1]; N = math.ceil(math.log2(target["value"]))          # first bounce at which 2^k > target
    assert 2 ** N > target["value"] >= 2 ** (N - 1)
    m = spec.get("star_step", 15)
    while math.gcd(m, N) != 1: m += 1
    R, CX, CY = spec.get("R", 400), W // 2, 1050
    th0 = -math.pi / 2; step = 2 * math.pi * m / N
    pts = [(CX + R * math.cos(th0 + k * step), CY + R * math.sin(th0 + k * step)) for k in range(N + 1)]
    # bounce schedule: accelerating, then two suspense beats before the final pass
    iv = [0.85 * (0.30 ** ((k - 1) / (N - 3))) for k in range(1, N - 1)] + [0.55, 1.05]
    LEAD = 0.25; tb = [LEAD] + list(LEAD + np.cumsum(iv))                  # tb[k] = time ball reaches point k
    v_end = tb[N]; CARD = spec.get("card_seconds", 4.0); total = v_end + CARD; LOOP = 0.35
    n_frames = int(round(total * FPS)); n_frames = min(n_frames, int(smoke * FPS)) if smoke else n_frames
    passes = {}
    for b in bm:
        k = math.ceil(math.log2(b["value"])) if b["value"] > 1 else 1
        passes[k] = b
    units = {10: "$1,000", 20: "$1 MILLION", 30: "$1 BILLION", 40: "$1 TRILLION"}
    log(f"[doubling] target {money(target['value'])} -> {N} bounces, star {{{N}/{m}}}, video {total:.1f}s")

    bg = E.make_bg(top=(4, 4, 14), bottom=(14, 4, 26), glow=(50, 20, 90)); E.bake_source_bar(bg, spec["source_line"])
    hue = lambda k: (0.55 + 0.45 * k / N) % 1.0
    col = lambda k: E.hsv(hue(k), .75, 1.0)
    # static layers rebuilt only when a chord completes
    cache = {"k": -1, "layer": None}
    def chords_layer(k):
        if cache["k"] == k: return cache["layer"]
        lay = np.zeros((H, W, 3), np.uint8); g = np.zeros((H // 2, W // 2, 3), np.uint8)
        cv2.circle(g, (CX // 2, CY // 2), R // 2, (60, 30, 140), 5, cv2.LINE_AA)
        for j in range(1, k + 1):
            a, b = pts[j - 1], pts[j]; c = col(j)
            cv2.line(g, (int(a[0] / 2), int(a[1] / 2)), (int(b[0] / 2), int(b[1] / 2)), E.mulc(c, .55), 3, cv2.LINE_AA)
        g = cv2.GaussianBlur(g, (0, 0), 8); lay[:] = cv2.resize(g, (W, H)); lay = cv2.add(lay, lay)
        cv2.circle(lay, (CX, CY), R, (170, 140, 255), 4, cv2.LINE_AA)
        for j in range(1, k + 1):
            a, b = pts[j - 1], pts[j]; cv2.line(lay, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), col(j), 2, cv2.LINE_AA)
        cache.update(k=k, layer=lay); return lay

    title = E.text_sprite(spec.get("title", "EVERY BOUNCE = 2×"), 70, (255, 255, 255), "bold", stroke=5, stroke_color=(0, 0, 0))
    sub = E.text_sprite(spec.get("question", "CAN $1 PASS THE NATIONAL DEBT?"), 36, (255, 210, 120), "bold", spacing=2)
    guess = E.text_sprite("GUESS THE BOUNCE NUMBER · COMMENT IT", 30, (255, 255, 255), "bold", spacing=2)
    almost = E.text_sprite("ALMOST...", 46, (255, 120, 140), "bold", stroke=4, stroke_color=(0, 0, 0), spacing=6)
    rng = np.random.default_rng(7)
    sparks = {k: rng.uniform(0, 2 * math.pi, 9) for k in range(N + 1)}

    def kat(v): return int(np.searchsorted(tb, v, side="right") - 1)   # bounces completed (k=0 at start)
    def draw(i, final=True):
        v = i / FPS; k = max(0, min(kat(v), N)); f = cv2.add(bg, chords_layer(k))
        if k < N:                                                             # live chord + ball + trail
            a, b = pts[k], pts[k + 1]; u = E.clamp((v - tb[k]) / (tb[k + 1] - tb[k])) if v >= tb[0] else 0
            x, y = a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u; c = col(k + 1)
            cv2.line(f, (int(a[0]), int(a[1])), (int(x), int(y)), c, 3, cv2.LINE_AA)
        else:
            x, y = pts[N]; c = col(N)
        for rr, al in ((34, .18), (24, .3)):
            ov = f[int(y) - 40:int(y) + 40, int(x) - 40:int(x) + 40].copy()
            cv2.circle(f, (int(x), int(y)), rr, c, -1, cv2.LINE_AA)
            f[int(y) - 40:int(y) + 40, int(x) - 40:int(x) + 40] = cv2.addWeighted(f[int(y) - 40:int(y) + 40, int(x) - 40:int(x) + 40], al, ov, 1 - al, 0)
        cv2.circle(f, (int(x), int(y)), 15, (255, 255, 255), -1, cv2.LINE_AA)
        if k >= 1:                                                            # impact flash + sparks
            age = v - tb[k]
            if age < .35:
                p = pts[k]; e_ = 1 - age / .35
                cv2.circle(f, (int(p[0]), int(p[1])), int(20 + 70 * (1 - e_)), col(k), max(1, int(6 * e_)), cv2.LINE_AA)
                for a_ in sparks[k]:
                    d = 30 + 110 * (1 - e_); cv2.circle(f, (int(p[0] + d * math.cos(a_)), int(p[1] + d * math.sin(a_))), max(1, int(5 * e_)), (255, 255, 255), -1, cv2.LINE_AA)
        val = 2 ** k; pulse = 1 + .22 * max(0, 1 - (v - tb[k]) / .2) if k >= 1 else 1
        E.blit(f, title, W / 2, 300); E.blit(f, sub, W / 2, 380)
        E.blit(f, E.text_sprite(money(val), 104 if val < 1e6 else 82, col(max(k, 1)), "black", stroke=5, stroke_color=(0, 0, 0)), W / 2, 505, scale=pulse)
        if v < 3.0: E.blit(f, guess, W / 2, 595, alpha=1 - E.smooth((v - 2.6) / .4))
        elif k < N: E.blit(f, E.text_sprite(f"BOUNCE {k}", 30, (190, 190, 220), "bold", spacing=6), W / 2, 595)
        if k in (N - 2, N - 1) and v < v_end: E.blit(f, almost, W / 2, CY, alpha=.6 + .4 * math.sin(v * 12) ** 2)
        for kk, txt in units.items():                                         # unit toasts (pure math)
            if kk <= N and 0 <= v - tb[kk] < 1.0:
                E.blit(f, E.text_sprite(txt + "!", 54, (255, 255, 255), "bold", stroke=4, stroke_color=(0, 0, 0)), W / 2, CY, alpha=1 - E.smooth((v - tb[kk] - .6) / .4), scale=E.out_back((v - tb[kk]) / .25))
        for kk, b in passes.items():                                          # .gov milestone cards
            if kk < N and 0 <= v - tb[kk] < 2.4:
                a_ = E.smooth((v - tb[kk]) / .2) * (1 - E.smooth((v - tb[kk] - 2.0) / .4))
                E.pill(f, 70, 1480, W - 70, 1600, (10, 10, 25), .78 * a_)
                E.blit(f, E.text_sprite("PASSED  " + b["label"] + "  " + money(b["value"]), 31, (255, 220, 120), "bold"), W / 2, 1520, alpha=a_)
                E.blit(f, E.text_sprite(b["detail"], 22, (200, 200, 220), "med"), W / 2, 1565, alpha=a_)
        if v >= v_end:                                                        # reveal card
            u = v - v_end; a_ = E.smooth(u / .3); sc = E.out_back(u / .45)
            f[:1600] = cv2.convertScaleAbs(f[:1600], alpha=1 - .45 * a_)
            if u < .12: f[:1600] = cv2.add(f[:1600], np.full_like(f[:1600], int(160 * (1 - u / .12))))
            E.blit(f, E.text_sprite(f"{N} BOUNCES", 120, (255, 255, 255), "black", stroke=6, stroke_color=(0, 0, 0)), W / 2, 900, alpha=a_, scale=sc)
            E.blit(f, E.text_sprite(f"{money(2**N)} > {target['label'].lower()}", 40, (255, 220, 120), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1010, alpha=a_)
            E.blit(f, E.text_sprite(f"{money(target['value'])} · {target['detail']}", 24, (220, 220, 235), "med", stroke=2, stroke_color=(0, 0, 0)), W / 2, 1062, alpha=E.smooth((u - .2) / .3))
            c = E.smooth((u - .9) / .3)
            E.blit(f, E.text_sprite("DID YOU GUESS IT? COMMENT YOUR NUMBER", 36, (255, 255, 255), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1200, alpha=c)
            E.blit(f, E.text_sprite("SEND THIS TO SOMEONE WHO GUESSED LOW", 30, (190, 220, 255), "bold", stroke=3, stroke_color=(0, 0, 0)), W / 2, 1255, alpha=E.smooth((u - 1.5) / .3))
            E.arrow_down(f, W / 2, 1320 + 8 * math.sin(u * 7), 22, (255, 255, 255), alpha=c)
        if final and v > total - LOOP:
            b_ = E.smooth((v - (total - LOOP)) / LOOP); f = cv2.addWeighted(f, 1 - b_, draw(0, False), b_, 0)
        return f

    # audio: rising arpeggio that modulates up every 6 bounces, tempo set by the bounce schedule
    mix = E.Mix(total); arp = [0, 4, 7, 12, 7, 4]
    mix.add(0.02, E.bell(float(E.midi_hz(84)), 1.0), .2)
    for k in range(1, N + 1):
        note = 57 + arp[k % len(arp)] + (k // 6) * 2; pan = (pts[k][0] - CX) / R * .6
        mix.add(tb[k], E.kalimba(float(E.midi_hz(note + 12)), .9), .5, pan); mix.add(tb[k], E.tick(float(E.midi_hz(note + 24)), .05), .12, pan)
        mix.add(tb[k], E.thump(.25, 200, 80), .25 + .25 * k / N)
        if k in units: mix.add(tb[k], E.bell(float(E.midi_hz(note + 24)), 1.4), .25)
        if k in passes and k < N: mix.add(tb[k], E.chord([note + 12, note + 16, note + 19], 1.6), .3)
    mix.add(tb[N - 6], E.riser(tb[N] - tb[N - 6]), .4)
    mix.add(v_end, E.thump(1.2, 140, 32), 1.0); mix.add(v_end, E.chord([69, 73, 76, 81], 3.0), .5); mix.add(v_end + .05, E.whoosh(.6), .2)
    wav = os.path.join(out_dir, spec["name"] + ".wav"); mix.write(wav)
    if stills:
        for t_ in stills: E.save_png(os.path.join(out_dir, f"{spec['name']}_still_{t_:05.2f}.png"), draw(int(t_ * FPS)))
        return dict(still_only=True, v_end=v_end, total=total, tb=[round(x, 2) for x in tb])
    mp4 = os.path.join(out_dir, spec["name"] + ".mp4"); E.render(mp4, wav, n_frames, draw)
    E.save_png(os.path.join(out_dir, spec["name"] + "_cover.png"), draw(int(spec.get("cover_t", 1.2) * FPS)))
    return dict(mp4=mp4, wav=wav, duration=total, frames=int(round(total * FPS)), bounces=N, final_value=2 ** N,
                passes={k: b["label"] for k, b in passes.items()})
