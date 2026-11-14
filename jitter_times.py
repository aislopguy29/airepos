# usage: python3 -I jitter_times.py   -> prints one line per slot: <trigger_id> <cron_expression> <name>
# Picks a new minute within +/- jitter of each base time, keeping slots at least min_gap apart
# and never landing on :00 or :30. Run daily; the scheduled task applies the output.
import json, random, datetime
cfg = json.load(open("schedule_bases.json"))
J, GAP = cfg["jitter_minutes"], cfg["min_gap_minutes"]
R = random.Random(datetime.date.today().isoformat())
taken = []
out = []
for s in cfg["slots"]:
    bh, bm = map(int, s["base"].split(":"))
    base_abs = bh*60 + bm
    best = None
    for _ in range(300):
        cand = base_abs + R.randint(-J, J)
        m = cand % 60
        if m in (0, 30):           # avoid the busiest minutes
            continue
        if any(abs(cand - t) < GAP for t in taken):
            continue
        best = cand; break
    if best is None: best = base_abs
    taken.append(best)
    minute = best % 60
    hours = s["hours"]
    # keep the slot inside its own hour band: shift the hour list if the minute wrapped
    delta = best//60 - (bh)
    hrs = ",".join(str((h + delta) % 24) for h in hours)
    out.append((s["trigger_id"], f"CRON_TZ=America/New_York {minute} {hrs} * * *", s["name"]))
for tid, cron, name in out:
    print(f"{tid} {cron} {name}")
