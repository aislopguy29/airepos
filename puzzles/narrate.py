# usage: python3 -I puzzles/narrate.py <script.json> <out.wav> [voice] [pitch]
import sys, json, subprocess, wave, os, tempfile, re
import numpy as np
sj,out = sys.argv[1], sys.argv[2]
voice = sys.argv[3] if len(sys.argv)>3 else 'slt'
pitch = float(sys.argv[4]) if len(sys.argv)>4 else 1.0
S=json.load(open(sj)); SR=44100
INTRO,SEARCH,REVEAL,OUTRO=2.0,S.get('search',5.0),2.2,4.0
R=len(S['rounds']); DUR=INTRO+R*(SEARCH+REVEAL)+OUTRO
def synth(text):
    with tempfile.NamedTemporaryFile('w',suffix='.txt',delete=False) as f:
        f.write(re.sub(r'[^A-Za-z0-9 ,.?!\'-]',' ',text)); tf=f.name
    ow=tf+'.wav'
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i',f"flite=textfile={tf}:voice={voice}",
        '-af',f"asetrate=16000*{pitch},aresample={SR},atempo=1.06,lowpass=f=5200",'-ar',str(SR),'-ac','1',ow],check=True)
    w=wave.open(ow);d=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32767;w.close()
    os.unlink(tf);os.unlink(ow);return d
tr=np.zeros(int(SR*DUR),np.float32)
def put(sec,a):
    s=int(sec*SR);n=min(len(a),len(tr)-s)
    if n>0: tr[s:s+n]+=a[:n]
put(0.25, synth(S['title']+'. '+S['sub']))
for i,rd in enumerate(S['rounds']):
    t0=INTRO+i*(SEARCH+REVEAL)
    put(t0+0.15, synth(f"Round {i+1}. {rd['prompt']}."))
    put(t0+SEARCH+0.3, synth("There it is." if i<R-1 else "That is the last one."))
put(INTRO+R*(SEARCH+REVEAL)+0.5, synth("How many did you spot? Comment your score."))
tr=np.clip(tr*1.7,-1,1)
w=wave.open(out,'wb');w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR)
w.writeframes((tr*32767).astype(np.int16).tobytes());w.close()
print('DUR',round(DUR,2))
