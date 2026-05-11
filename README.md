# Nadeshiko Anki Grind

![demo](/home/xifax/repos/nadeshiko_anki_export/data/demo.svg)

```bash
# specify Anki decks & fields in src/export.py:107,117 to grind
uv run src/export.py
# set key in .env or in the shell
export NADESHIKO_API_KEY=...
# grind via Nadeshiko api
uv run src/tui.py words.txt
```

## TODO:

[x] key to .env
[x] fix source name
[x] images
[x] basic stats
[x] fetch different example for this item hotkey
[x] find definition | copy to clipboard | etc, context
[ ] add cool info
[ ] open in YouGlish
