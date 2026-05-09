# Nadeshiko Anki Grind

```bash
# specify Anki decks & fields in src/export.py:107, 117
uv run src/export.py
# grind via Nadeshiko api
export NADESHIKO_API_KEY = ...
uv run src/tui.py words.txt
```

## TODO:

- images
- basic stats
- fetch different example for this item hotkey
- open in YouGlish
- find definition | copy to clipboard | etc, context
