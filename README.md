# Nadeshiko Anki Grind

![demo](data/demo.svg)

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

## SUPER TODO:

Use history or stats to ignore (or vice versa, repeat) previously appeared
words. For example:

1. skip a word if n (occurence) > 1 (in history)
2. increase frequency of words with n (occurence) > 1 (in history)
