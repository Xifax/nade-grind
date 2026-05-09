"""
Nadeshiko API client — searches anime/J-Drama segments and returns
Japanese text (textJa.content) and audio links (urls.audioUrl).

Docs: https://nadeshiko.co/docs/api/index.html
Auth: Bearer API key from https://nadeshiko.co/user/developer

Usage:
    python nadeshiko_client.py <query> [--n N] [--exact] [--api-key KEY]

Examples:
    NADESHIKO_API_KEY=your_key python nadeshiko_client.py "食べる" --n 5
    python nadeshiko_client.py "おはよう" --n 10 --exact --api-key your_key
"""

import argparse
import os
import sys
from dataclasses import dataclass

import httpx

BASE_URL = "https://api.nadeshiko.co"
SEARCH_ENDPOINT = f"{BASE_URL}/v1/search"

# API limits: take is 1–50 per request, 150 req/min, 5000 req/month
MAX_TAKE_PER_REQUEST = 50


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class SegmentResult:
    public_id: str
    text_ja: str
    text_en: str
    audio_url: str
    image_url: str
    video_url: str
    episode: int
    media_public_id: str
    start_ms: int
    end_ms: int

    def display(self, index: int) -> None:
        duration_s = (self.end_ms - self.start_ms) / 1000
        print(f"\n[{index}] {self.text_ja}")
        print(f"     EN      : {self.text_en}")
        print(f"     Audio   : {self.audio_url}")
        print(
            f"     Duration: {duration_s:.2f}s  |  Episode: {self.episode}  |  Media: {self.media_public_id}"
        )


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


def _parse_segment(raw: dict) -> SegmentResult:
    return SegmentResult(
        public_id=raw["publicId"],
        text_ja=raw["textJa"]["content"],
        text_en=raw["textEn"]["content"],
        audio_url=raw["urls"]["audioUrl"],
        image_url=raw["urls"]["imageUrl"],
        video_url=raw["urls"]["videoUrl"],
        episode=raw["episode"],
        media_public_id=raw["mediaPublicId"],
        start_ms=raw["startTimeMs"],
        end_ms=raw["endTimeMs"],
    )


def search(
    query: str,
    n: int,
    *,
    exact_match: bool = False,
    api_key: str,
    timeout: float = 10.0,
) -> list[SegmentResult]:
    """
    Search Nadeshiko for Japanese segments matching *query*.

    Paginates automatically if n > 50 (the per-request maximum).

    Parameters
    ----------
    query:       Search expression. Supports kanji, kana, romaji, English/Spanish,
                 boolean operators (AND/OR/NOT), wildcards (te*t), and quoted phrases.
    n:           Total number of results to return (1–250 recommended).
    exact_match: Require exact phrase matching; disables fuzzy/partial matches.
    api_key:     Nadeshiko Bearer API key.
    timeout:     HTTP request timeout in seconds.
    """
    results: list[SegmentResult] = []
    cursor: str | None = None
    headers = {"Authorization": f"Bearer {api_key}"}

    with httpx.Client(timeout=timeout) as client:
        while len(results) < n:
            take = min(MAX_TAKE_PER_REQUEST, n - len(results))

            body: dict = {
                "query": {
                    "search": query,
                    "exactMatch": exact_match,
                },
                "take": take,
            }
            if cursor:
                body["cursor"] = cursor

            response = client.post(SEARCH_ENDPOINT, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()

            for raw in data["segments"]:
                results.append(_parse_segment(raw))

            pagination = data["pagination"]
            if not pagination["hasMore"] or not pagination["cursor"]:
                break

            cursor = pagination["cursor"]

    return results[:n]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Nadeshiko for Japanese sentences with audio.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("query", help="Search expression (kanji/kana/romaji/EN/ES)")
    parser.add_argument(
        "--n",
        type=int,
        default=10,
        metavar="N",
        help="Number of results to return (default: 10, max per request: 50)",
    )
    parser.add_argument(
        "--exact",
        action="store_true",
        help="Require exact phrase match (disables fuzzy/partial matching)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("NADESHIKO_API_KEY"),
        help="API key (or set NADESHIKO_API_KEY env var)",
    )
    args = parser.parse_args()

    if not args.api_key:
        parser.error(
            "API key required. Pass --api-key or set the NADESHIKO_API_KEY environment variable.\n"
            "Generate a key at https://nadeshiko.co/user/developer"
        )

    print(f"Searching for: {args.query!r}  (n={args.n}, exact={args.exact})")
    print("-" * 60)

    try:
        results = search(
            args.query,
            n=args.n,
            exact_match=args.exact,
            api_key=args.api_key,
        )
    except httpx.HTTPStatusError as e:
        body = e.response.text
        print(f"HTTP {e.response.status_code}: {body}", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("No results found.")
        return

    for i, result in enumerate(results, start=1):
        result.display(i)

    print(f"\n{len(results)} result(s) returned.")


if __name__ == "__main__":
    main()
