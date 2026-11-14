# usage: python3 -I serial/music.py <mood> <seconds> out.wav ; moods rotate per VARIETY_RULES.md
import sys, numpy as np, wave
mood, D, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
sr=44100; t=np.arange(int(sr*D))/sr
M={ # root freqs, bpm, beat?, arp?, scale
 'dark_ambient':dict(ch=[[55,110,130.8,164.8],[43.65,87.3,130.8,174.6],[49,98,123.5,147]],bpm=0,arp=0,beat=0),
 'tense_pulse':dict(ch=[[55,110,164.8],[58.3,116.5,174.6]],bpm=96,arp=0.04,beat=0.25),
 'lofi_noir':dict(ch=[[110,138.6,164.8,207.7],[98,123.5,146.8,185],[87.3,110,130.8,164.8]],bpm=72,arp=0.05,beat=0.2),
 'piano_minimal':dict(ch=[[110,164.8,220,261.6],[98,146.8,196,246.9]],bpm=0,arp=0.1,beat=0),
 'synth_chase':dict(ch=[[65.4,130.8,196],[73.4,146.8,220],[55,110,165]],bpm=112,arp=0.06,beat=0.3),
 'cinematic_strings':dict(ch=[[73.4,110,146.8,174.6],[65.4,98,130.8,155.6],[82.4,123.5,164.8,196]],bpm=0,arp=0.0,beat=0),
}[mood]
rs=np.random.RandomState(abs(hash(mood))%1000)
o=np.zeros_like(t)
seg=D/len(M['ch'])*1.0
def pad(f):return sum(np.sin(2*np.pi*f*(1+d)*t+i) for i,d in enumerate([-0.003,0,0.003]))/3
for i,ch in enumerate(M['ch']*int(np.ceil(D/(7.5*len(M['ch']))))):
    s0=i*7.5
    lt=t-s0;env=np.clip(lt/1.5,0,1)*np.clip((8.5-lt)/1.5,0,1)*((lt>=0)&(lt<8.5))
    if env.max()==0:continue
    for f in ch:o+=0.12*pad(f)*env
def add(i,x):
    n=min(len(x),len(o)-i)
    if n>0:o[i:i+n]+=x[:n]
if M['bpm']:
    beat=60/M['bpm']
    for k in range(int(D/beat)):
        s=k*beat
        if s<3:continue
        i=int(s*sr);tt=np.arange(int(.25*sr))/sr
        add(i,M['beat']*np.sin(2*np.pi*(52+60*np.exp(-tt*25))*tt)*np.exp(-tt*9))
if M['arp']:
    notes=[M['ch'][0][1]*2,M['ch'][0][2]*2,M['ch'][0][-1]*2,M['ch'][0][2]*2]
    for k in range(int(D/0.5)):
        s=k*0.5
        if s<4:continue
        tt=np.arange(int(.7*sr))/sr
        add(int(s*sr),M['arp']*min(1,(s-4)/8)*np.sin(2*np.pi*notes[k%4]*tt)*np.exp(-tt*4))
o*=np.clip((D-t)/2.0,0,1)*np.clip(t/0.8,0,1)
o/=np.max(np.abs(o))*1.15
w=wave.open(out,'wb');w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((o*32767).astype(np.int16).tobytes());w.close()
