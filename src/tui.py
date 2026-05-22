"""
Nadeshiko Drill.
Drill word list using examples from Nadeshiko API.

Usage:
    python app.py words.txt                         # prompts for API key
    NADESHIKO_API_KEY=xxx python app.py words.txt
    python app.py words.txt --key YOUR_KEY

Keyboard shortcuts:
    Space / N   ~ fetch next/random word and example sentence
    E           ~ get another example for current word
    R           ~ replay audio
    Q / Ctrl+C  ~ quit
"""

from __future__ import annotations

import argparse
import itertools
import os
import random
import sys
from collections.abc import Iterator
from pathlib import Path

import pyperclip
from dotenv import load_dotenv
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Footer, Header, Label, RichLog, Static

import audio
from nadeshiko import NadeshikoClient, NadeshikoError, Segment

REQUIRED_EXAMPLE_CYCLE_COUNT = 7

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
    overflow-x: auto;
    overflow-y: hidden;
}
#tokens-row {
    height: auto;
    width: auto;
    align: left middle;
    padding: 0 1;
}
.token-chip {
    background: $boost;
    color: $text;
    padding: 0 1;
    margin: 0 1 0 0;
    height: auto;
    width: auto;
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

/* clickable words */
TokenChip {
    pointer: pointer;
}
TokenChip:hover {
    background: $accent-darken-1;
    color: $text;
}
"""
    HISTORY_FILE = Path("history.txt")

    BINDINGS = [
        Binding("space", "next_sentence", "Next", show=True),
        Binding("n", "next_sentence", "Next", show=False),
        Binding("r", "replay", "Replay audio", show=True),
        Binding("t", "toggle_order", "Toggle random|seq", show=True),
        Binding("e", "new_example", "New example", show=True),
        Binding("d", "delete_word", "Delete word", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    fetch_count: reactive[int] = reactive(0)
    current_word: reactive[str] = reactive("")
    is_loading: reactive[bool] = reactive(False)

    def __init__(
        self, words: list[str], client: NadeshikoClient, words_file: Path, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._words = words
        self._client = client
        self._random = True
        self._words_file = words_file
        self._cycle = itertools.cycle(self._words)
        self._history: list[str] = []
        self._current_segment: Segment | None = None
        self._segments: list[Segment] = []
        self._cycle_segments: Iterator[Segment] = iter([])

    # ── layout ──────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        with Horizontal(id="stats-bar"):
            yield Label("fetched total: 0", id="lbl-count")
            yield Label("mode: random", id="lbl-mode")
            yield Label("examples: 0", id="lbl-example-count")
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

    def watch_is_loading(self, loading: bool) -> None:
        self.query_one("#btn-next", Button).disabled = loading
        if loading:
            self.add_class("loading")
        else:
            self.remove_class("loading")

    def watch_fetch_count(self, count: int) -> None:
        self.query_one("#lbl-count", Label).update(f"fetched total: {count}")

    def watch_current_word(self, word: str) -> None:
        self.query_one("#lbl-word", Label).update(f"🔍 {word}" if word else "")

    # ── actions ─────────────────────────────────────────────────────────────

    def action_next_sentence(self) -> None:
        if not self.is_loading:
            self._fetch_next_or_random()

    def action_replay(self) -> None:
        if self._current_segment:
            self._play(self._current_segment.urls.audio_url)

    def action_toggle_order(self) -> None:
        self._random = not self._random
        label = "mode: random" if self._random else "mode: sequence"
        self.query_one("#lbl-mode", Label).update(label)

    def action_new_example(self) -> None:
        if not self.is_loading:
            self._new_example()

    def action_delete_word(self) -> None:
        if not self.is_loading:
            self._delete_word()

    # ── events ──────────────────────────────────────────────────────────────

    @on(Button.Pressed, "#btn-next")
    def _on_next(self) -> None:
        self.action_next_sentence()

    @on(Button.Pressed, "#btn-replay")
    def _on_replay(self) -> None:
        self.action_replay()

    async def on_unmount(self) -> None:
        """Called when the app is shutting down."""
        # Append self.history list to history.txt file
        # TODO: use occurences for custom cycling/random query modes
        with self.HISTORY_FILE.open("a", encoding="utf-8") as f:
            f.write("\n".join(self._history) + "\n")

    # ── worker ──────────────────────────────────────────────────────────────

    @work(exclusive=True, thread=False)
    async def _delete_word(self) -> None:
        self._words.remove(self.current_word)
        self._words_file.write_text("\n".join(self._words))
        self._log(
            f"Removed [bold red]{self.current_word}[/bold red] from [yellow]{self._words_file}[/yellow]"
        )

    @work(exclusive=True, thread=False)
    async def _new_example(self) -> None:
        if not self._segments:
            return

        if len(self._segments) < REQUIRED_EXAMPLE_CYCLE_COUNT:
            segment = self._cycle_segments.__next__()
        else:
            segment = random.choice(self._segments)

        # Update show name
        ep_str = f"ep {segment.episode}" if segment.episode else "movie/special"
        self.query_one("#lbl-media", Label).update(
            f"{segment.name} · {ep_str} · {segment.duration_ms / 1000:.1f}s"
        )

        self._current_segment = segment
        self.fetch_count += 1
        await self._show_segment(segment)
        self._play(segment.urls.audio_url)
        self.is_loading = False
        self._history.append(self.current_word)

    @work(exclusive=True, thread=False)
    async def _fetch_word(self, word: str) -> None:
        self.current_word = word
        self.is_loading = True
        self._log(f"Looking up token [bold cyan]{word}[/bold cyan] …")
        try:
            segments = await self._client.search(word, n=50, exact_match=False)
        except NadeshikoError as exc:
            self._log(
                f"[red]API error {exc.status}: {exc.code} — {exc.detail}[/red]")
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

    @work(exclusive=True, thread=False)
    async def _fetch_next_or_random(self) -> None:
        if self._random:
            word = random.choice(self._words)
        else:
            word = self._cycle.__next__()

        self.current_word = word
        pyperclip.copy(word)
        self._history.append(word)

        self.is_loading = True
        self._log(f"Searching for [bold cyan]{word}[/bold cyan] …")

        try:
            segments = await self._client.search(word, n=50, exact_match=False)
        except NadeshikoError as exc:
            self._log(
                f"[red]API error {exc.status}: {exc.code} ~ {exc.detail}[/red]")
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

        # save segments if user wants different example
        self._segments = segments
        self._cycle_segments = itertools.cycle(self._segments)
        self.query_one("#lbl-example-count",
                       Label).update(f"examples: {len(segments)}")

        # cycle through segments in order, if not a lot of them
        # FIX: first sentence showing twice (check order and how __next__ is
        # called and how cycle is initialized)
        if len(self._segments) < REQUIRED_EXAMPLE_CYCLE_COUNT:
            segment = self._cycle_segments.__next__()
        else:
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

        # Don't need spaces for JP sentence
        content = seg.text_ja.content.replace(" ", "")
        self.query_one("#ja-text", Static).update(content)
        self.query_one("#en-text", Static).update(seg.text_en.content)

        image_url = seg.urls.image_url
        self.query_one("#url-bar", Static).update(
            f"[dim]{image_url[:80]}…[/dim]"
            if len(image_url) > 80
            else f"[dim]{image_url}[/dim]"
        )

        ep_str = f"ep {seg.episode}" if seg.episode else "movie/special"
        self.query_one("#lbl-media", Label).update(
            f"{seg.name} · {ep_str} · {seg.duration_ms / 1000:.1f}s"
        )

        # Rebuild token chips — mount all at once to avoid layout thrash
        token_row = self.query_one("#tokens-row", Horizontal)
        await token_row.remove_children()
        chips = [
            TokenChip(
                tok.surface,
                tok.reading,
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

    def on_token_chip_clicked(self, event: TokenChip.Clicked) -> None:
        event.stop()
        if not self.is_loading:
            self._fetch_word(event.surface)

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
        description="Nadeshiko Drill. Drill word list using examples from Nadeshiko API.",
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
            # Save to .env if it does not exist
            if not os.path.exists(".env"):
                with open(".env", "a") as f:
                    f.write(f"NADESHIKO_API_KEY={api_key}\n")

        except (EOFError, KeyboardInterrupt):
            sys.exit(0)
        if not api_key:
            print("Error: API key is required", file=sys.stderr)
            sys.exit(1)

    words = load_words(args.words_file)
    client = NadeshikoClient(api_key)

    print(f"Loaded {len(words)} word(s) from {args.words_file}")
    NadeshikoApp(words=words, client=client, words_file=args.words_file).run()


class TokenChip(Static):
    """A clickable token chip that triggers a search for that token's surface form."""

    class Clicked(Message):
        def __init__(self, surface: str) -> None:
            super().__init__()
            self.surface = surface

    def __init__(self, surface: str, reading: str, **kwargs) -> None:
        super().__init__(f"{surface}[dim]({reading})[/dim]", **kwargs)
        self._surface = surface

    def on_click(self) -> None:
        self.post_message(self.Clicked(self._surface))


if __name__ == "__main__":
    main()
