# usage: python3 -I puzzles/memeaudio.py <script.json> <out.wav> [seed]
# Clickbaity but listenable bed: catchy pentatonic hook, soft trap-ish kit,
# tonal risers and chimes synced to the puzzle timeline. All synthesized here.
import sys, json, wave
import numpy as np
sj, out = sys.argv[1], sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
RS = np.random.RandomState(seed)
S = json.load(open(sj)); SR = 44100
INTRO, SEARCH, REVEAL, OUTRO = 1.9, S.get('search', 2.9), 1.9, 3.6
NR = len(S['rounds']); DUR = INTRO + NR*(SEARCH+REVEAL) + OUTRO
N = int(SR*DUR)+SR
mus = np.zeros(N, np.float32); sfx = np.zeros(N, np.float32)
def put(sec, a, g=1.0, tgt=None):
    t = mus if tgt is None else tgt
    s = int(max(0, sec)*SR); n = min(len(a), len(t)-s)
    if n > 0: t[s:s+n] += a[:n]*g
def T(d): return np.arange(max(1, int(SR*d)))/SR
def lp(x, cut):                                  # one-pole lowpass: tames harshness
    a = np.exp(-2*np.pi*cut/SR); y = np.zeros_like(x); acc = 0.0
    for i in range(0, len(x), 512):              # block-wise lfilter
        blk = x[i:i+512]
        for j, v in enumerate(blk):
            acc = a*acc + (1-a)*v; y[i+j] = acc
    return y
def env(a, atk=.004, dec=.14):
    t = np.arange(len(a))/SR
    return (a*np.minimum(1, t/max(atk,1e-4))*np.exp(-t/dec)).astype(np.float32)
# ---- warm, rounded instruments ----
def mallet(f, d=.42):                            # marimba-ish: the hook voice
    t = T(d)
    a = np.sin(2*np.pi*f*t) + .32*np.sin(2*np.pi*f*4*t)*np.exp(-t*16) + .12*np.sin(2*np.pi*f*9.2*t)*np.exp(-t*28)
    return (a*np.exp(-t*5.0)*.55).astype(np.float32)
def chime(f, d=.8):
    t = T(d)
    a = np.sin(2*np.pi*f*t) + .45*np.sin(2*np.pi*f*2.01*t) + .2*np.sin(2*np.pi*f*3.0*t)
    return (a*np.exp(-t*3.2)*.4).astype(np.float32)
def pluck(f, d=.2):
    t = T(d)
    a = np.sin(2*np.pi*f*t)*.7 + .25*np.sin(2*np.pi*f*2*t) + .08*np.sin(2*np.pi*f*3*t)
    return env(a.astype(np.float32), .003, .12)
def sub(f, d=.26):
    t = T(d); a = np.sin(2*np.pi*f*t)*.9 + .12*np.sin(2*np.pi*f*2*t)
    return env(a.astype(np.float32), .006, .18)
def kick(d=.26):
    t = T(d); f = 118*np.exp(-t*26)+46
    return (np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*9.5)*.95).astype(np.float32)
def snap(d=.16):                                 # soft finger-snap instead of harsh clap
    t = T(d); n = lp(RS.randn(len(t)).astype(np.float32), 5200)
    return (n*np.exp(-t*34)*.5 + np.sin(2*np.pi*1700*t)*np.exp(-t*60)*.12).astype(np.float32)
def hat(d=.04, open_=False):
    t = T(d*(3 if open_ else 1))
    n = lp(RS.randn(len(t)).astype(np.float32), 9000)
    return (n*np.exp(-t*(20 if open_ else 90))*.16).astype(np.float32)
def woodblock(f=1150, d=.07):                    # countdown tick (tonal, not noise)
    t = T(d); return (np.sin(2*np.pi*f*t)*np.exp(-t*48)*.3).astype(np.float32)
# ---- ear candy, rounded off ----
def riser(d=1.3):                                # tonal sweep, light filtered air
    t = T(d); sweep = np.sin(2*np.pi*np.cumsum(330*np.exp(t*1.7))/SR)
    air = lp(RS.randn(len(t)).astype(np.float32), 2600)*.18
    return ((sweep*.5 + air)*((t/d)**2.2)).astype(np.float32)
def whoosh(d=.45):
    t = T(d); n = lp(RS.randn(len(t)).astype(np.float32), 1800)
    return (n*np.sin(np.pi*t/d)*.5).astype(np.float32)
