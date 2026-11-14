# usage: python3 -I puzzles/eyeaudio.py <eyejump_script.json> <out.wav> [seed]
# Audio for the eye-jump drill: a blip exactly on every dot move, risers between
# levels, and a bed that speeds up with the drill. Listenable, all synthesized here.
import sys, json, wave
import numpy as np
sj, out = sys.argv[1], sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 5
RS = np.random.RandomState(seed); S = json.load(open(sj)); SR = 44100
INTRO, LABEL, OUTRO = 2.4, 1.3, 4.2
jumps, T = [], INTRO
for li, L in enumerate(S["levels"]):
    L["t0"] = T; T += LABEL; L["tj"] = T
    gap = 60/L["bpm"]
    for i in range(L["jumps"]): jumps.append((T + i*gap, li, i))
    T += L["jumps"]*gap; L["t1"] = T
DRILL_END = T; DUR = T + OUTRO; N = int(SR*DUR)+SR
mus = np.zeros(N, np.float32); sfx = np.zeros(N, np.float32)
def put(sec, a, g=1.0, tgt=None):
    t = mus if tgt is None else tgt
    s = int(max(0, sec)*SR); n = min(len(a), len(t)-s)
    if n > 0: t[s:s+n] += a[:n]*g
def T_(d): return np.arange(max(1, int(SR*d)))/SR
def env(a, atk=.004, dec=.12):
    t = np.arange(len(a))/SR
    return (a*np.minimum(1, t/max(atk,1e-4))*np.exp(-t/dec)).astype(np.float32)
def blip(f, d=.1):
    t = T_(d); a = np.sin(2*np.pi*f*t)*.8 + .25*np.sin(2*np.pi*f*2*t)
    return env(a.astype(np.float32), .002, .05)
def mallet(f, d=.4):
    t = T_(d)
    a = np.sin(2*np.pi*f*t) + .3*np.sin(2*np.pi*f*4*t)*np.exp(-t*16)
    return (a*np.exp(-t*5)*.5).astype(np.float32)
def chime(f, d=.7):
    t = T_(d); a = np.sin(2*np.pi*f*t) + .4*np.sin(2*np.pi*f*2.01*t)
    return (a*np.exp(-t*3.2)*.4).astype(np.float32)
def subb(f, d=.26):
    return env((np.sin(2*np.pi*f*T_(d))*.9).astype(np.float32), .006, .18)
def kick(d=.24):
    t = T_(d); f = 115*np.exp(-t*26)+46
    return (np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*10)*.9).astype(np.float32)
def hat(d=.04):
    t = T_(d); n = RS.randn(len(t)).astype(np.float32)
    return (n*np.exp(-t*95)*.13).astype(np.float32)
def riser(d=1.0):
    t = T_(d); sweep = np.sin(2*np.pi*np.cumsum(340*np.exp(t*1.8))/SR)
    return (sweep*.45*((t/d)**2.2)).astype(np.float32)
def thud(d=.6):
    t = T_(d); f = 92*np.exp(-t*8)+40
    return (np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*4.4)*.8).astype(np.float32)
PENT = [0,2,4,7,9,12,14,16]; ROOT = 523.25
nf = lambda s, o=0: ROOT*(2**((PENT[s % len(PENT)]+12*o)/12))
# bed: tempo follows the drill so it tightens as levels speed up
t = 0.0; i = 0
HOOK = [0,2,4,2, 5,4,2,0]
while t < DUR:
    lvl = next((L for L in S["levels"] if L["t0"] <= t < L["t1"]), None)
    bpm = 96 if lvl is None else min(150, 80 + lvl["bpm"]*0.22)
    step = (60/bpm)/2
    k = i % 8
    if k in (0,3,6): put(t, kick(), .75)
    put(t, hat(), .5 if k % 2 == 0 else .3)
    put(t, subb(nf(0,-2), step*.9), .45)
    put(t, mallet(nf(HOOK[k]), step*1.6), .3)
    t += step; i += 1
# a blip on every single dot move, pitch climbing through each level
for (jt, li, idx) in jumps:
    L = S["levels"][li]
    f = nf((idx % 5) + li, 1)
    put(jt, blip(f, min(.12, (60/L["bpm"])*.6)), .5, sfx)
for li, L in enumerate(S["levels"]):
    put(L["t0"]-.9, riser(.9), .4, sfx)          # build into the level card
    put(L["t0"], thud(), .5, sfx)                 # level lands
    for i2, s in enumerate([0,2,4]): put(L["t0"]+.08+i2*.09, mallet(nf(s,1),.3), .28, sfx)
put(DRILL_END-.6, riser(.6), .4, sfx)
put(DRILL_END, thud(.7), .55, sfx)
for i2, s in enumerate([0,2,4,7,9]): put(DRILL_END+.35+i2*.12, chime(nf(s,1),.6), .3, sfx)
b = (mus*.95 + sfx*.85)[:int(SR*DUR)]
b = np.tanh(b*1.1)
b *= np.minimum(1, np.arange(len(b))/(SR*.04))
b *= np.clip((len(b)-np.arange(len(b)))/(SR*.35), 0, 1)
b /= max(1e-6, np.max(np.abs(b)))*1.05
w = wave.open(out,'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((b*32767).astype(np.int16).tobytes()); w.close()
print('DUR', round(DUR,2))
