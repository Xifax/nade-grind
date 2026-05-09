"""
Audio playback helpers.

Uses pygame.mixer for robust cross-platform audio.
The module lazily initialises pygame so it doesn't cost anything if audio
is never used, and is safe to import in headless environments.
"""

from __future__ import annotations

import io
import threading
from typing import Callable

import httpx

_lock = threading.Lock()
_pygame_ready = False


def _ensure_pygame() -> bool:
    global _pygame_ready
    with _lock:
        if _pygame_ready:
            return True
        try:
            import pygame

            pygame.mixer.init()
            _pygame_ready = True
            return True
        except Exception:
            return False


def play_url(
    url: str,
    on_error: Callable[[str], None] | None = None,
) -> None:
    """
    Download *url* and play it via pygame in a background thread.
    Non-blocking: returns immediately.
    """

    def _run() -> None:
        try:
            if not _ensure_pygame():
                if on_error:
                    on_error("pygame.mixer unavailable")
                return

            import pygame

            resp = httpx.get(url, timeout=20, follow_redirects=True)
            resp.raise_for_status()

            buf = io.BytesIO(resp.content)
            buf.name = "audio.mp3"  # hint for pygame format detection

            with _lock:
                pygame.mixer.music.stop()
                pygame.mixer.music.load(buf)
                pygame.mixer.music.play()

        except Exception as exc:  # noqa: BLE001
            if on_error:
                on_error(str(exc))

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def stop() -> None:
    """Stop any currently playing audio."""
    if not _pygame_ready:
        return
    try:
        import pygame

        pygame.mixer.music.stop()
    except Exception:
        pass
