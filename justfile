run:
  uv run src/tui.py words.txt

export:
  uv run src/export.py

lint:
  ruff format .

compile-win:
  uv run compile_by_nuitka.py windows

compile-linux:
  uv run compile_by_nuitka.py linux
