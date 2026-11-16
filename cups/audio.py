"""Event-locked audio for Cup Shuffle. Same sound for every swap (ball or not) so audio never leaks the answer.
Mood (scale/root/timbre) comes from the seed so every video sounds different. Everything is synthesized."""
import json, math, sys, wave
import numpy as np
SR = 48000
MOODS = {  # root midi, scale steps, timbre
    "marimba":  (57, [0, 2, 4, 7, 9], "mar"), "pluck": (60, [0, 3, 5, 7, 10], "plk"),
    "glass":    (64, [0, 2, 4, 6, 9], "gls"), "kalimba": (59, [0, 2, 3, 7, 8], "kal"),
    "wood":     (55, [0, 2, 5, 7, 9], "mar"), "bell": (62, [0, 4, 5, 7, 11], "gls"),
}
def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def T(d): return np.arange(int(d * SR)) / SR
def tone(f, d, kind):
    t = T(d)
    if kind == "mar": s = np.sin(2*np.pi*f*t) * np.exp(-t*7) + .35*np.sin(2*np.pi*f*4*t)*np.exp(-t*30)
    elif kind == "plk": s = (np.sin(2*np.pi*f*t) + .4*np.sin(2*np.pi*f*2*t)*np.exp(-t*10) + .2*np.sin(2*np.pi*f*3*t)*np.exp(-t*18)) * np.exp(-t*9)
    elif kind == "gls": s = np.sin(2*np.pi*f*t + 1.6*np.sin(2*np.pi*f*2.76*t)*np.exp(-t*8)) * np.exp(-t*4.2)
    else: s = (np.sin(2*np.pi*f*t) + .3*np.sin(2*np.pi*f*5.4*t)*np.exp(-t*30)) * np.exp(-t*5.5)
    return (s * (1 - np.exp(-t*1500))).astype(np.float32)
def clack(seed, bright=1.0):      # wooden-plastic cup tap: filtered noise burst + short body resonance
    rng = np.random.default_rng(seed); t = T(0.13); n = rng.standard_normal(len(t))
    n = np.convolve(n, np.ones(5)/5, "same") * np.exp(-t*85)
    body = np.sin(2*np.pi*(310+rng.uniform(-30, 30))*bright*t) * np.exp(-t*48)
    return ((n*.9 + body*.8) * (1 - np.exp(-t*4000))).astype(np.float32)
def slide(d, seed):               # soft cup-on-wood slide
    rng = np.random.default_rng(seed); t = T(d); n = rng.standard_normal(len(t)); n = np.convolve(n, np.ones(40)/40, "same")
    return (n * np.sin(np.pi*t/d)**2 * .5).astype(np.float32)
def thump(d=0.35, f0=130, f1=48):
    t = T(d); f = f1 + (f0-f1)*np.exp(-t*16); return (np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t*9) * (1-np.exp(-t*1200))).astype(np.float32)
def riser(d, f0=180, f1=2200):
    t = T(d); u = t/d; f = f0*(f1/f0)**u; n = np.convolve(np.random.default_rng(3).standard_normal(len(t)), np.ones(6)/6, "same")
    return ((.5*np.sin(2*np.pi*np.cumsum(f)/SR) + .35*n) * u**2.4 * .5).astype(np.float32)

class Mix:
    def __init__(s, d): s.n = int(d*SR); s.L = np.zeros(s.n, np.float32); s.R = np.zeros(s.n, np.float32)
    def add(s, t, sig, g=1.0, pan=0.0):
        i = int(round(t*SR))
        if i < 0 or i >= s.n: return
        m = min(len(sig), s.n-i); a = (pan+1)*math.pi/4; s.L[i:i+m] += sig[:m]*g*math.cos(a); s.R[i:i+m] += sig[:m]*g*math.sin(a)

def build(plan, wav_path, mood=None):
    rng = np.random.default_rng(plan["seed"]); names = sorted(MOODS); mood = mood or names[plan["seed"] % len(names)]
    root, scale, kind = MOODS[mood]; D = plan["duration"]; m = Mix(D)
    note = lambda i: root + 12*(i//len(scale)) + scale[i % len(scale)]
    # ---- bed: soft pad that tightens as the shuffle speeds up
    t = T(D); s0, s1 = plan["t_shuffle"]
    pad = sum(np.sin(2*np.pi*hz(root-12+iv)*t) * .5 for iv in (0, 7, 12)) * .05
    env = np.clip((t-0.2)/1.0, 0, 1) * (0.55 + 0.45*np.clip((t-s0)/(s1-s0), 0, 1)) * np.clip((D-t)/0.5, 0, 1)
    pad *= env * (1 + .15*np.sin(2*np.pi*.5*t)); m.L += pad.astype(np.float32); m.R += pad.astype(np.float32)
    # ---- opening: ball clink as the cup lowers, thump when it lands
    l0, l1 = plan["t_lower"]
    m.add(0.02, tone(hz(note(7)), .9, "gls"), .5); m.add(0.06, tone(hz(note(9)), .9, "gls"), .35)
    m.add(l0, slide(l1-l0, 1), .5); m.add(l1-0.01, thump(.4, 150, 55), .9); m.add(l1-0.01, clack(2, .8), .7)
    # ---- shuffle: every swap = slide + two clacks; a melodic tick per event that climbs with speed (same for ball / no ball)
    for k, e in enumerate(plan["events"]):
        u = (e["t0"]-s0)/(s1-s0); d = e["dur"]
        for j, (a, b, side) in enumerate(e["pairs"]):
            pan = rng.uniform(-.6, .6)
            m.add(e["t0"], slide(d, 10+k*3+j), .22+.18*u, pan)
            m.add(e["t0"]+0.015, clack(100+k*5+j, 1.0), .26, pan); m.add(e["t0"]+d-0.012, clack(200+k*5+j, 1.07), .34, pan)
        idx = int(u*9) + (k % 3)
        m.add(e["t0"]+d-0.01, tone(hz(note(idx)+0), .5, kind), .28+.14*u, 0.0)
    m.add(s1-2.6, riser(2.6+(plan["t_badges"]-s1)), .55)
    # ---- ending: number badges pop in a rising arpeggio, then an unresolved question chord (no resolution = invites comments)
    for cl in range(16):
        tt = plan["t_badges"] + cl*0.035
        m.add(tt, tone(hz(note(cl % 10 + 5)), .35, "gls"), .16, (cl % 4 - 1.5)/2.2)
    q = plan["t_badges"] + 0.3
    for iv in (0, 4, 9):
        m.add(q, tone(hz(root+12+scale[iv % 5]+(7 if iv == 9 else 0)), 1.6, kind), .22)
    m.add(q, thump(.5, 110, 40), .5)
    # ---- master
    x = np.stack([m.L, m.R], 1); x = np.tanh(x*1.2)/np.tanh(1.2); x *= 0.88/max(1e-6, np.abs(x).max())
    k = int(.35*SR); x[-k:] *= np.linspace(1, 0, k)[:, None]
    with wave.open(wav_path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x*32767).astype(np.int16).tobytes())
    return mood
if __name__ == "__main__":
    plan = json.load(open(sys.argv[1])); print(build(plan, sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None))
