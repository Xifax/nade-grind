"""
Thin async Nadeshiko API client.
Docs: https://nadeshiko.co/docs/api/index.html
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx
from cashews import cache

cache.setup("disk://.cache")
BASE_URL = "https://api.nadeshiko.co"
SEARCH_URL = f"{BASE_URL}/v1/search"
MAX_TAKE = 50


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class Token:
    surface: str  # Surface form as it appears in the sentence
    dictionary: str  # Dictionary / lemma form
    reading: str  # Reading in katakana
    begin: int  # Char offset start in text_ja
    end: int  # Char offset end in text_ja
    pos: str  # Primary part-of-speech
    pos_sub1: str | None
    pos_sub2: str | None
    conjugation_type: str | None
    conjugation_form: str | None

    @classmethod
    def from_dict(cls, d: dict) -> "Token":
        return cls(
            surface=d["s"],
            dictionary=d["d"],
            reading=d["r"],
            begin=d["b"],
            end=d["e"],
            pos=d["p"],
            pos_sub1=d.get("p1"),
            pos_sub2=d.get("p2"),
            conjugation_type=d.get("p4"),
            conjugation_form=d.get("cf"),
        )


@dataclass
class TextJa:
    content: str
    highlight: str | None
    tokens: list[Token] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "TextJa":
        tokens = [Token.from_dict(t) for t in (d.get("tokens") or [])]
        return cls(content=d["content"], highlight=d.get("highlight"), tokens=tokens)


@dataclass
class Translation:
    content: str
    is_machine_translated: bool
    highlight: str | None

    @classmethod
    def from_dict(cls, d: dict) -> "Translation":
        return cls(
            content=d["content"],
            is_machine_translated=d.get("isMachineTranslated", False),
            highlight=d.get("highlight"),
        )


@dataclass
class URLs:
    audio_url: str
    video_url: str
    image_url: str

    @classmethod
    def from_dict(cls, d: dict) -> "URLs":
        return cls(
            audio_url=d["audioUrl"],
            video_url=d["videoUrl"],
            image_url=d["imageUrl"],
        )


@dataclass
class Segment:
    public_id: str
    position: int
    status: str
    start_ms: int
    end_ms: int
    content_rating: str
    episode: int
    media_public_id: str
    text_ja: TextJa
    text_en: Translation
    text_es: Translation
    urls: URLs
    name: str | None

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @classmethod
    def from_dict(cls, d: dict) -> "Segment":
        return cls(
            public_id=d["publicId"],
            position=d["position"],
            status=d["status"],
            start_ms=d["startTimeMs"],
            end_ms=d["endTimeMs"],
            content_rating=d["contentRating"],
            episode=d["episode"],
            media_public_id=d["mediaPublicId"],
            text_ja=TextJa.from_dict(d["textJa"]),
            text_en=Translation.from_dict(d["textEn"]),
            text_es=Translation.from_dict(d["textEs"]),
            urls=URLs.from_dict(d["urls"]),
            name=d["name"],
        )


class NadeshikoError(Exception):
    def __init__(self, status: int, code: str, detail: str):
        self.status = status
        self.code = code
        self.detail = detail
        super().__init__(f"[{status}] {code}: {detail}")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class NadeshikoClient:
    def __init__(self, api_key: str, timeout: float = 15.0):
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._timeout = timeout

    @cache(ttl="10d")
    async def search(
        self,
        query: str,
        n: int = 10,
        *,
        exact_match: bool = False,
    ) -> list[Segment]:
        """Search and return up to *n* segments. Auto-paginates if n > 50."""
        results: list[Segment] = []
        cursor: str | None = None

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            while len(results) < n:
                take = min(MAX_TAKE, n - len(results))
                body: dict = {
                    "query": {
                        "search": query,
                        "exactMatch": exact_match,
                    },
                    "take": take,
                    "include": ["media"],
                }
                if cursor:
                    body["cursor"] = cursor

                resp = await client.post(SEARCH_URL, json=body, headers=self._headers)

                if resp.status_code != 200:
                    data = resp.json()
                    raise NadeshikoError(
                        resp.status_code,
                        data.get("code", "UNKNOWN"),
                        data.get("detail", resp.text),
                    )

                data = resp.json()
                media = iter(data["includes"]["media"].items())
                for raw in data["segments"]:
                    try:
                        # Get media name
                        name = next(media)[1]["nameJa"]
                    except Exception:
                        name = "NoName"

                    raw["name"] = name
                    results.append(Segment.from_dict(raw))

                pagination = data["pagination"]
                if not pagination["hasMore"] or not pagination.get("cursor"):
                    break
                cursor = pagination["cursor"]

        return results[:n]
