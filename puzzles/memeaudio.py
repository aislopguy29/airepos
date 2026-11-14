# usage: python3 -I puzzles/memeaudio.py <script.json> <out.wav> [seed]
# Light bouncy house bed + sounds attached to what actually happens on screen:
# the grid popping in, the clock running down, the build, the reveal hit, the confetti.
# No melody, no hook. All synthesized here.
import sys, json, wave
import numpy as np
sj, out = sys.argv[1], sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
RS = np.random.RandomState(seed)
S = json.load(open(sj)); SR = 44100
INTRO, SEARCH, REVEAL, OUTRO = 1.9, S.get('search', 2.9), 1.9, 3.6
NR = len(S['rounds']); DUR = INTRO + NR*(SEARCH+REVEAL) + OUTRO
N = int(SR*DUR)+SR
bed = np.zeros(N, np.float32); ev = np.zeros(N, np.float32)
def put(sec, a, g=1.0, tgt=None):
    t = bed if tgt is None else tgt
    s = int(max(0, sec)*SR); n = min(len(a), len(t)-s)
    if n > 0: t[s:s+n] += a[:n]*g
def T(d): return np.arange(max(1, int(SR*d)))/SR
def dec(a, r):
    t = np.arange(len(a))/SR; return (a*np.exp(-t*r)).astype(np.float32)
def atk(a, ms=2.0):
    t = np.arange(len(a))/SR; return (a*np.minimum(1, t/(ms/1000))).astype(np.float32)
def lp(x, cut):
    a = np.exp(-2*np.pi*cut/SR); y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc = a*acc + (1-a)*x[i]; y[i] = acc
    return y
# ---------- the bed: light house, bouncy, no melody ----------
def kick(d=.30):
    t = T(d); f = 125*np.exp(-t*30)+48
    body = np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*8.5)
    click = np.exp(-t*900)*.25
    return (np.tanh((body+click)*1.25)*.95).astype(np.float32)
def hat(open_=False):
    d = .14 if open_ else .035
    t = T(d); n = RS.randn(len(t)).astype(np.float32)
    n = n - lp(n, 6000)                      # high passed
    return (n*np.exp(-t*(16 if open_ else 110))*(.16 if open_ else .13)).astype(np.float32)
def clap(d=.22):
    t = T(d); n = RS.randn(len(t)).astype(np.float32); n = n - lp(n, 1200)
    e = np.exp(-t*20) + .6*np.exp(-np.abs(t-.010)*420) + .6*np.exp(-np.abs(t-.022)*420)
    return (n*e*.33).astype(np.float32)
def bass(f, d=.20):                          # short bouncy sub
    t = T(d); a = np.sin(2*np.pi*f*t)*.9 + .1*np.sin(2*np.pi*f*2*t)
    return atk(dec(a.astype(np.float32), 9), 4)
BPM = 124; beat = 60/BPM; step = beat/2
ROOT = 65.41                                  # C2
BOUNCE = [0, 12, 0, 7, 0, 12, 7, 0]           # octave-bounce bassline, no tune
kick_times = []
for i in range(int(DUR/step)+4):
    t = i*step; k = i % 8
    if k % 2 == 0: put(t, kick(), .92); kick_times.append(t)     # four on the floor
    if k in (2, 6): put(t, clap(), .5)                            # 2 and 4
    put(t, hat(False), .55 if k % 2 == 0 else .4)
    if k % 2 == 1: put(t + step*.5, hat(True), .5)                # offbeat open hat
    put(t + step*.25, bass(ROOT*(2**(BOUNCE[k]/12)), step*.8), .55)
# ---------- event sounds ----------
def blip(f, d=.085):                          # grid cell landing
    t = T(d); a = np.sin(2*np.pi*f*t)*.8 + .2*np.sin(2*np.pi*f*2*t)
    return atk(dec(a.astype(np.float32), 34), 1.2)
def wood(f, d=.07):                           # clock tick
    t = T(d); return dec(np.sin(2*np.pi*f*t)*.75, 52)
def riser(d=1.15):                            # the build
    t = T(d); sweep = np.sin(2*np.pi*np.cumsum(300*np.exp(t*2.0))/SR)
    air = lp(RS.randn(len(t)).astype(np.float32), 2400)*.22
    trem = 1 + .25*np.sin(2*np.pi*(5+16*t/d)*t)
    return (((sweep*.5 + air)*trem)*((t/d)**2.1)).astype(np.float32)
