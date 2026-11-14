# usage: python3 -I serial/narrate.py <script.json> <voice.wav> <adjusted_script.json> [voice=rms] [pitch=0.92]
# Synthesizes a narrator for each beat + the choice card with ffmpeg's offline flite filter,
# stretches beat durations so the voice always fits, and writes the voice track on the full timeline.
import sys, json, subprocess, wave, os, re, tempfile
import numpy as np
sj, out_wav, out_sj = sys.argv[1], sys.argv[2], sys.argv[3]
voice = sys.argv[4] if len(sys.argv) > 4 else 'rms'
pitch = float(sys.argv[5]) if len(sys.argv) > 5 else 0.92
S = json.load(open(sj))
SR = 44100
NUM = {'0':'zero','1':'one','2':'two','3':'three','4':'four','5':'five','6':'six','7':'seven','8':'eight','9':'nine'}
def norm(t):
    t = t.replace('%',' percent ')
    t = re.sub(r'(\d{1,2}):(\d{2})\s*([ap]m)', lambda m: f"{m.group(1)} {m.group(2)} {'ay em' if m.group(3)=='am' else 'pee em'}", t, flags=re.I)
    t = re.sub(r'\b(\d)\b', lambda m: NUM[m.group(1)], t)
    return re.sub(r'[^A-Za-z0-9 ,.?!\'\-]', ' ', t)
def synth(text):
    with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
        f.write(norm(text)); tf = f.name
    ow = tf + '.wav'
    af = f"asetrate=16000*{pitch},aresample={SR},atempo=1.03,aecho=0.6:0.55:55:0.22,lowpass=f=4600"
    subprocess.run(['ffmpeg','-y','-loglevel','error','-f','lavfi','-i',f"flite=textfile={tf}:voice={voice}",
                    '-af',af,'-ar',str(SR),'-ac','1',ow], check=True)
    w = wave.open(ow); d = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)/32767
    w.close(); os.unlink(tf); os.unlink(ow)
    return d
clips = []   # (slot_index or 'choice', audio)
for i,b in enumerate(S['beats']):
    clips.append((i, synth(' '.join(b['lines']))))
ch = S['choice']
clips.append(('choice', synth(ch['q'].replace('|',' ') + f" Comment {ch['a']}, or {ch['b']}. The majority writes the next part.")))
# stretch durations so each voice clip fits inside its beat
for i,b in enumerate(S['beats']):
    need = len(clips[i][1])/SR + 1.0
    b['dur'] = round(max(b['dur'], need), 2)
S['choice_dur'] = round(max(S.get('choice_dur',7.5), len(clips[-1][1])/SR + 1.8), 2)
# timeline
T = sum(b['dur'] for b in S['beats']); DUR = T + S['choice_dur']
track = np.zeros(int(SR*DUR), np.float32)
t0 = 0.0
for i,b in enumerate(S['beats']):
    a = clips[i][1]; s = int((t0+0.45)*SR); track[s:s+len(a)] += a; t0 += b['dur']
a = clips[-1][1]; s = int((T+0.5)*SR); track[s:s+len(a)] += a
track = np.clip(track*1.6, -1, 1)
w = wave.open(out_wav,'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((track*32767).astype(np.int16).tobytes()); w.close()
json.dump(S, open(out_sj,'w'), indent=1)
print('DUR', round(DUR,2))
