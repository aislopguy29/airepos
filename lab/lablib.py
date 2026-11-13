"""YouTube lab helpers: one brand-new video type per day, posted as a YouTube Short via Metricool.

A lab style lives in lab/styles/<style_id>.py and exposes build(out_mp4, seed, log) -> dict with
  duration, title (<= 90 chars), description, tags (list), plus anything style specific.
Use engine.py (repo root) for frames, text, audio and encoding: 1080x1920, 60 fps, H.264 + AAC.

  python3 -I lab/lablib.py check  lab/<date>/<style_id>.mp4     -> prints OK or the problems
  python3 -I lab/lablib.py styles                               -> every style/topic already used (never repeat one)
"""
import json, os, subprocess, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = os.path.join(ROOT, "lab", "registry.json")


def today():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).date().isoformat()


def load():
    return json.load(open(REG)) if os.path.exists(REG) else []


def check(mp4, lo=12.0, hi=59.0):
    """ffprobe gate for a YouTube Short."""
    if not os.path.exists(mp4): return [f"missing {mp4}"]
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate",
                          "-show_entries", "format=duration,size", "-of", "json", mp4], capture_output=True, text=True).stdout
    d = json.loads(out); v = [s for s in d["streams"] if s["codec_type"] == "video"]; a = [s for s in d["streams"] if s["codec_type"] == "audio"]
    dur = float(d["format"]["duration"]); size = int(d["format"]["size"]); bad = []
    if not v or (v[0]["width"], v[0]["height"]) != (1080, 1920): bad.append("not 1080x1920")
    if v and v[0]["r_frame_rate"] != "60/1": bad.append(f"fps {v[0]['r_frame_rate']}")
    if not a or a[0]["codec_name"] != "aac": bad.append("no AAC audio")
    if not lo <= dur <= hi: bad.append(f"duration {dur:.1f}s outside {lo}-{hi}s")
    if size > 100 * 2 ** 20: bad.append(f"size {size / 2**20:.0f} MB")
    return bad


def record(entry):
    """Append one experiment to lab/registry.json (id = <date>_<style_id>)."""
    reg = load(); reg = [e for e in reg if e["id"] != entry["id"]] + [entry]
    json.dump(reg, open(REG, "w"), indent=1)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "styles"
    if cmd == "check":
        bad = check(sys.argv[2]); print("OK" if not bad else "BAD: " + "; ".join(bad))
    elif cmd == "styles":
        for e in load(): print(f"{e['date']}  {e['style_id']:<22} {e.get('format', ''):<28} topic: {e.get('topic', '')}")
