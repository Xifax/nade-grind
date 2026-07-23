# Nadeshiko Anki Grind

[App page](https://xifax.gitlab.io/nade_grind/)

Idea:

0. query grindable Anki cards based on a specific criteria (leeches, low ease,
   new cards, old cards, etc) OR just save some words to text file
1. export those cards from Anki via AnkiConnect to plain text
2. grind them using Nadeshiko examples, randomly or in sequence
3. copy current item in clipboard (external lookup?), allow to prune it from input file (seen too many times)
4. save history/session for further evaluation and LLM summary

![demo](astro/public/poster.webp)

## Binaries

By default app wil try to read `words.txt` from the current directory.
You can also drag and drop a `.txt` file onto the executable to use it.

## How to use

```bash
# specify Anki decks & fields in src/export.py:107,117 to grind
uv run src/export.py
# set key in .env or in the shell
export NADESHIKO_API_KEY=...
# grind via Nadeshiko api
uv run src/tui.py words.txt
```

## TODO:

    [ ] tweak letter margin for JP text on Windows
    [ ] llm session export (create automatically, on quit, write to session.txt file)
    [ ] semi-random mode ~> by frequency
    [-] open in YouGlish

## SUPER TODO:

Use history or stats to ignore (or vice versa, repeat) previously appeared
words. For example:

    1. skip a word if n (occurence) > 1 (in history)
    2. increase frequency of words with n (occurence) > 1 (in history)