def thud(d=.7):                                  # reveal impact, mostly low end
    t = T(d); f = 90*np.exp(-t*8)+40
    return (np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*4.2)*.85).astype(np.float32)
def sparkle(d=.7, root=1046.5):
    o = np.zeros(int(SR*d)+SR//3, np.float32)
    for i in range(6):
        f = root*(2**(RS.choice([0,2,4,7,9,12])/12))
        a = chime(f,.5); s = int(i*.055*SR); n = min(len(a), len(o)-s); o[s:s+n] += a[:n]*.45
    return o
# ---- the hook: short, catchy, repeats so it sticks ----
BPM = 138; beat = 60/BPM; step = beat/2
PENT = [0,2,4,7,9,12,14,16,19,21]; ROOT = 523.25
HOOK = [0,2,4,2, 5,4,2,0, 4,5,7,5, 4,2,0,2]     # singable, loops every 2 bars
BASSN= [0,0,-3,-3, -5,-5,-1,-1]
def nf(s, o=0): return ROOT*(2**((PENT[s % len(PENT)]+12*o)/12))
def bf(s): return ROOT/4*(2**((PENT[abs(s) % len(PENT)]*np.sign(s))/12))
kick_times = []
for i in range(int(DUR/step)+4):
    t = i*step + (beat*.05 if i % 2 else 0) + RS.uniform(-.005,.005)
    k = i % 16
    if k in (0,3,6,8,11,14): put(t, kick(), .85); kick_times.append(t)
    if k in (4,12): put(t, snap(), .5)
    put(t, hat(.04, k % 8 == 6), .5 if k % 2 == 0 else .3)
    put(t, sub(bf(BASSN[(i//2) % 8])*2, beat*.5), .5)
    put(t, mallet(nf(HOOK[k], 0), beat*.9), .42)                 # the hook
    if k % 4 == 2: put(t, pluck(nf(HOOK[k]+2, 1), step*.8), .14)  # sparkle layer
# ---- synced to the edit ----
put(.0, whoosh(.5), .45, sfx); put(.08, sparkle(.7, 1318), .35, sfx)
for r in range(NR):
    t0 = INTRO + r*(SEARCH+REVEAL); tr = t0 + SEARCH
    put(t0-.2, whoosh(.4), .4, sfx)
    for s in range(3):                                            # three clean ticks
        ts = tr - (s+1)*.5
        if ts > t0: put(ts, woodblock(1050 + s*180), .5, sfx)
    put(tr-1.2, riser(1.2), .45, sfx)
    put(tr, thud(), .55 if r < NR-1 else .7, sfx)
    put(tr+.05, sparkle(.7), .4, sfx)
    for i, s in enumerate([0,2,4,7]): put(tr+.1+i*.1, mallet(nf(s,1), .35), .3, sfx)
tO = INTRO + NR*(SEARCH+REVEAL)
put(tO-.25, whoosh(.45), .45, sfx); put(tO, sparkle(1.0), .45, sfx); put(tO, thud(.6), .4, sfx)
for i, s in enumerate([0,2,4,7,9]): put(tO+.4+i*.12, chime(nf(s,1), .6), .3, sfx)
# ---- gentle sidechain so it breathes without pumping hard ----
duck = np.ones(N, np.float32)
for kt in kick_times:
    s = int(kt*SR); e = min(N, s+int(.13*SR))
    if 0 <= s < N and e > s: duck[s:e] = np.minimum(duck[s:e], np.linspace(.62, 1.0, e-s))
mus *= duck
for r in range(NR):                                               # dip under each build
    tr = INTRO + r*(SEARCH+REVEAL) + SEARCH
    a, b = max(0, int((tr-1.2)*SR)), min(N, int(tr*SR))
    if b > a: mus[a:b] *= np.linspace(1.0, .6, b-a)
    c = min(N, int((tr+.2)*SR))
    if c > b: mus[b:c] *= np.linspace(.5, 1.0, c-b)
b = (mus*1.0 + sfx*.72)[:int(SR*DUR)]
b = np.tanh(b*1.08)                                               # light glue, no crush
b *= np.minimum(1, np.arange(len(b))/(SR*.04))
b *= np.clip((len(b)-np.arange(len(b)))/(SR*.35), 0, 1)
b /= max(1e-6, np.max(np.abs(b)))*1.05
w = wave.open(out,'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((b*32767).astype(np.int16).tobytes()); w.close()
print('DUR', round(DUR,2))
