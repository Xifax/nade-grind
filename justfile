run:
  uv run src/tui.py words.txt

export:
  uv run src/export.py

lint:
  ruff format .
