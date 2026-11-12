"""Tally state names in comments -> shield for the next STATE ELIMINATION episode.
Usage: python3 votes.py comments.json [STATE_CODES_ALREADY_OUT...]
comments.json = list of comment texts (strings). Counts each state at most once per comment
(full names, or 2-letter codes written in capitals as a separate word). Prints the winning code, or nothing."""
import sys, json, re, csv, os, collections
ROOT = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "state_pop_2025.csv"))))
out = set(sys.argv[2:]); texts = json.load(open(sys.argv[1])); c = collections.Counter()
names = sorted(((r["name"], r["code"]) for r in rows), key=lambda x: -len(x[0]))
for t in texts:
    t = str(t); seen = set(); low = t.lower()
    for nm, code in names:                       # longest first so "West Virginia" beats "Virginia"
        if re.search(r"\b" + re.escape(nm.lower()) + r"\b", low): seen.add(code); low = low.replace(nm.lower(), " ")
    for code in re.findall(r"\b([A-Z]{2})\b", t):
        if any(r["code"] == code for r in rows) and code not in ("OK", "IN", "ME", "OR", "HI") or (code in ("OK", "IN", "ME", "OR", "HI") and t.strip() == code):
            seen.add(code)
    for code in seen - out: c[code] += 1
if c: print(c.most_common(1)[0][0])
