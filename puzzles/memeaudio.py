# usage: python3 -I puzzles/memeaudio.py <script.json> <out.wav> [seed]
# Max-brainrot "AI slop" audio bed: relentless bright loop, sidechain pump, risers,
# whooshes, sparkles and impacts synced to the puzzle timeline. All synthesized here.
import sys, json, wave
import numpy as np
sj, out = sys.argv[1], sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 7
RS = np.random.RandomState(seed)
S = json.load(open(sj)); SR = 44100
INTRO, SEARCH, REVEAL, OUTRO = 1.9, S.get('search', 2.9), 1.9, 3.6
NR = len(S['rounds']); DUR = INTRO + NR*(SEARCH+REVEAL) + OUTRO
N = int(SR*DUR)+SR
mus = np.zeros(N, np.float32)   # musical bed (gets sidechain pump)
sfx = np.zeros(N, np.float32)   # ear candy on top
def put(sec, a, g=1.0, tgt=None):
    t = mus if tgt is None else tgt
    s = int(max(0, sec)*SR); n = min(len(a), len(t)-s)
    if n > 0: t[s:s+n] += a[:n]*g
def T(d): return np.arange(max(1,int(SR*d)))/SR
def sq(f, d, duty=.5, det=0.): 
    t=T(d); return np.where((t*f*(1+det)) % 1.0 < duty, 1., -1.).astype(np.float32)
def saw(f,d): t=T(d); return (2*((t*f)%1.)-1).astype(np.float32)
def env(a, atk=.004, dec=.12):
    t=np.arange(len(a))/SR; return (a*np.minimum(1,t/max(atk,1e-4))*np.exp(-t/dec)).astype(np.float32)
# ---- instruments (bright, plasticky, generic-upbeat on purpose) ----
def pluck(f,d=.17):
    a = sq(f,d,.5,RS.uniform(-.006,.006))*.45 + sq(f*2.01,d,.25)*.18 + np.sin(2*np.pi*f*T(d))*.3
    return env(a,.002,.1)
def bell(f,d=.5):
    t=T(d); a=np.sin(2*np.pi*f*t)+.5*np.sin(2*np.pi*f*2.76*t)+.25*np.sin(2*np.pi*f*5.4*t)
    return (a*np.exp(-t*4.5)*.4).astype(np.float32)
def sub(f,d=.22):
    a = np.sin(2*np.pi*f*T(d))*.8 + sq(f,d,.5)*.2; return env(a,.004,.15)
def kick(d=.24):
    t=T(d); f=135*np.exp(-t*28)+48
    return (np.tanh(np.sin(2*np.pi*np.cumsum(f)/SR)*1.4)*np.exp(-t*10)).astype(np.float32)
def clap(d=.2):
    t=T(d); n=RS.randn(len(t))
    e=np.exp(-t*24)+.5*np.exp(-np.abs(t-.012)*300)+.5*np.exp(-np.abs(t-.026)*300)
    return (n*e*.45).astype(np.float32)
def hat(d=.045,open_=False):
    t=T(d*(3 if open_ else 1)); return (RS.randn(len(t))*np.exp(-t*(22 if open_ else 95))*.3).astype(np.float32)
# ---- ear candy ----
def whoosh(d=.55, up=True):
    t=T(d); n=RS.randn(len(t))
    sw=np.sin(2*np.pi*np.cumsum(np.linspace(200,2600,len(t)) if up else np.linspace(2600,200,len(t)))/SR)
    amp=(t/d)**1.6 if up else np.exp(-t*4)
    return ((n*.45+sw*.35)*amp).astype(np.float32)
def riser(d=1.4):
    t=T(d); n=RS.randn(len(t))
    sw=np.sin(2*np.pi*np.cumsum(300*np.exp(t*2.2))/SR)
    trem=1+.5*np.sin(2*np.pi*(4+14*t/d)*t)
    return (((n*.3+sw*.55)*trem)*((t/d)**2)).astype(np.float32)
