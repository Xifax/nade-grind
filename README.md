# Nadeshiko Anki Grind

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
[ ] fix source name
[ ] add cool info

- images
- basic stats
- fetch different example for this item hotkey
- open in YouGlish
- find definition | copy to clipboard | etc, context
