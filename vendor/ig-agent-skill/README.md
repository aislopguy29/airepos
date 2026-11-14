# Vendored from Jakeschincariol/instagram-agent-skill (MIT)

Source: https://github.com/Jakeschincariol/instagram-agent-skill
Copied unmodified: caption.py, humanize.py, detect.py, slop.json, hookscore.py, hooks.json, LICENSE.

Why vendored: scheduled runs start from a fresh cloud session with no plugins installed, so the
pipeline calls these scripts from the repo instead of relying on a skill being present.

Used by `puzzles/make.py`:
- `hookscore.py --hook "<line>" --json`  -> scores candidate caption hooks, best one wins
- `caption.py <file> --json`             -> lints the caption, checks what shows before "... more"
- `humanize.py <file> --json`            -> strips AI fingerprint (em dashes, slop words, watermarks)

To use them interactively as real skills instead, install the upstream plugin:
  /plugin marketplace add Jakeschincariol/instagram-agent-skill
  /plugin install instagram-agent