def sparkle(d=.7, root=1046.5):
    o=np.zeros(int(SR*d)+SR//4,np.float32)
    for i in range(9):
        f=root*(2**(RS.choice([0,2,4,7,9,12,16])/12))
        a=bell(f,.45); s=int(i*.05*SR); n=min(len(a),len(o)-s); o[s:s+n]+=a[:n]*.5
    return o
def impact(d=1.0):
    t=T(d); f=80*np.exp(-t*9)+36
    body=np.tanh(np.sin(2*np.pi*np.cumsum(f)/SR)*1.7)*np.exp(-t*3.6)
    return (body*.8 + RS.randn(len(t))*np.exp(-t*16)*.3).astype(np.float32)
def tickk(hi=False):
    t=T(.045); return (RS.randn(len(t))*np.exp(-t*120)*(.55 if hi else .35)).astype(np.float32)
def pop(d=.08):
    t=T(d); f=1100*np.exp(-t*28)+340
    return (np.sin(2*np.pi*np.cumsum(f)/SR)*np.exp(-t*30)*.7).astype(np.float32)
def boing(d=.5):
    t=T(d); f=520*np.exp(-t*6)+90
    return (np.sin(2*np.pi*np.cumsum(f*(1+.3*np.sin(2*np.pi*13*t)))/SR)*np.exp(-t*5)).astype(np.float32)
# ---- relentless loop: bright major arp, four-on-floor, never stops ----
BPM=146; beat=60/BPM; step=beat/2
SC=[0,2,4,7,9,12,14,16,19]; ROOT=523.25
ARP=[0,2,4,6,4,2,0,2, 1,3,5,7,5,3,1,3]
CH=[0,-2,-4,-5]           # chord root per bar (scale steps)
def nf(s,o=0): return ROOT*(2**((SC[s%len(SC)]+12*o)/12))
nsteps=int(DUR/step)+4
kick_times=[]
for i in range(nsteps):
    t=i*step + (beat*.06 if i%2 else 0) + RS.uniform(-.008,.008)
    k=i%16; bar=(i//16)%4; cr=CH[bar]
    if k%2==0: put(t,kick(),.9); kick_times.append(t)
    if k in (4,12): put(t,clap(),.55)
    put(t,hat(.045,k%8==6),.26 if k%2 else .16)
    put(t,sub(nf(cr%len(SC),-2)*.5,beat*.42),.5)
    put(t,pluck(nf(ARP[k]+cr,0),step*1.1),.34)
    put(t+step*.5,pluck(nf(ARP[(k+3)%16]+cr,1),step*.7),.16)
    if k in (0,8): put(t,bell(nf(cr,1),.6),.18)
# ---- timeline ear candy ----
put(.0,whoosh(.6),.55,sfx); put(.05,sparkle(.6,1318),.4,sfx)
for r in range(NR):
    t0=INTRO+r*(SEARCH+REVEAL); tr=t0+SEARCH
    put(t0-.25,whoosh(.45),.5,sfx)                        # round transition
    for i in range(16): put(t0+.015*i, pop(), .2, sfx)    # grid pops
    tck=t0+.2; gap=.26
    while tck<tr-.08:                                     # accelerating ticks (bounded)
        put(tck,tickk(tck>tr-1.0),.45,sfx); gap=max(.085,gap*.86); tck+=gap
    put(tr-1.3,riser(1.3),.55,sfx)                        # suspense build
    put(tr,impact(),.6 if r<NR-1 else .85,sfx)            # reveal hit
    put(tr+.02,boing(),.45,sfx)
    put(tr+.06,sparkle(.8),.5,sfx)
    for i,s in enumerate([0,2,4,7]): put(tr+.1+i*.09,pluck(nf(s,1),.16),.3,sfx)
tO=INTRO+NR*(SEARCH+REVEAL)
put(tO-.3,whoosh(.5),.5,sfx); put(tO,sparkle(1.1),.55,sfx); put(tO,impact(.8),.5,sfx)
for i,s in enumerate([0,2,4,7,9]): put(tO+.45+i*.11,bell(nf(s,1),.5),.3,sfx)
# ---- sidechain pump on the music bed ----
duck=np.ones(N,np.float32)
idx=np.arange(N)/SR
for kt in kick_times:
    s=int(kt*SR); e=min(N,s+int(.17*SR))
    if 0<=s<N and e>s: duck[s:e]=np.minimum(duck[s:e],np.linspace(.42,1.0,e-s))
mus*=duck
# tension: dip the loop slightly under each riser so the build reads, never silent
for r in range(NR):
    tr=INTRO+r*(SEARCH+REVEAL)+SEARCH
    a,b=max(0,int((tr-1.3)*SR)),min(N,int(tr*SR))
    if b>a: mus[a:b]*=np.linspace(1.0,.45,b-a)
    c=min(N,int((tr+.25)*SR))
    if c>b: mus[b:c]*=np.linspace(.3,1.0,c-b)
b=(mus*0.95+sfx*0.9)[:int(SR*DUR)]
b=np.round(b*72)/72                       # light crunch
b=np.tanh(b*1.35)                         # loud, squashed
b*=np.minimum(1,np.arange(len(b))/(SR*.03))
b*=np.clip((len(b)-np.arange(len(b)))/(SR*.3),0,1)
b/=max(1e-6,np.max(np.abs(b)))*1.02
w=wave.open(out,'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((b*32767).astype(np.int16).tobytes()); w.close()
print('DUR',round(DUR,2))
