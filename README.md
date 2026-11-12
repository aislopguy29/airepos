# aislop pipeline
Python 3 + numpy + opencv + Pillow + ffmpeg. No network needed at render time.
1. Refresh data: edit values in data/build_data.py from the .gov URLs in data/provenance.json, then `python3 data/build_data.py` (aborts if checks fail).
2. QA: `python3 make.py specs/ring_states_day1.json --stills`
3. Render + package: `python3 make.py specs/ring_states_day1.json` -> out/post/
4. Next episode: `python3 make.py specs/ring_states_day1.json --next`, then render specs/ring_states_day2.json
See PLAYBOOK.md for the research and the addiction checklist.
