"""COUNTRY CLASH: 7-day bracket (QF x4, SF x2, Final), one fight per day.
  python3 daily_clash.py   -> renders today's fight into posts/YYYY-MM-DD_c.mp4, prints POST_JSON=...; prints SERIES_DONE after day 7."""
import sys, os, json, datetime, shutil
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path[:0] = [ROOT, os.path.join(ROOT, "styles")]
import clash
QF = [("FR", "IT"), ("US", "GB"), ("MX", "BR"), ("JP", "IN")]
EFFECT = {"power": "×2.5 hit", "speed": "speed", "heal": "+20 HP"}
N = lambda c: clash.KITS[c]["name"].title() if c not in ("US", "GB") else clash.KITS[c]["name"]

def matchup(day, w):
    if day <= 4: return QF[day - 1], "QUARTERFINAL"
    if day == 5: return (w["1"], w["2"]), "SEMIFINAL"
    if day == 6: return (w["3"], w["4"]), "SEMIFINAL"
    return (w["5"], w["6"]), "THE FINAL"

def next_text(day, w):
    if day < 4: a, b = QF[day]; return f"TOMORROW: {clash.KITS[a]['name']} vs {clash.KITS[b]['name']}"
    if day == 4: return "TOMORROW: THE SEMIFINALS BEGIN"
    if day == 5: return "TOMORROW: THE OTHER SEMIFINAL"
    if day == 6: return "TOMORROW: THE FINAL"
    return "THE TOURNAMENT IS OVER"

def main():
    sp = os.path.join(ROOT, "state", "clash.json"); st = json.load(open(sp)); day = st["day"]
    if day > 7: print("SERIES_DONE"); return
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).date().isoformat()
    vid = os.path.join(ROOT, "posts", f"{today}_c.mp4"); meta = vid[:-4] + ".json"
    if os.path.exists(meta): print("POST_JSON=" + open(meta).read().strip()); return
    (a, b), stage = matchup(day, st["winners"])
    spec = dict(name="daily_c", a=a, b=b, day=day, stage=stage, seed=1 + day * 13, watermark="@eas.ydata", next=next_text(day, st["winners"]))
    if day == 7: spec.update(win_text="{n} IS CHAMPION", card_q="DID YOUR PICK WIN?")
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True); os.makedirs(os.path.dirname(vid), exist_ok=True)
    res = clash.build(spec, ROOT, os.path.join(ROOT, "out"), log=lambda *x: print(*x, file=sys.stderr)); shutil.copy(res["mp4"], vid)
    ka, kb = clash.KITS[a], clash.KITS[b]
    kit = lambda K: ", ".join(f"{e} {EFFECT[k]}" for e, k, _ in K["items"])
    hook = {"QUARTERFINAL": f"{N(a)} vs {N(b)}. One box. Only one leaves.", "SEMIFINAL": f"Semifinal: {N(a)} vs {N(b)}. Winner goes to the final.",
            "THE FINAL": f"The final: {N(a)} vs {N(b)}. One champion."}[stage]
    cap = (f"{hook} Country Clash · Day {day} of 7\n\n{res['winner'].title() if res['winner'] not in ('USA','UK') else res['winner']} survives with {res['winner_hp']} HP. "
           f"Each country can only grab its own power-ups:\n{N(a)}: {kit(ka)}\n{N(b)}: {kit(kb)}\n\n"
           + ("Who wins the whole tournament? 👇" if day < 7 else "Did your pick take the crown? 👇")
           + f"\n\n#countryballs #{ka['name'].lower()} #{kb['name'].lower()} #simulation #satisfying #physics")
    w = dict(st["winners"]); w[str(day)] = res["winner_code"]
    done = [f"D{d}: {clash.KITS[c]['name']}" for d, c in sorted(w.items(), key=lambda x: int(x[0]))]
    com = "Bracket so far: " + " · ".join(done) + f". {next_text(day, w).title()}."
    rec = dict(date=today, slot="c", series="COUNTRY CLASH", day=day, video=f"posts/{today}_c.mp4", winner=res["winner_code"], caption=cap, comment=com,
               thumb_offset_ms=300, duration=round(res["duration"], 2))
    json.dump(rec, open(meta, "w")); st["winners"] = w; st["day"] = day + 1; json.dump(st, open(sp, "w"))
    print("POST_JSON=" + json.dumps(rec))

if __name__ == "__main__": main()
