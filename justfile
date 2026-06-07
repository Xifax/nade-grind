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

demo:
  ffmpeg -i astro/public/source.webm -c:v libvpx-vp9 -crf 33 -b:v 0 -vf scale=1280:-1 astro/public/demo.webm
  ffmpeg -i astro/public/source.webm -c:v libx264 -crf 28 -preset slow -movflags +faststart astro/public/demo.mp4
  ffmpeg -ss 00:00:01 -i astro/public/source.webm -vframes 1 -quality 85 astro/public/poster.webp

debug:
  zellij --layout zj_layouts/nadeshiko-dev.kdl
