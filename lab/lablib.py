"""Lab helpers: brand-new video types every day for eas.ydata (Instagram) and YouTube Shorts (Metricool).

A lab style lives in lab/styles/<style_id>.py and exposes build(out_mp4, seed, <episode>, log, stills=None) -> dict with
  duration, title (<= 90 chars), description, tags (list), plus anything style specific.
Use engine.py (repo root) for frames, text, audio and encoding: 1080x1920, 60 fps, H.264 + AAC.

  python3 -I lab/lablib.py styles                 -> every type already made (never repeat one)
  python3 -I lab/lablib.py check  <mp4>           -> OK, or the problems (size over 15 MB counts: run shrink)
  python3 -I lab/lablib.py shrink <mp4>           -> re-encode the video stream lighter in place (audio copied)
  python3 -I lab/lablib.py youtube                -> prints the YouTube gate from lab/youtube.json

The registry is derived from the per-post json files (lab/<date>/<slot>.json), so parallel runs never conflict.
"""
import json, os, subprocess, sys, glob, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_MB = 15


def today():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).date().isoformat()


def load():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "lab", "20*", "*.json"))):
        try: d = json.load(open(p))
        except Exception: continue
        if "style_id" in d: out.append(d)
    return out


def record(entry):
    """Kept for older prompts: the per-post json IS the registry entry now, so nothing else is written."""
    return entry


def probe(mp4):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate",
                          "-show_entries", "format=duration,size", "-of", "json", mp4], capture_output=True, text=True).stdout
    return json.loads(out)


def check(mp4, lo=12.0, hi=59.0):
    """ffprobe gate for an Instagram Reel / YouTube Short."""
    if not os.path.exists(mp4): return [f"missing {mp4}"]
    d = probe(mp4); v = [s for s in d["streams"] if s["codec_type"] == "video"]; a = [s for s in d["streams"] if s["codec_type"] == "audio"]
    dur = float(d["format"]["duration"]); size = int(d["format"]["size"]); bad = []
    if not v or (v[0]["width"], v[0]["height"]) != (1080, 1920): bad.append("not 1080x1920")
    if v and v[0]["r_frame_rate"] != "60/1": bad.append(f"fps {v[0]['r_frame_rate']}")
    if not a or a[0]["codec_name"] != "aac": bad.append("no AAC audio")
    if not lo <= dur <= hi: bad.append(f"duration {dur:.1f}s outside {lo}-{hi}s")
    if size > MAX_MB * 2 ** 20: bad.append(f"size {size / 2**20:.1f} MB > {MAX_MB} MB (Instagram ingest failed once at 18 MB): run lablib.py shrink")
    return bad


def shrink(mp4, crf=24):
    tmp = mp4[:-4] + ".shrink.mp4"
    for c in (crf, crf + 3, crf + 6):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp4, "-map", "0", "-c:v", "libx264", "-preset", "medium", "-crf", str(c),
                        "-profile:v", "high", "-level", "4.2", "-pix_fmt", "yuv420p", "-r", "60", "-g", "120",
                        "-c:a", "copy", "-movflags", "+faststart", tmp], check=True)
        if os.path.getsize(tmp) <= MAX_MB * 2 ** 20: break
    os.replace(tmp, mp4); return os.path.getsize(mp4)


def youtube_gate():
    p = os.path.join(ROOT, "lab", "youtube.json")
    return json.load(open(p)) if os.path.exists(p) else {"extra_types_enabled": False}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "styles"
    if cmd == "check":
        bad = check(sys.argv[2]); print("OK" if not bad else "BAD: " + "; ".join(bad))
    elif cmd == "shrink":
        print(f"{shrink(sys.argv[2]) / 2**20:.1f} MB")
    elif cmd == "youtube":
        print(json.dumps(youtube_gate()))
    elif cmd == "styles":
        for e in load(): print(f"{e['date']}  {str(e.get('slot')):<3} {e['style_id']:<22} {e.get('format', '')[:90]}")
