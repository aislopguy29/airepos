# usage: python3 -I puzzles/run.py <YYYY-MM-DD> <slot> [seed]
# End-to-end daily build: fresh puzzle -> slop audio -> 1080x1920@60 mp4 -> verified.
import sys, os, json, subprocess, shutil
date, slot = sys.argv[1], sys.argv[2]
seed = sys.argv[3:4]
out = os.path.join("puzzles", date); os.makedirs(out, exist_ok=True)
def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode: sys.exit(f"FAILED: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()
npm_root = subprocess.run(["npm","root","-g"], capture_output=True, text=True).stdout.strip()
env = {**os.environ, "NODE_PATH": npm_root}
run(["python3","-I","puzzles/make.py", out, slot, *seed])
script = os.path.join(out, f"{slot}_script.json"); meta_p = os.path.join(out, f"{slot}.json")
meta = json.load(open(meta_p))
wav, wav2 = f"/tmp/pz_{slot}.wav", f"/tmp/pz_{slot}_n.wav"
run(["python3","-I","puzzles/memeaudio.py", script, wav, str(meta["seed"] % 100000)])
run(["ffmpeg","-y","-loglevel","error","-i",wav,"-af","loudnorm=I=-13:TP=-1.0:LRA=11","-ar","44100","-ac","2",wav2])
raw, final = f"/tmp/pz_{slot}_raw.mp4", os.path.join(out, f"{slot}.mp4")
run(["node","puzzles/render.js", script, raw, wav2], env=env)
run(["ffmpeg","-y","-loglevel","error","-i",raw,"-c:v","libx264","-crf","23","-preset","fast",
     "-tune","animation","-pix_fmt","yuv420p","-c:a","copy","-movflags","+faststart", final])
probe = run(["ffprobe","-v","error","-show_entries","stream=codec_name,width,height,r_frame_rate",
             "-show_entries","format=duration,size","-of","json", final])
p = json.loads(probe); v = [s for s in p["streams"] if s.get("width")][0]
a = [s for s in p["streams"] if s.get("codec_name") in ("aac","mp3")]
dur = float(p["format"]["duration"]); size = int(p["format"]["size"])
errs = []
if (v["width"], v["height"]) != (1080, 1920): errs.append(f"size {v['width']}x{v['height']}")
if v["r_frame_rate"] != "60/1": errs.append(f"fps {v['r_frame_rate']}")
if not a: errs.append("no audio")
if not (18 <= dur <= 50): errs.append(f"duration {dur:.1f}s")
if size > 50*1024*1024: errs.append(f"size {size/1e6:.1f}MB")
if errs: sys.exit("CHECK FAILED: " + ", ".join(errs))
meta.update({"video": final, "duration": round(dur,2), "size_mb": round(size/1e6,2)})
json.dump(meta, open(meta_p,"w"), indent=1)
print("OK")
print("POST_JSON=" + json.dumps(meta))
