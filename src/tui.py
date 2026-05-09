"""
Nadeshiko TUI — random sentence drill from a word list.

Usage:
    python app.py words.txt                         # prompts for API key
    NADESHIKO_API_KEY=xxx python app.py words.txt
    python app.py words.txt --key YOUR_KEY

Keyboard shortcuts:
    Space / N   — fetch next sentence
    R           — replay audio
    Q / Ctrl+C  — quit
"""

from __future__ import annotations

import argparse
import itertools
import os
import random
import sys
from pathlib import Path

from dotenv import load_dotenv
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Label, RichLog, Static

import audio
from nadeshiko import NadeshikoClient, NadeshikoError, Segment

# ── POS → chip class ────────────────────────────────────────────────────────


def _token_class(pos: str) -> str:
    if "動詞" in pos:
        return "token-chip-verb"
    if "名詞" in pos:
        return "token-chip-noun"
    if "形容詞" in pos or "形状詞" in pos:
        return "token-chip-adj"
    if "副詞" in pos:
        return "token-chip-adv"
    return "token-chip-other"


# ── App ─────────────────────────────────────────────────────────────────────


class NadeshikoApp(App[None]):
    """Random sentence drill from a word list."""

    TITLE = "Nadeshiko Drill"

    CSS = """
Screen {
    background: $surface;
    layers: base;
}

/* ── top stats bar ── */
#stats-bar {
    height: 1;
    background: $panel;
    padding: 0 2;
    color: $text-muted;
    dock: top;
}
#stats-bar Label {
    width: 1fr;
}
#lbl-count { text-align: left; }
#lbl-word  { text-align: center; color: $accent; }
#lbl-media { text-align: right; }

/* ── main card ── */
#card {
    margin: 1 2;
    border: round $accent;
    background: $panel;
    padding: 1 2;
    height: 14;
}

#ja-text {
    text-style: bold;
    color: $text;
    height: 3;
    width: 1fr;
    content-align: center middle;
    text-align: center;
}

#en-text {
    color: $text-muted;
    height: 2;
    width: 1fr;
    content-align: center middle;
    text-align: center;
}

#placeholder {
    color: $text-disabled;
    text-align: center;
    width: 1fr;
    height: 5;
    content-align: center middle;
    text-style: italic;
}

/* ── token strip ── */
#tokens-scroll {
    height: 3;
    margin-top: 1;
}
#tokens-row {
    height: 1;
    align: left middle;
    padding: 0 1;
}
.token-chip {
    background: $boost;
    color: $text;
    padding: 0 1;
    margin: 0 1 0 0;
    height: 1;
}
.token-chip-verb   { background: #2d4a3e; color: #7ecba1; }
.token-chip-noun   { background: #2a3f5e; color: #7ab4f5; }
.token-chip-adj    { background: #4a3040; color: #d488b8; }
.token-chip-adv    { background: #3e3a20; color: #d4c05a; }
.token-chip-other  { background: $boost;  color: $text-muted; }

/* ── url bar ── */
#url-bar {
    height: 1;
    color: $text-disabled;
    text-align: center;
    content-align: center middle;
}

/* ── button row ── */
#btn-row {
    height: 3;
    align: center middle;
    margin: 1 2;
}
#btn-next {
    min-width: 24;
    margin-right: 2;
}
#btn-replay {
    min-width: 12;
}

/* ── log panel ── */
#log-panel {
    height: 8;
    margin: 0 2 1 2;
    border: round $panel-darken-2;
    background: $panel-darken-1;
    padding: 0 1;
}

/* loading state */
.loading #card {
    border: round $warning;
}
"""

    BINDINGS = [
        Binding("space", "next_sentence", "Next", show=True),
        Binding("n", "next_sentence", "Next", show=False),
        Binding("r", "replay", "Replay audio", show=True),
        Binding("t", "toggle", "Toggle random|seq", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    fetch_count: reactive[int] = reactive(0)
    current_word: reactive[str] = reactive("")
    is_loading: reactive[bool] = reactive(False)

    def __init__(self, words: list[str], client: NadeshikoClient, **kwargs) -> None:
        super().__init__(**kwargs)
        self._words = words
        self._client = client
        self._random = True
        self._cycle = itertools.cycle(self._words)
        self._current_segment: Segment | None = None

    # ── layout ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="stats-bar"):
            yield Label("fetched: 0", id="lbl-count")
            yield Label("mode: random", id="lbl-mode")
            yield Label("", id="lbl-word")
            yield Label("", id="lbl-media")

        with Container(id="card"):
            yield Static(
                "Press [bold]Space[/bold] or click [bold]Next[/bold] to begin",
                id="placeholder",
            )
            yield Static("", id="ja-text")
            yield Static("", id="en-text")
            with ScrollableContainer(id="tokens-scroll"):
                with Horizontal(id="tokens-row"):
                    pass
            yield Static("", id="url-bar")

        with Horizontal(id="btn-row"):
            yield Button("⚡  Next sentence  [Space]", id="btn-next", variant="primary")
            yield Button(
                "🔊  Replay  [R]", id="btn-replay", variant="default", disabled=True
            )

        yield RichLog(id="log-panel", highlight=True, markup=True, max_lines=200)
        yield Footer()

    # ── watchers ────────────────────────────────────────────────────────────

    def watch_is_loading(self, loading: bool) -> None:
        self.query_one("#btn-next", Button).disabled = loading
        if loading:
            self.add_class("loading")
        else:
            self.remove_class("loading")

    def watch_fetch_count(self, count: int) -> None:
        self.query_one("#lbl-count", Label).update(f"fetched: {count}")

    def watch_current_word(self, word: str) -> None:
        self.query_one("#lbl-word", Label).update(f"🔍 {word}" if word else "")

    # ── actions ─────────────────────────────────────────────────────────────

    def action_next_sentence(self) -> None:
        if not self.is_loading:
            self._fetch_random()

    def action_replay(self) -> None:
        if self._current_segment:
            self._play(self._current_segment.urls.audio_url)

    def action_toggle(self) -> None:
        self._random = not self._random
        label = "mode: random" if self._random else "mode: sequence"
        self.query_one("#lbl-mode", Label).update(label)

    # ── events ──────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-next")
    def _on_next(self) -> None:
        self.action_next_sentence()

    @on(Button.Pressed, "#btn-replay")
    def _on_replay(self) -> None:
        self.action_replay()

    @on(Button.Pressed, "#btn-toggle")
    def _on_toggle(self) -> None:
        self.action_toggle()

    # ── worker ──────────────────────────────────────────────────────────────

    @work(exclusive=True, thread=False)
    async def _fetch_random(self) -> None:
        if self._random:
            word = random.choice(self._words)
        else:
            word = self._cycle.__next__()
        # word = random.choice(self._words)
        # OR
        # word = self._cycle.__next__()
        self.current_word = word
        self.is_loading = True
        self._log(f"Searching for [bold cyan]{word}[/bold cyan] …")

        try:
            segments = await self._client.search(word, n=50, exact_match=False)
        except NadeshikoError as exc:
            self._log(f"[red]API error {exc.status}: {exc.code} — {exc.detail}[/red]")
            self.is_loading = False
            return
        except Exception as exc:
            self._log(f"[red]Request failed: {exc}[/red]")
            self.is_loading = False
            return

        if not segments:
            self._log(f"[yellow]No results for [bold]{word}[/bold][/yellow]")
            self.is_loading = False
            return

        segment = random.choice(segments)
        self._current_segment = segment
        self.fetch_count += 1
        await self._show_segment(segment)
        self._play(segment.urls.audio_url)
        self.is_loading = False

    # ── helpers ─────────────────────────────────────────────────────────────

    async def _show_segment(self, seg: Segment) -> None:
        # Switch placeholder ↔ content
        self.query_one("#placeholder", Static).display = False
        self.query_one("#ja-text", Static).display = True
        self.query_one("#en-text", Static).display = True

        self.query_one("#ja-text", Static).update(seg.text_ja.content)
        self.query_one("#en-text", Static).update(seg.text_en.content)

        audio_url = seg.urls.audio_url
        self.query_one("#url-bar", Static).update(
            f"[dim]{audio_url[:80]}…[/dim]"
            if len(audio_url) > 80
            else f"[dim]{audio_url}[/dim]"
        )

        ep_str = f"ep {seg.episode}" if seg.episode else "movie/special"
        self.query_one("#lbl-media", Label).update(
            f"{seg.name} · {ep_str} · {seg.duration_ms / 1000:.1f}s"
        )

        # Rebuild token chips — mount all at once to avoid layout thrash
        token_row = self.query_one("#tokens-row", Horizontal)
        await token_row.remove_children()
        chips = [
            Static(
                f"{tok.surface}[dim]({tok.reading})[/dim]",
                classes=f"token-chip {_token_class(tok.pos)}",
            )
            for tok in (seg.text_ja.tokens or [])
        ]
        if chips:
            await token_row.mount(*chips)

        self.query_one("#btn-replay", Button).disabled = False

        self._log(
            f"[green]✓[/green] [bold]{seg.text_ja.content}[/bold] "
            f"— [dim]{seg.text_en.content}[/dim]"
        )

    def _play(self, url: str) -> None:
        audio.play_url(
            url, on_error=lambda e: self._log(f"[red]Audio error: {e}[/red]")
        )

    def _log(self, msg: str) -> None:
        self.query_one("#log-panel", RichLog).write(msg)


# ── Entry point ─────────────────────────────────────────────────────────────


def load_words(path: Path) -> list[str]:
    words = [w.strip() for w in path.read_text(encoding="utf-8").splitlines()]
    words = [w for w in words if w and not w.startswith("#")]
    if not words:
        print(f"Error: no words found in {path}", file=sys.stderr)
        sys.exit(1)
    return words


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Nadeshiko TUI — random sentence drill from a word list",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "words_file", type=Path, help="Path to word list (.txt, one word per line)"
    )
    parser.add_argument(
        "--key",
        default=os.environ.get("NADESHIKO_API_KEY"),
        help="Nadeshiko API key (or set NADESHIKO_API_KEY)",
    )
    args = parser.parse_args()

    if not args.words_file.exists():
        print(f"Error: file not found: {args.words_file}", file=sys.stderr)
        sys.exit(1)

    load_dotenv()
    api_key = os.environ.get("NADESHIKO_API_KEY")

    if not api_key:
        api_key = args.key
        try:
            api_key = input("Nadeshiko API key: ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if not api_key:
            print("Error: API key is required", file=sys.stderr)
            sys.exit(1)

    words = load_words(args.words_file)
    client = NadeshikoClient(api_key)

    print(f"Loaded {len(words)} word(s) from {args.words_file}")
    NadeshikoApp(words=words, client=client).run()


if __name__ == "__main__":
    main()
