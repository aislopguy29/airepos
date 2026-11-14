# usage: python3 -I puzzles/eyeaudio.py <eyejump_script.json> <out.wav> [seed]
# Audio for the eye-jump drill. Every dot move gets its own voice: 14 distinct timbres
# crossed with pitches, and no (timbre, pitch) pair is ever used twice in one video.
import sys, json, wave
import numpy as np
sj, out = sys.argv[1], sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 5
RS = np.random.RandomState(seed); S = json.load(open(sj)); SR = 44100
INTRO = S.get("intro", 0.9); LABEL = S.get("label_beat", 0.55); OUTRO = 3.6
jumps, T = [], INTRO
for li, L in enumerate(S["levels"]):
    L["t0"] = T; T += LABEL; L["tj"] = T
    gap = 60/L["bpm"]
    for i in range(L["jumps"]): jumps.append((T + i*gap, li, i, gap))
    T += L["jumps"]*gap; L["t1"] = T
DRILL_END = T; DUR = T + OUTRO; N = int(SR*DUR)+SR
mus = np.zeros(N, np.float32); sfx = np.zeros(N, np.float32)
def put(sec, a, g=1.0, tgt=None):
    t = mus if tgt is None else tgt
    s = int(max(0, sec)*SR); n = min(len(a), len(t)-s)
    if n > 0: t[s:s+n] += a[:n]*g
def T_(d): return np.arange(max(1, int(SR*d)))/SR
def dec(a, r): 
    t = np.arange(len(a))/SR; return (a*np.exp(-t*r)).astype(np.float32)
def atk(a, ms=3.0):
    t = np.arange(len(a))/SR; return (a*np.minimum(1, t/(ms/1000))).astype(np.float32)
# ---- 14 distinct voices ----
def v_sine(f,d):   return atk(dec(np.sin(2*np.pi*f*T_(d)), 26))
def v_square(f,d): t=T_(d); return atk(dec(np.where((t*f)%1<.5,1.,-1.)*.5, 30))
def v_tri(f,d):    t=T_(d); return atk(dec((2*np.abs(2*((t*f)%1)-1)-1)*.7, 24))
def v_marimba(f,d):t=T_(d); return dec(np.sin(2*np.pi*f*t)+.35*np.sin(2*np.pi*f*4*t)*np.exp(-t*18), 16)
def v_bell(f,d):   t=T_(d); return dec(np.sin(2*np.pi*f*t)+.5*np.sin(2*np.pi*f*2.76*t)+.25*np.sin(2*np.pi*f*5.4*t), 7)*.5
def v_wood(f,d):   t=T_(d); return dec(np.sin(2*np.pi*f*1.6*t)*.9, 55)
def v_kalimba(f,d):t=T_(d); return atk(dec(np.sin(2*np.pi*f*t)*.8+.2*np.sin(2*np.pi*f*2.004*t), 13), 1.5)
def v_zap(f,d):    t=T_(d); return dec(np.sin(2*np.pi*np.cumsum(f*2.2*np.exp(-t*14))/SR), 22)
def v_bubble(f,d): t=T_(d); return dec(np.sin(2*np.pi*np.cumsum(f*.55*np.exp(t*9))/SR), 26)
def v_glass(f,d):  t=T_(d); return dec(np.sin(2*np.pi*f*2*t)*.6+.3*np.sin(2*np.pi*f*3.01*t), 10)*.7
def v_clave(f,d):  t=T_(d); n=RS.randn(len(t)).astype(np.float32)
                   # tone + tiny noise transient
def v_clave(f,d):
    t=T_(d); n=RS.randn(len(t)).astype(np.float32)
    return dec(np.sin(2*np.pi*f*1.9*t)*.8 + n*np.exp(-t*220)*.3, 60)
def v_string(f,d):            # karplus-strong pluck
    n = int(SR/max(60,f)); buf = RS.randn(n).astype(np.float32)
    outp = np.zeros(int(SR*d), np.float32)
    for i in range(len(outp)):
        outp[i] = buf[i % n]
        buf[i % n] = .5*(buf[i % n] + buf[(i+1) % n])*.996
    return dec(outp*.7, 6)
