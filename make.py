"""aislop pipeline: one command from spec -> 60 fps Reel + cover + post notes.
  python3 make.py specs/ring_states_day1.json            full render + Instagram handoff package
  python3 make.py specs/ring_states_day1.json --stills   key-moment PNGs only (QA before the full render)
  python3 make.py specs/ring_states_day1.json --next     write the next episode's spec (series state)
Every number must come from data/ (built by data/build_data.py from .gov sources, integrity-checked)."""
import sys, os, json, datetime, subprocess, shutil
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [ROOT, os.path.join(ROOT, "styles")]
STYLES = {"ring_elimination": "ring", "neon_doubling": "doubling"}

def notes(spec, res):
    if spec["style"] == "ring_elimination":
        L = res["eliminated"]; d = spec.get("episode", 1); n = res["N"]
        cap = (f"{n} states in one spinning ring. Only one doesn't make it out. Day {d}\n\n"
               f"Each circle is sized by the state's July 1, 2025 population (scaled to fit). Escape through the gap and you're safe; "
               f"the last one inside is out, and the other {n-1} come back for Day {d+1}.\n\n"
               f"Source: U.S. Census Bureau, Vintage 2025 Population Estimates (NST-EST2025-ALLDATA).\n\n"
               f"Which state are you rooting for on Day {d+1}? Drop it below 👇\n\n"
               f"#states #census #population #simulation #satisfying #thatdatalover")
        pin = (f"Out so far: {', '.join(spec.get('eliminated_before', []) + [L['name']])}. "
               f"The outcome is physics, not a ranking: bigger circles just have a harder time squeezing through the gap.")
    else:
        cap = ("$1 doubles every bounce. How many bounces until it passes the national debt?\n\n"
               f"It takes {res['bounces']}: bounce {res['bounces']} reaches $70.4 trillion, past the $40.6 trillion in total public debt "
               "outstanding on Nov 9, 2026. On the way it passes the $7.25 federal minimum wage (bounce 3) and the $87,460 "
               "2025 median household income (bounce 17).\n\n"
               "Sources: U.S. Treasury Fiscal Data, Debt to the Penny (11/9/2026); Census Bureau, Income in the United States: 2025; "
               "Dept. of Labor, Wage and Hour Division.\n\n"
               "What number did you guess before the reveal? 👇\n\n"
               "#math #exponential #nationaldebt #data #dataviz #thatdatalover")
        pin = "Math: $1 × 2^46 = $70,368,744,177,664. Debt figure: Treasury 'Debt to the Penny', total public debt outstanding, 2026-11-09."
    audio = ("AUDIO: the sound design is baked in (synthesized; every note is triggered by an on-screen event; "
             "melody = public-domain composition). To use a trending sound instead, post the *_quiet.mp4 and add it in the app.\n"
             "If adding a track: 1) upbeat 120-140 BPM electronic/hyperpop, 2) lo-fi chill 85-95 BPM for the ASMR crowd, "
             "3) suspense/cinematic riser that hits at the reveal. Trending sounds were not checked this run; pick in the app.")
    when = "POST TIME: a guess, not data. Test two windows (e.g. 12-1pm ET vs 7-9pm ET) over ten posts, then use your Insights."
    return f"CAPTION\n-------\n{cap}\n\nPINNED COMMENT\n--------------\n{pin}\n\n{audio}\n\n{when}\n\nCHECKLIST\n- Save video to camera roll\n- Instagram > Reel > pick video > (optional) add audio\n- Paste caption, pick the cover image, post, then pin the comment\n"

def main():
    spec_path = sys.argv[1]; spec = json.load(open(spec_path)); mod = __import__(STYLES[spec["style"]])
    out = os.path.join(ROOT, "out"); os.makedirs(out, exist_ok=True)
    if "--next" in sys.argv:
        res = json.load(open(os.path.join(out, spec["name"] + "_result.json")))
        nxt = dict(spec, episode=spec.get("episode", 1) + 1, eliminated_before=spec.get("eliminated_before", []) + [res["eliminated"]["code"]],
                   name=spec["name"].rsplit("_day", 1)[0] + f"_day{spec.get('episode', 1) + 1}")
        left = res["N"] - 1; nxt["hook_sub"] = f"{left} STATES · 1 GAP · WHO ESCAPES LAST?"
        p = os.path.join(ROOT, "specs", nxt["name"] + ".json"); json.dump(nxt, open(p, "w"), indent=1); print("wrote", p); return
    if "--stills" in sys.argv:
        print(mod.build(spec, ROOT, out, stills=spec.get("qa_stills", [0.5, 6.0, 12.0]))); return
    res = mod.build(spec, ROOT, out)
    json.dump(res, open(os.path.join(out, spec["name"] + "_result.json"), "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    day = datetime.date.today().isoformat(); slug = f"{day}_{spec['style'].replace('_', '-')}_{spec['name']}"
    pkg = os.path.join(out, "post"); os.makedirs(pkg, exist_ok=True)
    final = os.path.join(pkg, slug + ".mp4"); shutil.copy(res["mp4"], final)
    shutil.copy(os.path.join(out, spec["name"] + "_cover.png"), os.path.join(pkg, slug + "_cover.png"))
    quiet = os.path.join(pkg, slug + "_quiet.mp4")                    # same video, sound at -20 dB for an in-app track
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", final, "-c:v", "copy", "-af", "volume=-20dB", "-c:a", "aac", "-b:a", "128k", quiet], check=True)
    open(os.path.join(pkg, slug + "_post-notes.txt"), "w").write(notes(spec, res))
    print("PACKAGE:", pkg, "->", slug)

if __name__ == "__main__": main()
