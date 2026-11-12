"""Daily automation: render today's episode for one slot, save it under posts/, advance the series state.
  python3 daily.py a     (12:30 ET slot: STATE ELIMINATION - last one inside is OUT)
  python3 daily.py b     (19:30 ET slot: CROWN RACE - last one inside WINS and leaves the race)
Prints one JSON line starting with POST_JSON= : video path, caption, comment, thumb_offset_ms.
Posting is done by the scheduled agent (Windsor.ai create_video_post), never by this script.
Idempotent: if today's post for the slot already exists, it re-prints it instead of rendering again."""
import sys, os, json, datetime, shutil
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [ROOT, os.path.join(ROOT, "styles")]
import ring

MODES = {
 "elim": dict(title="LAST ONE INSIDE IS OUT", card_word="ELIMINATED", card_color=[255, 85, 85], tally_label="OUT",
              back_text="{n} RETURN TOMORROW  ·  DAY {d}", cta_mid="ROOTING FOR A STATE? DROP IT BELOW",
              cta_end="MOST-NAMED STATE IN THE COMMENTS GETS A SHIELD", ring_color=[120, 215, 255], glow_color=[40, 120, 255]),
 "crown": dict(title="LAST ONE INSIDE WINS", card_word="CHAMPION", card_color=[255, 205, 70], tally_label="CROWNED",
               back_text="{n} RACE AGAIN TOMORROW  ·  DAY {d}", cta_mid="PICK YOUR CHAMPION BELOW",
               cta_end="WHO TAKES THE CROWN TOMORROW?", ring_color=[255, 210, 110], glow_color=[200, 120, 20]),
}
SOURCE = "Source: U.S. Census Bureau, Vintage 2025 Population Estimates · circle size = population (scaled)"

def caption(st, res, n_left):
    L = res["eliminated"]; d = st["episode"]; n = res["N"]; tag = f"S{st['season']} · Day {d}"
    if st["mode"] == "elim":
        hook = f"{n} states in one spinning ring. Only one doesn't make it out. {tag}"
        rule = (f"Escape through the gap and you're safe; the last one inside is out. Today that's {L['name']}. "
                f"The other {n-1} come back tomorrow.")
        q = ("Tomorrow's shield goes to the state named most in the comments: a shielded state survives even if it's the last one inside. "
             "Who are you backing? 👇"); tags = "#states #census #population #simulation #satisfying"
        comment_list = "Out so far"
    else:
        hook = f"{n} states. One gap. The last one still inside takes the crown. {tag}"
        rule = (f"Today's champion is {L['name']}, and it leaves the race. The other {n-1} race again tomorrow.")
        q = "Who takes the crown tomorrow? Call it below 👇"; tags = "#states #census #population #simulation #satisfying"
        comment_list = "Crowned so far"
    sh = res.get("shield_note", "")
    cap = (f"{hook}\n\n{sh}Each circle is sized by the state's July 1, 2025 population (scaled to fit). {rule}\n\n"
           f"Source: U.S. Census Bureau, Vintage 2025 Population Estimates (NST-EST2025-ALLDATA).\n\n{q}\n\n{tags} #thatdatalover")
    com = (f"{comment_list}: {', '.join(st['removed'] + [L['name'] if False else L['code']])}. "
           f"{L['name']}: {L['pop']:,} people (Census, July 1, 2025). The result is physics and chance, not a ranking.")
    return cap, com

def main():
    slot = sys.argv[1]; shield = sys.argv[sys.argv.index("--shield") + 1] if "--shield" in sys.argv else None; sp = os.path.join(ROOT, "state", f"series_{slot}.json"); st = json.load(open(sp))
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).date().isoformat()
    base = f"{today}_{slot}"; vid = os.path.join(ROOT, "posts", base + ".mp4"); meta = os.path.join(ROOT, "posts", base + ".json")
    if os.path.exists(vid) and os.path.exists(meta):
        print("POST_JSON=" + open(meta).read().strip()); return
    import csv
    allc = [r["code"] for r in csv.DictReader(open(os.path.join(ROOT, "data", "state_pop_2025.csv")))]
    if len(allc) - len(st["removed"]) < 3:                       # season over -> new season with everyone back
        st.update(season=st["season"] + 1, episode=1, removed=[])
    spec = dict(MODES[st["mode"]], name=f"daily_{slot}", style="ring_elimination", series=st["series"], episode=st["episode"],
                entities_csv="data/state_pop_2025.csv", source_line=SOURCE, mode=st["mode"], watermark="@eas.ydata",
                shield=(shield if shield and shield not in st["removed"] and st["mode"] == "elim" else None), eliminated_before=st["removed"],
                seed=1 + st["episode"] * 7 + st["season"] * 101 + (0 if slot == "a" else 50), seed_tries=24,
                sim_len=[10, 30], max_photo_finish=3.0, body_seconds=15.0, slowmo=0.5, card_seconds=3.6, cover_t=0.9)
    n_left = len(allc) - len(st["removed"])
    spec["hook_sub"] = f"{n_left} STATES · 1 GAP · WHO ESCAPES LAST?" if st["mode"] == "elim" else f"{n_left} STATES · 1 GAP · LAST INSIDE WINS"
    out = os.path.join(ROOT, "out"); os.makedirs(out, exist_ok=True); os.makedirs(os.path.dirname(vid), exist_ok=True)
    res = ring.build(spec, ROOT, out, log=lambda *a: print(*a, file=sys.stderr))
    shutil.copy(res["mp4"], vid)
    if res.get("saved"): res["shield_note"] = f"Shield held: {res['saved']} survived as the last one inside, so the closest escape went out instead. "
    cap, com = caption(st, res, n_left)
    rec = dict(shield=spec["shield"], date=today, slot=slot, series=st["series"], season=st["season"], episode=st["episode"], video=f"posts/{base}.mp4",
               result_state=res["eliminated"]["code"], caption=cap, comment=com, thumb_offset_ms=900, duration=round(res["duration"], 2))
    json.dump(rec, open(meta, "w"))
    st["removed"].append(res["eliminated"]["code"]); st["episode"] += 1; json.dump(st, open(sp, "w"), indent=1)
    print("POST_JSON=" + json.dumps(rec))

if __name__ == "__main__": main()