def whoosh(d=.4):
    t = T(d); n = lp(RS.randn(len(t)).astype(np.float32), 1700)
    return (n*np.sin(np.pi*t/d)*.5).astype(np.float32)
def hit(d=.75):                               # reveal impact
    t = T(d); f = 100*np.exp(-t*10)+42
    low = np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*4.5)
    snap = lp(RS.randn(len(t)).astype(np.float32), 5000)*np.exp(-t*34)*.35
    return (np.tanh((low+snap)*1.2)*.9).astype(np.float32)
def chime(f, d=.55):
    t = T(d); a = np.sin(2*np.pi*f*t) + .4*np.sin(2*np.pi*f*2.01*t) + .15*np.sin(2*np.pi*f*3*t)
    return (a*np.exp(-t*4.2)*.42).astype(np.float32)
def sparkle(t0, root=1318.5, n=7, spread=.5):  # confetti glitter
    for i in range(n):
        f = root*(2**(RS.choice([0,2,4,7,9,12,16,19])/12))
        put(t0 + i*(spread/n) + RS.uniform(0,.02), chime(f,.45), .33, ev)
def ding(f=1760, d=.5):                        # the satisfying confirm
    t = T(d); a = np.sin(2*np.pi*f*t)*.7 + .35*np.sin(2*np.pi*f*1.5*t) + .2*np.sin(2*np.pi*f*2*t)
    return (a*np.exp(-t*6)*.5).astype(np.float32)
PENT = [0,2,4,7,9,12,14,16,19,21,24]
nf = lambda s: 523.25*(2**(PENT[s % len(PENT)]/12))
put(.0, whoosh(.45), .5, ev); sparkle(.05, 1046.5, 6, .45)
for r, rd in enumerate(S['rounds']):
    t0 = INTRO + r*(SEARCH+REVEAL); tr = t0 + SEARCH
    cells = rd.get('cols',5)*rd.get('rows',7)
    put(t0-.18, whoosh(.38), .45, ev)
    # the grid popping in: one blip per cell, pitch climbing with the stagger (matches the visual)
    for k in range(cells):
        pt = t0 + .01*k
        if pt > tr - .2: break
        put(pt, blip(nf(k % 11)*(1 if k < 40 else .5), .07), .17, ev)
    # clock: ticks on each whole second left, rising, tightening
    secs = int(SEARCH)
    for s in range(secs, 0, -1):
        ts = tr - s
        if ts > t0 + .15: put(ts, wood(900 + (secs-s)*210), .5, ev)
    put(tr - 1.15, riser(1.15), .5, ev)                       # build
    put(tr, hit(), .75 if r < NR-1 else .9, ev)               # reveal lands
    put(tr + .05, ding(1760 if r < NR-1 else 2093), .5, ev)   # confirm
    sparkle(tr + .30, 1318.5, 8, .6)                          # confetti
tO = INTRO + NR*(SEARCH+REVEAL)
put(tO - .35, whoosh(.45), .5, ev); put(tO, hit(.7), .6, ev)
sparkle(tO + .1, 1046.5, 10, .9)
for i, s in enumerate([0,2,4,7,9]): put(tO + .5 + i*.11, chime(nf(s), .5), .3, ev)
# ---------- sidechain the bed under the kick, duck it under each build ----------
duck = np.ones(N, np.float32)
for kt in kick_times:
    s = int(kt*SR); e = min(N, s+int(.15*SR))
    if 0 <= s < N and e > s: duck[s:e] = np.minimum(duck[s:e], np.linspace(.45, 1.0, e-s))
bed *= duck
for r in range(NR):
    tr = INTRO + r*(SEARCH+REVEAL) + SEARCH
    a, b = max(0, int((tr-1.15)*SR)), min(N, int(tr*SR))
    if b > a: bed[a:b] *= np.linspace(1.0, .35, b-a)          # bed drops away into the build
    c = min(N, int((tr+.35)*SR))
    if c > b: bed[b:c] *= np.linspace(.15, 1.0, c-b)          # and slams back after the hit
b = (bed*.85 + ev*1.0)[:int(SR*DUR)]
b = np.tanh(b*1.1)
b *= np.minimum(1, np.arange(len(b))/(SR*.03))
b *= np.clip((len(b)-np.arange(len(b)))/(SR*.3), 0, 1)
b /= max(1e-6, np.max(np.abs(b)))*1.04
w = wave.open(out,'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((b*32767).astype(np.int16).tobytes()); w.close()
print('DUR', round(DUR,2))