def v_koto(f,d):
    t=T_(d); bend = f*(1+.06*np.exp(-t*16))
    return dec(np.sin(2*np.pi*np.cumsum(bend)/SR)*.8+.2*np.sin(2*np.pi*np.cumsum(bend*2)/SR), 11)
def v_vibe(f,d):
    t=T_(d); trem = 1+.35*np.sin(2*np.pi*6.5*t)
    return dec(np.sin(2*np.pi*f*t)*trem*.8, 9)
VOICES = [v_sine, v_square, v_tri, v_marimba, v_bell, v_wood, v_kalimba,
          v_zap, v_bubble, v_glass, v_clave, v_string, v_koto, v_vibe]
PENT = [0,2,4,7,9,12,14,16,19,21]; ROOT = 523.25
NOTES = [ROOT*(2**((PENT[i % len(PENT)]+12*(i//len(PENT)))/12)) for i in range(len(PENT)*2)]
# every jump gets a unique (voice, note); adjacent jumps never share a voice family
used = set(); order = list(range(len(VOICES))); RS.shuffle(order)
vi = 0; last_v = -1
for (jt, li, idx, gap) in jumps:
    d = min(.22, gap*.85)
    for _ in range(400):
        v = order[vi % len(order)]; vi += 1
        n = (idx*3 + li*5 + vi) % len(NOTES)
        if v != last_v and (v, n) not in used:
            used.add((v, n)); last_v = v
            put(jt, VOICES[v](NOTES[n], d), .55, sfx)
            break
# bed: sparse so the voices read, tempo rises with the drill
def kick(d=.22):
    t=T_(d); f=115*np.exp(-t*26)+46
    return (np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*11)*.85).astype(np.float32)
def hat(d=.035):
    t=T_(d); return (RS.randn(len(t)).astype(np.float32)*np.exp(-t*100)*.1)
def subb(f,d=.24): return atk(dec(np.sin(2*np.pi*f*T_(d))*.9, 6), 5)
t = 0.0; i = 0
while t < DUR:
    lvl = next((L for L in S["levels"] if L["t0"] <= t < L["t1"]), None)
    bpm = 100 if lvl is None else min(160, 84 + lvl["bpm"]*0.2)
    step = (60/bpm)/2; k = i % 8
    if k in (0,4): put(t, kick(), .7)
    if k % 2 == 1: put(t, hat(), .5)
    if k in (0,6): put(t, subb(NOTES[0]/4, step*1.4), .4)
    t += step; i += 1
def riser(d=.8):
    t=T_(d); return (np.sin(2*np.pi*np.cumsum(360*np.exp(t*1.9))/SR)*.45*((t/d)**2.2)).astype(np.float32)
def thud(d=.55):
    t=T_(d); f=95*np.exp(-t*9)+40
    return (np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*5)*.8).astype(np.float32)
for li, L in enumerate(S["levels"]):
    put(L["t0"]-.7, riser(.7), .38, sfx)
    put(L["t0"], thud(), .5, sfx)
put(DRILL_END-.5, riser(.5), .4, sfx); put(DRILL_END, thud(.7), .55, sfx)
for i2 in range(5): put(DRILL_END+.3+i2*.12, VOICES[(order[i2]) % len(VOICES)](NOTES[i2+4], .5), .3, sfx)
b = (mus*.8 + sfx*1.0)[:int(SR*DUR)]
b = np.tanh(b*1.12)
b *= np.minimum(1, np.arange(len(b))/(SR*.03))
b *= np.clip((len(b)-np.arange(len(b)))/(SR*.3), 0, 1)
b /= max(1e-6, np.max(np.abs(b)))*1.05
w = wave.open(out,'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((b*32767).astype(np.int16).tobytes()); w.close()
print('DUR', round(DUR,2), '| unique sounds used:', len(used), '| jumps:', len(jumps))
